import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLakeGen } from '../state/LakeGenContext';
import { AgentHeader } from '../components/agent/AgentHeader';
import { AgentEmptyState } from '../components/agent/AgentEmptyState';
import { ChatMessage } from '../components/agent/ChatMessage';
import { Composer } from '../components/agent/Composer';

export function Agent() {
  const {
    messages,
    isStreaming,
    sendMessage,
    selectedSessionId,
    sessionHistoryLoading,
    sessionHistoryLoadingMore,
    sessionHistoryHasMore,
    sessionHistoryError,
    loadMoreSessionHistory,
  } = useLakeGen();
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToBottomRef = useRef(true);
  const previousMessageCountRef = useRef(0);
  const historyScrollAnchorRef = useRef<{ sessionId: string; height: number } | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const retryMessage = useCallback((text: string) => {
    void sendMessage(text);
  }, [sendMessage]);

  useEffect(() => {
    document.title = 'Agent · LakeGen';
  }, []);

  useEffect(() => {
    historyScrollAnchorRef.current = null;
    pinnedToBottomRef.current = true;
    previousMessageCountRef.current = 0;
  }, [selectedSessionId]);

  useLayoutEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const anchor = historyScrollAnchorRef.current;
    if (anchor !== null && !sessionHistoryLoadingMore) {
      if (anchor.sessionId === selectedSessionId) {
        const delta = container.scrollHeight - anchor.height;
        if (delta > 0) container.scrollTop += delta;
      }
      historyScrollAnchorRef.current = null;
      previousMessageCountRef.current = messages.length;
      return;
    }

    if (pinnedToBottomRef.current) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: messages.length > previousMessageCountRef.current ? 'smooth' : 'auto',
      });
    }
    previousMessageCountRef.current = messages.length;
  }, [isStreaming, messages, selectedSessionId, sessionHistoryLoadingMore]);

  function handleScroll() {
    const container = scrollRef.current;
    if (!container) return;
    const pinned = container.scrollHeight - container.scrollTop - container.clientHeight < 48;
    pinnedToBottomRef.current = pinned;
    setShowJumpToLatest(!pinned && isStreaming);
    if (
      container.scrollTop < 80
      && sessionHistoryHasMore
      && !sessionHistoryLoading
      && !sessionHistoryLoadingMore
    ) {
      if (selectedSessionId) {
        historyScrollAnchorRef.current = { sessionId: selectedSessionId, height: container.scrollHeight };
      }
      void loadMoreSessionHistory();
    }
  }

  return (
    <main className="flex h-full min-w-0 flex-1 flex-col bg-canvas">
      <AgentHeader />

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        aria-live="polite"
        aria-busy={isStreaming}
        className="lg-scroll relative flex-1 overflow-y-auto"
      >
        {sessionHistoryLoading ? (
          <div className="mx-auto max-w-[760px] px-8 pt-[18vh] text-[14px] text-ink-muted">
            Loading session history…
          </div>
        ) : sessionHistoryError ? (
          <div role="alert" className="mx-auto max-w-[760px] px-8 pt-[18vh] text-[14px] text-err">
            {sessionHistoryError}
          </div>
        ) : selectedSessionId && messages.length === 0 ? (
          <div className="mx-auto max-w-[760px] px-8 pt-[18vh] text-[14px] text-ink-muted">
            This session has no messages.
          </div>
        ) : messages.length === 0 ? (
          <AgentEmptyState />
        ) : (
          <div className="mx-auto max-w-[760px] px-8 pb-10 pt-2">
            {sessionHistoryLoadingMore && (
              <p className="py-2 text-center text-[13px] text-ink-muted">Loading older messages…</p>
            )}
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} onRetry={retryMessage} />
            ))}
          </div>
        )}
        {showJumpToLatest && (
          <button
            type="button"
            onClick={() => {
              const container = scrollRef.current;
              if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
              pinnedToBottomRef.current = true;
              setShowJumpToLatest(false);
            }}
            className="sticky bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-line bg-panel px-3 py-1.5 text-[12px] font-medium text-ink shadow-subtle hover:bg-line-soft"
          >
            Jump to latest
          </button>
        )}
      </div>

      <Composer />
    </main>
  );
}
