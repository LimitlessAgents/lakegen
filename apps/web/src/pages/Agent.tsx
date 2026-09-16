import { useCallback, useEffect, useRef, useState } from 'react';
import { useLakeGen } from '../state/LakeGenContext';
import { AgentHeader } from '../components/agent/AgentHeader';
import { AgentEmptyState } from '../components/agent/AgentEmptyState';
import { ChatMessage } from '../components/agent/ChatMessage';
import { Composer } from '../components/agent/Composer';

export function Agent() {
  const { activeConversationRestored, messages, isStreaming, sendMessage } = useLakeGen();
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToBottomRef = useRef(true);
  const previousMessageCountRef = useRef(0);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const retryMessage = useCallback((text: string) => {
    void sendMessage(text);
  }, [sendMessage]);

  useEffect(() => {
    document.title = 'Agent · LakeGen';
  }, []);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !pinnedToBottomRef.current) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: messages.length > previousMessageCountRef.current ? 'smooth' : 'auto',
    });
    previousMessageCountRef.current = messages.length;
  }, [isStreaming, messages]);

  function handleScroll() {
    const container = scrollRef.current;
    if (!container) return;
    const pinned = container.scrollHeight - container.scrollTop - container.clientHeight < 48;
    pinnedToBottomRef.current = pinned;
    setShowJumpToLatest(!pinned && isStreaming);
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
        {messages.length === 0 ? (
          <AgentEmptyState />
        ) : (
          <div className="mx-auto max-w-[760px] px-8 pb-10 pt-2">
            {activeConversationRestored && (
              <p className="border-b border-line-soft py-3 text-[12px] leading-[1.5] text-ink-faint">
                Restored from your browser. The agent does not have the earlier messages as context.
              </p>
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
