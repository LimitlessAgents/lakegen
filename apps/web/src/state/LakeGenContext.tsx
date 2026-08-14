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
  deleteSession,
  listCatalogs,
} from '../api/client';
import { runTurn } from '../api/sse';
import type {
  CatalogCreateRequest,
  CatalogResponse,
  Message,
} from '../api/types';

const ACTIVE_CATALOG_KEY = 'lakegen.activeCatalog';

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
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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
    abortRef.current?.abort();
  }, []);

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    const sessionId = sessionIdRef.current;
    sessionIdRef.current = null;
    setMessages([]);
    setIsStreaming(false);
    if (sessionId) {
      void deleteSession(sessionId).catch(() => undefined);
    }
  }, []);

  const patchAssistant = useCallback((id: string, patch: (message: Message) => Message) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? patch(m) : m)));
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const assistantId = uid('msg');
      setMessages((prev) => [
        ...prev,
        { id: uid('msg'), role: 'user', text: trimmed, createdAt: Date.now() },
        {
          id: assistantId,
          role: 'assistant',
          text: '',
          streaming: true,
          createdAt: Date.now(),
        },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        if (!sessionIdRef.current) {
          sessionIdRef.current = (await createSession()).id;
        }
        await runTurn(
          sessionIdRef.current,
          {
            text: trimmed,
            catalog_name: activeCatalogName,
          },
          (event) => {
            if (event.type === 'text_delta') {
              patchAssistant(assistantId, (m) => ({
                ...m,
                text: m.text + event.data.text,
              }));
            } else if (event.type === 'turn_done') {
              patchAssistant(assistantId, (m) => ({
                ...m,
                text: event.data.final_message || m.text,
                streaming: false,
              }));
            } else if (event.type === 'error') {
              patchAssistant(assistantId, (m) => ({
                ...m,
                streaming: false,
                error: event.data.message,
              }));
            }
          },
          controller.signal,
        );
        patchAssistant(assistantId, (m) => ({ ...m, streaming: false }));
      } catch (err) {
        if (controller.signal.aborted) {
          patchAssistant(assistantId, (m) => ({ ...m, streaming: false }));
        } else {
          const message =
            err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Turn failed';
          patchAssistant(assistantId, (m) => ({
            ...m,
            streaming: false,
            error: message,
          }));
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [activeCatalogName, isStreaming, patchAssistant],
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
