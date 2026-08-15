import { AlertTriangleIcon } from 'lucide-react';
import type { Message } from '../../api/types';
import { RichText } from './RichText';

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <article className="animate-fade-up border-b border-line-soft py-6 last:border-0">
      <div className="mb-2.5 text-2xs font-medium uppercase tracking-wider text-ink-faint">
        {isUser ? 'You' : 'LakeGen'}
      </div>

      {isUser ? (
        <p className="text-[14px] leading-[1.6] text-ink">{message.text}</p>
      ) : (
        <div className="space-y-3">
          {message.error && (
            <div className="flex gap-2.5 rounded-lg border border-[#EBD5D0] bg-[#FCF6F5] px-3 py-2.5">
              <AlertTriangleIcon className="mt-[2px] h-3.5 w-3.5 shrink-0 text-err" strokeWidth={2} />
              <div className="text-[13px] leading-[1.6] text-[#7C3323]">
                <RichText text={message.error} />
              </div>
            </div>
          )}

          {message.text && <RichText text={message.text} />}

          {message.streaming && !message.error && (
            <span
              aria-label="Generating response"
              className="inline-block h-[14px] w-[2px] translate-y-[2px] animate-pulse bg-accent"
            />
          )}
        </div>
      )}
    </article>
  );
}
