import { useEffect, useRef, useState } from 'react';
import { ArrowUpIcon, SquareIcon } from 'lucide-react';
import { useLakeGen } from '../../state/LakeGenContext';

const MAX_MESSAGE_LENGTH = 10_000;

interface ComposerProps {
  /** `landing` drops the docked page padding so the card can sit in a centered hero. */
  variant?: 'docked' | 'landing';
}

export function Composer({ variant = 'docked' }: ComposerProps) {
  const {
    catalogs,
    sendMessage,
    sendError,
    isStreaming,
    stopStreaming,
    activeCatalog,
    selectedSessionId,
    sessionHistoryLoading,
    sessionHistoryError,
  } = useLakeGen();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autofocusedRef = useRef(false);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [value]);

  const unavailableReason =
    sessionHistoryLoading
      ? 'Wait for session history to load.'
      : selectedSessionId && sessionHistoryError
        ? 'Session history is unavailable. Retry it or start a new conversation.'
        : catalogs.length === 0
            ? 'Connect a catalog before sending a message.'
            : !activeCatalog
              ? 'Select an active catalog before sending a message.'
              : null;
  const cannotSend = Boolean(unavailableReason) || isStreaming || value.length > MAX_MESSAGE_LENGTH;

  useEffect(() => {
    if (autofocusedRef.current || unavailableReason) return;
    autofocusedRef.current = true;
    textareaRef.current?.focus();
  }, [unavailableReason]);

  function submit() {
    if (!value.trim() || cannotSend) return;
    const text = value;
    setValue('');
    void sendMessage(text);
  }

  return (
    <div className={variant === 'landing' ? undefined : 'px-4 pb-4 pt-2 sm:px-8 sm:pb-6'}>
      <div className="mx-auto max-w-[760px]">
        {sendError && (
          <p role="alert" className="mb-2 text-[13px] text-err">
            {sendError}
          </p>
        )}

        <div className="rounded-xl border border-line-strong bg-panel shadow-raised transition-[border-color,box-shadow] duration-150 focus-within:border-accent-hover focus-within:ring-[3px] focus-within:ring-accent/15">
          <label htmlFor="composer" className="sr-only">
            Message LakeGen
          </label>
          <textarea
            id="composer"
            ref={textareaRef}
            rows={1}
            value={value}
            maxLength={MAX_MESSAGE_LENGTH}
            disabled={Boolean(unavailableReason)}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                void submit();
              }
            }}
            placeholder={unavailableReason ?? 'Ask about namespaces, tables, snapshots, or files…'}
            className="lg-scroll block w-full resize-none bg-transparent px-4 pb-1 pt-3 text-[14px] leading-[1.55] text-ink placeholder:text-ink-faint focus-visible:outline-none disabled:cursor-not-allowed disabled:text-ink-faint"
          />

          <div className="flex items-center gap-3 pb-2 pl-4 pr-2 pt-1">
            <span className="min-w-0 truncate text-2xs tabular-nums text-ink-faint">
              {value.length >= MAX_MESSAGE_LENGTH * 0.9
                ? `${value.length.toLocaleString()} / ${MAX_MESSAGE_LENGTH.toLocaleString()}`
                : isStreaming
                  ? 'Generating response…'
                  : ''}
            </span>

            {!isStreaming && (
              <div className="ml-auto flex items-center gap-3">
                <span className="hidden items-center gap-1.5 text-2xs text-ink-faint sm:flex">
                  Send
                  <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-line bg-canvas px-1 font-mono text-[10px] leading-none text-ink-muted">
                    ⏎
                  </kbd>
                </span>

                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={!value.trim() || Boolean(unavailableReason)}
                  title={unavailableReason ?? undefined}
                  aria-label="Send message"
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors duration-150 enabled:hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-sunken disabled:text-ink-faint"
                >
                  <ArrowUpIcon className="h-4 w-4" strokeWidth={2.5} />
                </button>
              </div>
            )}

            {isStreaming && (
              <button
                type="button"
                onClick={stopStreaming}
                aria-label="Stop generating"
                title="Stop generating"
                className="ml-auto inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors duration-150 hover:bg-accent-hover"
              >
                <SquareIcon className="h-3.5 w-3.5 fill-current" strokeWidth={0} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
