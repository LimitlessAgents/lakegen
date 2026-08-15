import { useEffect, useRef } from 'react';
import { useLakeGen } from '../state/LakeGenContext';
import { AgentHeader } from '../components/agent/AgentHeader';
import { AgentEmptyState } from '../components/agent/AgentEmptyState';
import { ChatMessage } from '../components/agent/ChatMessage';
import { Composer } from '../components/agent/Composer';

export function Agent() {
  const { messages } = useLakeGen();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  return (
    <main className="flex h-full min-w-0 flex-1 flex-col bg-canvas">
      <AgentHeader />

      <div className="lg-scroll flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <AgentEmptyState />
        ) : (
          <div className="mx-auto max-w-[760px] px-8 pb-10 pt-2">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <Composer />
    </main>
  );
}
