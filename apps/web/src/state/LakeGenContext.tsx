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
} from '../api/client';
import { runTurn } from '../api/sse';
import { readLocal, removeLocal, writeLocal } from '../lib/storage';
import { useToast } from '../components/ui/Toast';
import type {
  CatalogCreateRequest,
  CatalogResponse,
  Message,
} from '../api/types';

const ACTIVE_CATALOG_KEY = 'lakegen.activeCatalog';
const CONVERSATIONS_KEY = 'lakegen.conversations';
const ACTIVE_CONVERSATION_KEY = 'lakegen.activeConversation';
const MAX_PERSISTED_CONVERSATIONS = 20;
const MAX_PERSISTED_CONVERSATION_BYTES = 1_000_000;
const EMPTY_MESSAGES: Message[] = [];
let messageSequence = 0;

export interface Conversation {
  id: string;
  sessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  updatedAt: number;
  restored: boolean;
}

interface LakeGenValue {
  catalogs: CatalogResponse[];
  catalogsError: string | null;
  catalogsLoading: boolean;
  catalogsRefreshing: boolean;
  refreshCatalogs: () => Promise<void>;
  addCatalog: (body: CatalogCreateRequest, signal?: AbortSignal) => Promise<void>;
  removeCatalog: (name: string) => Promise<void>;
  activeCatalogName: string | null;
  setActiveCatalogName: (name: string) => void;
  activeCatalog: CatalogResponse | null;
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversationRestored: boolean;
  selectConversation: (conversationId: string) => void;
  messages: Message[];
  isStreaming: boolean;
  sendError: string | null;
  sendMessage: (text: string) => Promise<boolean>;
  stopStreaming: () => void;
  newConversation: () => void;
}

const LakeGenContext = createContext<LakeGenValue | null>(null);

function uid(prefix: string): string {
  messageSequence += 1;
  return `${prefix}_${messageSequence}`;
}

function messageIsValid(value: unknown): value is Message {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<Message>;
  return (
    typeof message.id === 'string' &&
    typeof message.text === 'string' &&
    typeof message.createdAt === 'number' &&
    (message.role === 'user' || message.role === 'assistant')
  );
}

