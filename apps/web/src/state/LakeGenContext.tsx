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
import type {
  CatalogCreateRequest,
  CatalogResponse,
  Message,
} from '../api/types';

const ACTIVE_CATALOG_KEY = 'lakegen.activeCatalog';
const EMPTY_MESSAGES: Message[] = [];

interface Conversation {
  sessionId: string;
  messages: Message[];
  isStreaming: boolean;
}

interface LakeGenValue {
  catalogs: CatalogResponse[];
  catalogsError: string | null;
  catalogsLoading: boolean;
  refreshCatalogs: () => Promise<void>;
  addCatalog: (body: CatalogCreateRequest) => Promise<void>;
  removeCatalog: (name: string) => Promise<void>;
  activeCatalogName: string | null;
  setActiveCatalogName: (name: string) => void;
  activeCatalog: CatalogResponse | null;
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (text: string) => void;
  stopStreaming: () => void;
  newConversation: () => void;
}

const LakeGenContext = createContext<LakeGenValue | null>(null);

function uid(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`;
}

export function LakeGenProvider({ children }: { children: React.ReactNode }) {
  const [catalogs, setCatalogs] = useState<CatalogResponse[]>([]);
  const [catalogsError, setCatalogsError] = useState<string | null>(null);
  const [catalogsLoading, setCatalogsLoading] = useState(true);
  const [activeCatalogName, setActiveCatalogNameState] = useState<string | null>(
    () => localStorage.getItem(ACTIVE_CATALOG_KEY),
  );
  const [conversations, setConversations] = useState<Record<string, Conversation>>({});
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const sessionGenerationRef = useRef(0);
  const pendingSessionRef = useRef<{
    generation: number;
    promise: Promise<string>;
  } | null>(null);
  const abortsRef = useRef(new Map<string, AbortController>());

  const activeConversation = activeSessionId ? conversations[activeSessionId] : undefined;
  const messages = activeConversation?.messages ?? EMPTY_MESSAGES;
  const isStreaming = activeConversation?.isStreaming ?? false;

  const activeCatalog = useMemo(
    () => catalogs.find((c) => c.name === activeCatalogName) ?? null,
    [catalogs, activeCatalogName],
  );

  const setActiveCatalogName = useCallback((name: string) => {
    setActiveCatalogNameState(name);
    localStorage.setItem(ACTIVE_CATALOG_KEY, name);
  }, []);

  const refreshCatalogs = useCallback(async () => {
    setCatalogsLoading(true);
    try {
      const next = await listCatalogs();
      setCatalogs(next);
      setCatalogsError(null);
      setActiveCatalogNameState((current) => {
        if (current && next.some((c) => c.name === current)) return current;
        const fallback = next.find((c) => c.connected)?.name ?? next[0]?.name ?? null;
        if (fallback) localStorage.setItem(ACTIVE_CATALOG_KEY, fallback);
        else localStorage.removeItem(ACTIVE_CATALOG_KEY);
        return fallback;
      });
    } catch (err) {
      setCatalogsError(err instanceof Error ? err.message : 'Failed to load catalogs');
    } finally {
      setCatalogsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshCatalogs();
  }, [refreshCatalogs]);

  const ensureSession = useCallback((generation: number): Promise<string> => {
    const activeSessionId = activeSessionIdRef.current;
    if (sessionGenerationRef.current === generation && activeSessionId) {
      return Promise.resolve(activeSessionId);
    }

    const pending = pendingSessionRef.current;
    if (pending?.generation === generation) return pending.promise;

    const promise = createSession()
      .then(({ id }) => {
        setConversations((prev) => ({
          ...prev,
          [id]: {
            sessionId: id,
            messages: [],
            isStreaming: false,
          },
        }));
        if (sessionGenerationRef.current === generation) {
          activeSessionIdRef.current = id;
          setActiveSessionId(id);
        }
        return id;
      })
      .finally(() => {
        if (pendingSessionRef.current?.promise === promise) {
          pendingSessionRef.current = null;
        }
      });

    pendingSessionRef.current = { generation, promise };
    return promise;
  }, []);

  useEffect(() => {
    void ensureSession(sessionGenerationRef.current).catch(() => undefined);
  }, [ensureSession]);

  const addCatalog = useCallback(async (body: CatalogCreateRequest) => {
    const created = await addCatalogRequest(body);
    setCatalogs((prev) => [...prev.filter((c) => c.name !== created.name), created]);
    setActiveCatalogNameState((prev) => {
      if (prev) return prev;
      localStorage.setItem(ACTIVE_CATALOG_KEY, created.name);
      return created.name;
    });
  }, []);

  const removeCatalog = useCallback(async (name: string) => {
    await deleteCatalogRequest(name);
    setCatalogs((prev) => {
      const next = prev.filter((c) => c.name !== name);
      setActiveCatalogNameState((current) => {
        if (current !== name) return current;
        const fallback = next.find((c) => c.connected)?.name ?? next[0]?.name ?? null;
        if (fallback) localStorage.setItem(ACTIVE_CATALOG_KEY, fallback);
        else localStorage.removeItem(ACTIVE_CATALOG_KEY);
        return fallback;
      });
      return next;
    });
  }, []);

  const stopStreaming = useCallback(() => {
    const sessionId = activeSessionIdRef.current;
    if (sessionId) abortsRef.current.get(sessionId)?.abort();
  }, []);

  const newConversation = useCallback(() => {
    const generation = sessionGenerationRef.current + 1;
    sessionGenerationRef.current = generation;
    activeSessionIdRef.current = null;
    setActiveSessionId(null);
    void ensureSession(generation).catch(() => undefined);
  }, [ensureSession]);

  const patchAssistant = useCallback(
    (sessionId: string, id: string, patch: (message: Message) => Message) => {
      setConversations((prev) => {
        const conversation = prev[sessionId];
        if (!conversation) return prev;
        return {
          ...prev,
          [sessionId]: {
            ...conversation,
            messages: conversation.messages.map((message) =>
              message.id === id ? patch(message) : message,
            ),
          },
        };
      });
    },
    [],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const generation = sessionGenerationRef.current;
      let sessionId: string;
      try {
        sessionId = await ensureSession(generation);
      } catch {
        return;
      }
      if (
        sessionGenerationRef.current !== generation ||
        activeSessionIdRef.current !== sessionId ||
        abortsRef.current.has(sessionId)
      ) {
        return;
      }

      const assistantId = uid('msg');
      const controller = new AbortController();
      abortsRef.current.set(sessionId, controller);
      setConversations((prev) => {
        const conversation = prev[sessionId];
        if (!conversation) return prev;
        return {
          ...prev,
          [sessionId]: {
            ...conversation,
            isStreaming: true,
            messages: [
              ...conversation.messages,
              { id: uid('msg'), role: 'user', text: trimmed, createdAt: Date.now() },
              {
                id: assistantId,
                role: 'assistant',
                text: '',
                streaming: true,
                createdAt: Date.now(),
              },
            ],
          },
        };
      });

      try {
        await runTurn(
          sessionId,
          {
            text: trimmed,
            catalog_name: activeCatalogName,
          },
          (event) => {
            if (event.type === 'text_delta') {
              patchAssistant(sessionId, assistantId, (m) => ({
                ...m,
                text: m.text + event.data.text,
              }));
            } else if (event.type === 'turn_done') {
              patchAssistant(sessionId, assistantId, (m) => ({
                ...m,
                text: event.data.final_message || m.text,
                streaming: false,
              }));
            } else if (event.type === 'error') {
              patchAssistant(sessionId, assistantId, (m) => ({
                ...m,
                streaming: false,
                error: event.data.message,
              }));
            }
          },
          controller.signal,
        );
        patchAssistant(sessionId, assistantId, (m) => ({ ...m, streaming: false }));
      } catch (err) {
        if (controller.signal.aborted) {
          patchAssistant(sessionId, assistantId, (m) => ({ ...m, streaming: false }));
        } else {
          const message =
            err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Turn failed';
          patchAssistant(sessionId, assistantId, (m) => ({
            ...m,
            streaming: false,
            error: message,
          }));
        }
      } finally {
        if (abortsRef.current.get(sessionId) === controller) {
          abortsRef.current.delete(sessionId);
          setConversations((prev) => {
            const conversation = prev[sessionId];
            if (!conversation) return prev;
            return {
              ...prev,
              [sessionId]: {
                ...conversation,
                isStreaming: false,
              },
            };
          });
        }
      }
    },
    [activeCatalogName, ensureSession, patchAssistant],
  );

  const value: LakeGenValue = {
    catalogs,
    catalogsError,
    catalogsLoading,
    refreshCatalogs,
    addCatalog,
    removeCatalog,
    activeCatalogName,
    setActiveCatalogName,
    activeCatalog,
    messages,
    isStreaming,
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
