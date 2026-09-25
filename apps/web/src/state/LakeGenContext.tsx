import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  addCatalog as addCatalogRequest,
  ApiError,
  createSession,
  deleteCatalog as deleteCatalogRequest,
  listCatalogs,
  listSessions,
  listSessionTurns,
} from '../api/client';
import { runTurn } from '../api/sse';
import { readLocal, removeLocal, writeLocal } from '../lib/storage';
import { useToast } from '../components/ui/Toast';
import type {
  AgentTurnInfo,
  CatalogCreateRequest,
  CatalogResponse,
  Message,
  SessionResponse,
} from '../api/types';

const ACTIVE_CATALOG_KEY = 'lakegen.activeCatalog';
const RETAINED_TURNS_KEY = 'lakegen.retainedTurns';
const EMPTY_MESSAGES: Message[] = [];
const SESSION_PAGE_SIZE = 10;
const TURN_PAGE_SIZE = 100;
const MAX_RETAINED_TURNS_BYTES = 200_000;
const SESSION_EXPIRED_MESSAGE = 'This agent session expired. Retry to continue in a new session.';

interface Conversation {
  id: string;
  sessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  updatedAt: number;
  live: boolean;
}

interface LakeGenValue {
  catalogs: CatalogResponse[];
  catalogsError: string | null;
  catalogsLoading: boolean;
  catalogsRefreshing: boolean;
  refreshCatalogs: () => Promise<CatalogResponse[] | null>;
  addCatalog: (body: CatalogCreateRequest, signal?: AbortSignal) => Promise<void>;
  removeCatalog: (name: string) => Promise<void>;
  activeCatalogName: string | null;
  setActiveCatalogName: (name: string) => void;
  activeCatalog: CatalogResponse | null;
  sessions: SessionResponse[];
  sessionsLoading: boolean;
  sessionsLoadingMore: boolean;
  sessionsError: string | null;
  sessionsHasMore: boolean;
  loadMoreSessions: () => Promise<void>;
  selectedSessionId: string | null;
  selectSession: (session: SessionResponse) => Promise<void>;
  sessionHistoryLoading: boolean;
  sessionHistoryError: string | null;
  activeSessionLive: boolean;
  messages: Message[];
  isStreaming: boolean;
  sendError: string | null;
  sendMessage: (text: string) => Promise<boolean>;
  stopStreaming: () => void;
  newConversation: () => void;
}

const LakeGenContext = createContext<LakeGenValue | null>(null);