function loadConversations(): Record<string, Conversation> {
  try {
    const stored = JSON.parse(readLocal(CONVERSATIONS_KEY) ?? '[]') as unknown;
    if (!Array.isArray(stored)) return {};
    return Object.fromEntries(
      stored
        .filter(
          (value): value is Pick<Conversation, 'id' | 'messages' | 'updatedAt'> =>
            Boolean(value) &&
            typeof value === 'object' &&
            typeof (value as Conversation).id === 'string' &&
            Array.isArray((value as Conversation).messages) &&
            typeof (value as Conversation).updatedAt === 'number',
        )
        .slice(0, MAX_PERSISTED_CONVERSATIONS)
        .map((value) => [
          value.id,
          {
            ...value,
            sessionId: null,
            isStreaming: false,
            restored: true,
            messages: value.messages
              .filter(messageIsValid)
              .map((message) =>
                message.role === 'assistant' && message.status === 'streaming'
                  ? { ...message, status: 'incomplete' as const }
                  : message,
              ),
          },
        ]),
    );
  } catch {
    return {};
  }
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
  const [conversations, setConversations] = useState<Record<string, Conversation>>(loadConversations);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    const loaded = loadConversations();
    const saved = readLocal(ACTIVE_CONVERSATION_KEY);
    if (saved && loaded[saved]) return saved;
    return Object.values(loaded).sort((a, b) => b.updatedAt - a.updatedAt)[0]?.id ?? null;
  });
  const [sendError, setSendError] = useState<string | null>(null);
  const catalogsRef = useRef<CatalogResponse[]>([]);
  const hasLoadedCatalogsRef = useRef(false);
  const activeCatalogNameRef = useRef<string | null>(activeCatalogName);
  const conversationsRef = useRef(conversations);
  const activeConversationIdRef = useRef(activeConversationId);
  const pendingSessionRef = useRef<Map<string, Promise<string>>>(new Map());
  const abortsRef = useRef(new Map<string, AbortController>());

  const activeConversation = activeConversationId ? conversations[activeConversationId] : undefined;
  const messages = activeConversation?.messages ?? EMPTY_MESSAGES;
  const isStreaming = activeConversation?.isStreaming ?? false;
  const activeConversationRestored = activeConversation?.restored ?? false;

  const updateConversations = useCallback(
    (update: (current: Record<string, Conversation>) => Record<string, Conversation>) => {
      const next = update(conversationsRef.current);
      conversationsRef.current = next;
      setConversations(next);
    },
    [],
  );

  const selectConversation = useCallback((conversationId: string) => {
    if (!conversationsRef.current[conversationId]) return;
    activeConversationIdRef.current = conversationId;
    setActiveConversationId(conversationId);
  }, []);

  const createConversation = useCallback((): Conversation => {
    const conversation: Conversation = {
      id: uid('conversation'),
      sessionId: null,
      messages: [],
      isStreaming: false,
      updatedAt: Date.now(),
      restored: false,
    };
    updateConversations((current) => ({ ...current, [conversation.id]: conversation }));
    activeConversationIdRef.current = conversation.id;
    setActiveConversationId(conversation.id);
    return conversation;
  }, [updateConversations]);

  useEffect(() => {
    const persisted = Object.values(conversations)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_PERSISTED_CONVERSATIONS)
      .map(({ id, messages, updatedAt }) => ({
        id,
        messages,
        updatedAt,
      }));
    const limited: typeof persisted = [];
    let size = 2;
    for (const conversation of persisted) {
      const serialized = JSON.stringify(conversation);
      if (size + serialized.length > MAX_PERSISTED_CONVERSATION_BYTES) break;
      limited.push(conversation);
      size += serialized.length + 1;
    }
    writeLocal(CONVERSATIONS_KEY, JSON.stringify(limited));
  }, [conversations]);

  useEffect(() => {
    if (activeConversationId) writeLocal(ACTIVE_CONVERSATION_KEY, activeConversationId);
    else removeLocal(ACTIVE_CONVERSATION_KEY);
  }, [activeConversationId]);

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
            [conversationId]: { ...currentConversation, sessionId: id },
          };
        });
        return id;
      })
      .finally(() => {
        pendingSessionRef.current.delete(conversationId);
      });

    pendingSessionRef.current.set(conversationId, promise);
    return promise;
  }, [updateConversations]);

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

  const refreshCatalogs = useCallback(async () => {
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load catalogs';
      setCatalogsError(message);
      if (!isInitialLoad) notify({ tone: 'error', message });
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
    const current = activeConversationIdRef.current
      ? conversationsRef.current[activeConversationIdRef.current]
      : undefined;
    if (current && current.messages.length === 0) return;
    createConversation();
  }, [createConversation]);

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
              patchAssistant(conversation.id, assistantId, (m) => ({
                ...m,
                role: 'assistant',
                status: event.data.stop_reason === 'completed' ? 'done' : 'incomplete',
                stopReason: event.data.stop_reason,
              }));
            } else if (event.type === 'error') {
              streamError = true;
              patchAssistant(conversation.id, assistantId, (m) => ({
                ...m,
                role: 'assistant',
                status: 'error',
                errorMessage: event.data.message,
                errorCode: event.data.code,
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
          const message =
            sessionExpired
              ? 'This agent session expired. Retry to continue in a new session.'
              : err instanceof ApiError
                ? err.message
                : err instanceof Error
                  ? err.message
                  : 'Turn failed';
          if (sessionExpired) {
            updateConversation(conversation.id, (current) => ({ ...current, sessionId: null }));
            notify({ tone: 'info', message: 'The agent session expired. Retry the request to continue.' });
          }
          patchAssistant(conversation.id, assistantId, (m) => ({
            ...m,
            role: 'assistant',
            status: 'error',
            errorMessage: message,
            errorCode: err instanceof ApiError ? err.body?.code : undefined,
            retryText: sessionExpired ? trimmed : undefined,
          }));
        }
      } finally {
        if (abortsRef.current.get(conversation.id) === controller) {
          abortsRef.current.delete(conversation.id);
          updateConversation(conversation.id, (current) => ({ ...current, isStreaming: false }));
        }
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
    conversations: Object.values(conversations).sort((a, b) => b.updatedAt - a.updatedAt),
    activeConversationId,
    activeConversationRestored,
    selectConversation,
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

