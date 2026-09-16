import { AlertTriangleIcon, CopyIcon, RotateCwIcon } from 'lucide-react';
import { memo } from 'react';
import type { Message } from '../../api/types';
import { presentError } from '../../api/errors';
import { canCopyText, copyText } from '../../lib/clipboard';
import { useToast } from '../ui/Toast';
import { RichText } from './RichText';

interface ChatMessageProps {
  message: Message;
  onRetry?: (text: string) => void;
}

export const ChatMessage = memo(function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const { notify } = useToast();
  const isUser = message.role === 'user';
  const error = !isUser ? presentError(message.errorCode) : null;
  const statusLabel =
    !isUser && message.status === 'stopped'
      ? 'Stopped'
      : !isUser && message.status === 'incomplete'
        ? message.stopReason === 'max_iterations_exceeded'
          ? 'Stopped after reaching the step limit.'
          : message.stopReason === 'internal_error'
            ? 'The response could not be completed.'
            : 'The connection closed before the response finished.'
        : null;

  return (
    <article className="group animate-fade-up border-b border-line-soft py-6 last:border-0">
      <div className="mb-2.5 text-2xs font-medium uppercase tracking-wider text-ink-faint">
        <div className="flex items-center">
          {isUser ? 'You' : 'LakeGen'}
          {!isUser && canCopyText() && (
            <button
              type="button"
              className="ml-auto flex h-6 w-6 items-center justify-center rounded text-ink-faint opacity-0 transition-opacity hover:bg-line-soft hover:text-ink focus:opacity-100 group-hover:opacity-100"
              aria-label="Copy response"
              onClick={() => {
                void copyText(message.text).then((copied) => {
                  notify({
                    tone: copied ? 'success' : 'error',
                    message: copied ? 'Response copied.' : 'Could not copy the response.',
                  });
                });
              }}
            >
              <CopyIcon className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>

      {isUser ? (
        <p className="text-[14px] leading-[1.6] text-ink">{message.text}</p>
      ) : (
        <div className="space-y-3">
          {message.status === 'error' && message.errorMessage && (
            <div className="flex gap-2.5 rounded-lg border border-err-border bg-err-soft px-3 py-2.5">
              <AlertTriangleIcon className="mt-[2px] h-3.5 w-3.5 shrink-0 text-err" strokeWidth={2} />
              <div className="text-err-strong">
                <p className="text-[13px] font-medium leading-[1.6]">{error?.title}</p>
                <p className="whitespace-pre-wrap text-[13px] leading-[1.6]">{message.errorMessage}</p>
                <p className="mt-1 text-[12px] leading-[1.5] text-ink-muted">{error?.hint}</p>
              </div>
            </div>
          )}

          {message.text && <RichText text={message.text} />}

          {message.status === 'streaming' && (
            <span
              aria-label="Generating response"
              className="inline-block h-[14px] w-[2px] translate-y-[2px] animate-pulse bg-accent"
            />
          )}

          {statusLabel && <p className="text-[12px] text-ink-faint">{statusLabel}</p>}

          {message.status === 'error' && message.retryText && onRetry && (
            <button
              type="button"
              onClick={() => onRetry(message.retryText!)}
              className="inline-flex items-center gap-1.5 text-[12px] font-medium text-accent hover:text-accent-hover"
            >
              <RotateCwIcon className="h-3 w-3" strokeWidth={2} />
              Retry request
            </button>
          )}

          {message.status !== 'streaming' &&
            message.status !== 'error' &&
            !message.text &&
            !statusLabel && <p className="text-[13px] text-ink-faint">No response returned.</p>}
        </div>
      )}
    </article>
  );
});