function uid(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`;
}

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<Message>;
  if (typeof message.id !== 'string' || typeof message.text !== 'string' || typeof message.createdAt !== 'number') {
    return false;
  }
  if (message.role === 'user') return true;
  return message.role === 'assistant' && typeof message.status === 'string';
}

function readRetainedTurns(): Record<string, Message[]> {
  try {
    const stored = JSON.parse(readLocal(RETAINED_TURNS_KEY) ?? '{}') as unknown;
    if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {};
    return Object.fromEntries(
      Object.entries(stored).flatMap(([sessionId, messages]) => {
        if (!Array.isArray(messages)) return [];
        const valid = messages.filter(isMessage);
        return valid.length > 0 ? [[sessionId, valid] as const] : [];
      }),
    );
  } catch {
    return {};
  }
}

function writeRetainedTurns(sessionId: string, messages: Message[]) {
  const next = { ...readRetainedTurns(), [sessionId]: messages };
  const latest = (msgs: Message[]) => msgs.reduce((t, m) => Math.max(t, m.createdAt), 0);
  for (const id of Object.keys(next)
    .filter((key) => key !== sessionId)
    .sort((a, b) => latest(next[a]) - latest(next[b]))) {
    if (JSON.stringify(next).length <= MAX_RETAINED_TURNS_BYTES) break;
    delete next[id];
  }
  writeLocal(RETAINED_TURNS_KEY, JSON.stringify(next));
}

function clearRetainedTurns(sessionId: string) {
  const next = readRetainedTurns();
  if (!(sessionId in next)) return;
  delete next[sessionId];
  writeLocal(RETAINED_TURNS_KEY, JSON.stringify(next));
}

function retainConversation(conversation: Conversation | undefined) {
  if (!conversation?.sessionId || conversation.messages.length === 0) return;
  writeRetainedTurns(conversation.sessionId, conversation.messages);
}

function messagesFromTurns(turns: AgentTurnInfo[]): Message[] {
  return turns.slice().reverse().flatMap((turn) => {
    const result = turn.result;
    const turnMessages =
      result && typeof result === 'object' && 'turn_messages' in result
        ? result.turn_messages
        : null;
    const rawMessages =
      turnMessages && typeof turnMessages === 'object' && 'messages' in turnMessages
        ? turnMessages.messages
        : null;
    if (!Array.isArray(rawMessages)) return [];

    const createdAt = Date.parse(turn.created_at);
    return rawMessages.flatMap((value, index): Message[] => {
      if (!value || typeof value !== 'object') return [];
      const role = 'role' in value ? value.role : null;
      const content = 'content' in value ? value.content : null;
      if ((role !== 'user' && role !== 'assistant') || typeof content !== 'string' || !content) {
        return [];
      }
      const base = {
        id: `history_${turn.id}_${index}`,
        text: content,
        createdAt: Number.isNaN(createdAt) ? Date.now() : createdAt + index,
      };
      if (role === 'user') return [{ ...base, role }];
      return [{
        ...base,
        role,
        status: result.stop_reason === 'completed' ? 'done' : 'incomplete',
        stopReason: typeof result.stop_reason === 'string' ? result.stop_reason : undefined,
      }];
    });
  });
}

export function LakeGenProvider({ children }: { children: React.ReactNode }) {
  const { notify } = useToast();
  const [catalogs, setCatalogs] = useState<CatalogResponse[]>([]);
  const [catalogsError, setCatalogsError] = useState<string | null>(null);
  const [catalogsLoading, setCatalogsLoading] = useState(true);
  const [catalogsRefreshing, setCatalogsRefreshing] = useState(false);
  const [activeCatalogName, setActiveCatalogNameState] = useState<string | null>(
    () => readLocal(ACTIVE_CATALOG_KEY),
  );
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsLoadingMore, setSessionsLoadingMore] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sessionsHasMore, setSessionsHasMore] = useState(false);
  const [sessionHistoryLoading, setSessionHistoryLoading] = useState(false);
  const [sessionHistoryError, setSessionHistoryError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Record<string, Conversation>>({});
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const catalogsRef = useRef<CatalogResponse[]>([]);
  const hasLoadedCatalogsRef = useRef(false);
  const activeCatalogNameRef = useRef<string | null>(activeCatalogName);
  const sessionsRef = useRef<SessionResponse[]>([]);
  const sessionsRevisionRef = useRef(0);
  const sessionsLoadingMoreRef = useRef(false);
  const conversationsRef = useRef(conversations);
  const activeConversationIdRef = useRef(activeConversationId);
  const selectedSessionIdRef = useRef(selectedSessionId);
  const historyAbortRef = useRef<AbortController | null>(null);
  const pendingSessionRef = useRef<Map<string, Promise<string>>>(new Map());
  const abortsRef = useRef(new Map<string, AbortController>());

  const activeConversation = activeConversationId ? conversations[activeConversationId] : undefined;
  const messages = activeConversation?.messages ?? EMPTY_MESSAGES;
  const isStreaming = activeConversation?.isStreaming ?? false;
  const activeSessionLive = activeConversation?.live ?? true;

  const updateConversations = useCallback(
    (update: (current: Record<string, Conversation>) => Record<string, Conversation>) => {
      const next = update(conversationsRef.current);
      conversationsRef.current = next;
      setConversations(next);
    },
    [],
  );

  const createConversation = useCallback((): Conversation => {
    const conversation: Conversation = {
      id: uid('conversation'),
      sessionId: null,
      messages: [],
      isStreaming: false,
      updatedAt: Date.now(),
      live: true,
    };
    updateConversations((current) => ({ ...current, [conversation.id]: conversation }));
    activeConversationIdRef.current = conversation.id;
    setActiveConversationId(conversation.id);
    return conversation;
  }, [updateConversations]);

  const replaceSessions = useCallback((next: SessionResponse[]) => {
    sessionsRef.current = next;
    setSessions(next);
  }, []);

  const commitSessions = useCallback((next: SessionResponse[]) => {
    sessionsRevisionRef.current += 1;
    replaceSessions(next);
  }, [replaceSessions]);

  const refreshSessionHead = useCallback(async () => {
    const page = await listSessions();
    const pageIds = new Set(page.map((session) => session.id));
    const tail = sessionsRef.current.filter((session) => !pageIds.has(session.id));
    commitSessions([...page, ...tail]);
    setSessionsHasMore((current) => (
      tail.length > 0 ? current : page.length === SESSION_PAGE_SIZE
    ));
    setSessionsError(null);
  }, [commitSessions]);

  const loadMoreSessions = useCallback(async () => {
    if (sessionsLoadingMoreRef.current) return;
    sessionsLoadingMoreRef.current = true;
    setSessionsLoadingMore(true);
    try {
      const page = await listSessions(sessionsRef.current.length);
      const ids = new Set(sessionsRef.current.map((session) => session.id));
      commitSessions([...sessionsRef.current, ...page.filter((session) => !ids.has(session.id))]);
      setSessionsHasMore(page.length === SESSION_PAGE_SIZE);
      setSessionsError(null);
    } catch (error) {
      setSessionsError(error instanceof Error ? error.message : 'Failed to load sessions');
    } finally {
      sessionsLoadingMoreRef.current = false;
      setSessionsLoadingMore(false);
    }
  }, [commitSessions]);

  useEffect(() => {
    let active = true;
    const revision = sessionsRevisionRef.current;
    listSessions()
      .then((page) => {
        if (!active || sessionsRevisionRef.current !== revision) return;
        replaceSessions(page);
        setSessionsHasMore(page.length === SESSION_PAGE_SIZE);
        setSessionsError(null);
      })
      .catch((error: unknown) => {
        if (active) {
          setSessionsError(error instanceof Error ? error.message : 'Failed to load sessions');
        }
      })
      .finally(() => {
        if (active) setSessionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [replaceSessions]);

  const selectSession = useCallback(async (session: SessionResponse) => {
    historyAbortRef.current?.abort();
    const controller = new AbortController();
    historyAbortRef.current = controller;
    selectedSessionIdRef.current = session.id;
    setSelectedSessionId(session.id);
    setSessionHistoryError(null);
    setSendError(null);

    const existing = Object.values(conversationsRef.current).find(
      (conversation) => conversation.sessionId === session.id,
    );
    if (existing) {
      updateConversations((current) => {
        const conversation = current[existing.id];
        if (!conversation) return current;
        return { ...current, [existing.id]: { ...conversation, live: session.live } };
      });
      activeConversationIdRef.current = existing.id;
      setActiveConversationId(existing.id);
    } else {
      activeConversationIdRef.current = null;
      setActiveConversationId(null);
      setSessionHistoryLoading(true);
    }

    try {
      const turns: AgentTurnInfo[] = [];
      for (let offset = 0; ; offset += TURN_PAGE_SIZE) {
        const page = await listSessionTurns(
          session.id,
          offset,
          TURN_PAGE_SIZE,
          controller.signal,
        );
        turns.push(...page);
        if (page.length < TURN_PAGE_SIZE) break;
      }
      if (controller.signal.aborted || selectedSessionIdRef.current !== session.id) return;
      const history = messagesFromTurns(turns);
      const retained = history.length > 0 ? [] : readRetainedTurns()[session.id] ?? [];
      if (history.length > 0) clearRetainedTurns(session.id);
      updateConversations((current) => {
        const previous = Object.values(current).find(
          (conversation) => conversation.sessionId === session.id,
        );
        if (previous?.isStreaming) {
          return {
            ...current,
            [previous.id]: { ...previous, live: session.live },
          };
        }
        const id = previous?.id ?? `session_${session.id}`;
        const messages = history.length > 0
          ? history
          : previous && previous.messages.length > 0
            ? previous.messages
            : retained;
        return {
          ...current,
          [id]: {
            id,
            sessionId: session.id,
            messages,
            isStreaming: false,
            updatedAt: Date.parse(session.created_at) || Date.now(),
            live: session.live,
          },
        };
      });
      const applied = Object.values(conversationsRef.current).find(
        (conversation) => conversation.sessionId === session.id,
      );
      if (applied && selectedSessionIdRef.current === session.id) {
        activeConversationIdRef.current = applied.id;
        setActiveConversationId(applied.id);
      }
    } catch (error) {
      if (controller.signal.aborted || selectedSessionIdRef.current !== session.id) return;
      if (existing) {
        notify({
          tone: 'error',
          message: error instanceof Error ? error.message : 'Failed to refresh session history',
        });
      } else {
        setSessionHistoryError(
          error instanceof Error ? error.message : 'Failed to load session history',
        );
      }
    } finally {
      if (historyAbortRef.current === controller) {
        historyAbortRef.current = null;
        setSessionHistoryLoading(false);
      }
    }
  }, [notify, updateConversations]);

  const ensureSession = useCallback((conversationId: string): Promise<string> => {
    const conversation = conversationsRef.current[conversationId];
    if (conversation?.sessionId) return Promise.resolve(conversation.sessionId);

    const pending = pendingSessionRef.current.get(conversationId);
    if (pending) return pending;

    const promise = createSession()
      .then(({ id }) => {
        updateConversations((current) => {
          const currentConversation = current[conversationId];
          if (!currentConversation) return current;
          return {
            ...current,
            [conversationId]: { ...currentConversation, sessionId: id, live: true },
          };
        });
        retainConversation(conversationsRef.current[conversationId]);
        if (activeConversationIdRef.current === conversationId) {
          selectedSessionIdRef.current = id;
          setSelectedSessionId(id);
        }
        void refreshSessionHead().catch((error: unknown) => {
          setSessionsError(error instanceof Error ? error.message : 'Failed to refresh sessions');
        });
        return id;
      })
      .finally(() => {
        pendingSessionRef.current.delete(conversationId);
      });

    pendingSessionRef.current.set(conversationId, promise);
    return promise;
  }, [refreshSessionHead, updateConversations]);

  const updateConversation = useCallback(
    (conversationId: string, update: (conversation: Conversation) => Conversation) => {
      updateConversations((current) => {
        const conversation = current[conversationId];
        if (!conversation) return current;
        return { ...current, [conversationId]: update(conversation) };
      });
    },
    [updateConversations],
  );

  const activeCatalog = useMemo(
    () => catalogs.find((c) => c.name === activeCatalogName) ?? null,
    [catalogs, activeCatalogName],
  );

  const updateActiveCatalog = useCallback((name: string | null) => {
    activeCatalogNameRef.current = name;
    setActiveCatalogNameState(name);
    if (name) writeLocal(ACTIVE_CATALOG_KEY, name);
    else removeLocal(ACTIVE_CATALOG_KEY);
  }, []);

  const setActiveCatalogName = useCallback(
    (name: string) => updateActiveCatalog(name),
    [updateActiveCatalog],
  );

  const refreshCatalogs = useCallback(async (): Promise<CatalogResponse[] | null> => {
    const isInitialLoad = !hasLoadedCatalogsRef.current;
    if (isInitialLoad) setCatalogsLoading(true);
    else setCatalogsRefreshing(true);
    try {
      const next = await listCatalogs();
      catalogsRef.current = next;
      setCatalogs(next);
      setCatalogsError(null);
      const current = activeCatalogNameRef.current;
      const nextActive =
        current && next.some((catalog) => catalog.name === current)
          ? current
          : next.length === 1
            ? next[0].name
            : null;
      updateActiveCatalog(nextActive);
      if (current && current !== nextActive) {
        notify({
          tone: 'info',
          message: 'The active catalog is no longer available. Select a catalog before sending a request.',
        });
      }
      hasLoadedCatalogsRef.current = true;
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load catalogs';
      setCatalogsError(message);
      if (!isInitialLoad) notify({ tone: 'error', message });
      return null;
    } finally {
      if (isInitialLoad) setCatalogsLoading(false);
      else setCatalogsRefreshing(false);
    }
  }, [notify, updateActiveCatalog]);

  useEffect(() => {
    void refreshCatalogs();
  }, [refreshCatalogs]);

  const addCatalog = useCallback(async (body: CatalogCreateRequest, signal?: AbortSignal) => {
    const created = await addCatalogRequest(body, signal);
    const next = [...catalogsRef.current.filter((catalog) => catalog.name !== created.name), created];
    catalogsRef.current = next;
    setCatalogs(next);
    if (!activeCatalogNameRef.current && next.length === 1) updateActiveCatalog(created.name);
  }, [updateActiveCatalog]);

  const removeCatalog = useCallback(async (name: string) => {
    await deleteCatalogRequest(name);
    const next = catalogsRef.current.filter((catalog) => catalog.name !== name);
    catalogsRef.current = next;
    setCatalogs(next);
    if (activeCatalogNameRef.current === name) {
      updateActiveCatalog(next.length === 1 ? next[0].name : null);
      notify({
        tone: 'info',
        message: 'Select a catalog before sending a request.',
      });
    }
  }, [notify, updateActiveCatalog]);

  const stopStreaming = useCallback(() => {
    const conversationId = activeConversationIdRef.current;
    if (conversationId) abortsRef.current.get(conversationId)?.abort();
  }, []);

  const newConversation = useCallback(() => {
    historyAbortRef.current?.abort();
    historyAbortRef.current = null;
    activeConversationIdRef.current = null;
    setActiveConversationId(null);
    selectedSessionIdRef.current = null;
    setSelectedSessionId(null);
    setSessionHistoryError(null);
    setSessionHistoryLoading(false);
    setSendError(null);
  }, []);

  const patchAssistant = useCallback(
    (conversationId: string, id: string, patch: (message: Message) => Message) => {
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        updatedAt: Date.now(),
        messages: conversation.messages.map((message) => (message.id === id ? patch(message) : message)),
      }));
    },
    [updateConversation],
  );

  const sendMessage = useCallback(
    async (text: string): Promise<boolean> => {
      const trimmed = text.trim();
      if (!trimmed) return false;

      const conversation =
        activeConversationIdRef.current && conversationsRef.current[activeConversationIdRef.current]
          ? conversationsRef.current[activeConversationIdRef.current]
          : createConversation();
      if (conversation.isStreaming) {
        setSendError('A response is already being generated.');
        return false;
      }
      if (!conversation.live) {
        setSendError('This session is no longer active. Start a new conversation to continue.');
        return false;
      }

      const assistantId = uid('msg');
      updateConversation(conversation.id, (current) => ({
        ...current,
        isStreaming: true,
        updatedAt: Date.now(),
        messages: [
          ...current.messages,
          { id: uid('msg'), role: 'user', text: trimmed, createdAt: Date.now() },
          { id: assistantId, role: 'assistant', text: '', status: 'streaming', createdAt: Date.now() },
        ],
      }));

      let sessionId: string;
      try {
        sessionId = await ensureSession(conversation.id);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Could not start a conversation.';
        setSendError(message);
        notify({ tone: 'error', message });
        patchAssistant(conversation.id, assistantId, (item) => ({
          ...item,
          role: 'assistant',
          status: 'error',
          errorMessage: message,
        }));
        updateConversation(conversation.id, (current) => ({ ...current, isStreaming: false }));
        return true;
      }

      setSendError(null);
      const controller = new AbortController();
      abortsRef.current.set(conversation.id, controller);

      const expireSession = () => {
        updateConversation(conversation.id, (current) => ({ ...current, sessionId: null }));
        notify({ tone: 'info', message: 'The agent session expired. Retry the request to continue.' });
      };

      try {
        let streamError = false;
        const { turnDone } = await runTurn(
          sessionId,
          {
            text: trimmed,
            catalog_name: activeCatalogName,
          },
          (event) => {
            if (event.type === 'text_delta') {
              patchAssistant(conversation.id, assistantId, (m) => ({
                ...m,
                text: m.text + event.data.text,
              }));
            } else if (event.type === 'turn_done') {
              clearRetainedTurns(sessionId);
              patchAssistant(conversation.id, assistantId, (m) => ({
                ...m,
                role: 'assistant',
                status: event.data.stop_reason === 'completed' ? 'done' : 'incomplete',
                stopReason: event.data.stop_reason,
              }));
            } else if (event.type === 'error') {
              streamError = true;
              const sessionExpired = event.data.code === 'NOT_FOUND';
              if (sessionExpired) expireSession();
              patchAssistant(conversation.id, assistantId, (m) => ({
                ...m,
                role: 'assistant',
                status: 'error',
                errorMessage: sessionExpired ? SESSION_EXPIRED_MESSAGE : event.data.message,
                errorCode: event.data.code,
                retryText: sessionExpired ? trimmed : undefined,
              }));
            }
          },
          controller.signal,
        );
        if (!streamError && !turnDone) {
          patchAssistant(conversation.id, assistantId, (m) => ({
            ...m,
            role: 'assistant',
            status: 'incomplete',
          }));
        }
      } catch (err) {
        if (controller.signal.aborted) {
          patchAssistant(conversation.id, assistantId, (m) => ({
            ...m,
            role: 'assistant',
            status: 'stopped',
          }));
        } else {
          const sessionExpired = err instanceof ApiError && err.body?.code === 'NOT_FOUND';
          if (sessionExpired) expireSession();
          patchAssistant(conversation.id, assistantId, (m) => ({
            ...m,
            role: 'assistant',
            status: 'error',
            errorMessage: sessionExpired
              ? SESSION_EXPIRED_MESSAGE
              : err instanceof ApiError
                ? err.message
                : err instanceof Error
                  ? err.message
                  : 'Turn failed',
            errorCode: err instanceof ApiError ? err.body?.code : undefined,
            retryText: sessionExpired ? trimmed : undefined,
          }));
        }
      } finally {
        if (abortsRef.current.get(conversation.id) === controller) {
          abortsRef.current.delete(conversation.id);
          updateConversation(conversation.id, (current) => ({ ...current, isStreaming: false }));
        }
        const current = conversationsRef.current[conversation.id];
        const last = current?.messages[current.messages.length - 1];
        const persisted = last?.role === 'assistant' && last.status === 'done';
        if (current?.sessionId && !persisted) retainConversation(current);
      }
      return true;
    },
    [activeCatalogName, createConversation, ensureSession, notify, patchAssistant, updateConversation],
  );

  const value: LakeGenValue = {
    catalogs,
    catalogsError,
    catalogsLoading,
    catalogsRefreshing,
    refreshCatalogs,
    addCatalog,
    removeCatalog,
    activeCatalogName,
    setActiveCatalogName,
    activeCatalog,
    sessions,
    sessionsLoading,
    sessionsLoadingMore,
    sessionsError,
    sessionsHasMore,
    loadMoreSessions,
    selectedSessionId,
    selectSession,
    sessionHistoryLoading,
    sessionHistoryError,
    activeSessionLive,
    messages,
    isStreaming,
    sendError,
    sendMessage,
    stopStreaming,
    newConversation,
  };

  return <LakeGenContext.Provider value={value}>{children}</LakeGenContext.Provider>;
}

export function useLakeGen(): LakeGenValue {
  const context = useContext(LakeGenContext);
  if (!context) throw new Error('useLakeGen must be used within LakeGenProvider');
  return context;
}

