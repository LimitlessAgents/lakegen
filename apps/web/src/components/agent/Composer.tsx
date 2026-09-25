import { useEffect, useRef, useState } from 'react';
import { ArrowUpIcon, SquareIcon } from 'lucide-react';
import { useLakeGen } from '../../state/LakeGenContext';
import { IconButton } from '../ui/IconButton';

const MAX_MESSAGE_LENGTH = 10_000;

export function Composer() {
  const {
    catalogs,
    sendMessage,
    sendError,
    isStreaming,
    stopStreaming,
    activeCatalog,
    selectedSessionId,
    activeSessionLive,
    sessionHistoryLoading,
    sessionHistoryError,
  } = useLakeGen();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
        : selectedSessionId && !activeSessionLive
          ? 'This session is history only. Start a new conversation to continue.'
          : catalogs.length === 0
            ? 'Connect a catalog before sending a message.'
            : !activeCatalog
              ? 'Select an active catalog before sending a message.'
              : null;
  const cannotSend = Boolean(unavailableReason) || isStreaming || value.length > MAX_MESSAGE_LENGTH;

  async function submit() {
    if (!value.trim() || cannotSend) return;
    if (await sendMessage(value)) setValue('');
  }

  return (
    <div className="border-t border-line bg-canvas px-8 py-4">
      <div className="mx-auto max-w-[760px]">
        {sendError && (
          <p role="alert" className="mb-2 text-[13px] text-err">
            {sendError}
          </p>
        )}
        <div className="rounded-xl border border-line bg-panel shadow-subtle transition-colors duration-150 focus-within:border-line-strong">
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
            className="lg-scroll block w-full resize-none bg-transparent px-3.5 pb-1 pt-3 text-[14px] leading-[1.55] text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed disabled:text-ink-faint"
          />

          <div className="flex items-center gap-2 px-3 pb-2.5 pt-1">
            <span className="flex items-center gap-1.5 text-[12px] text-ink-faint">
              <span>Catalog</span>
              <span className="font-mono text-ink-muted">
                {activeCatalog ? activeCatalog.name : 'none'}
              </span>
            </span>

            <span className="ml-auto hidden text-[12px] text-ink-faint sm:inline">
              {isStreaming ? 'Wait for the response to finish' : unavailableReason ?? 'Enter to send'}
            </span>

            {isStreaming ? (
              <>
                <span title="Wait for the response to finish">
                  <IconButton
                    disabled
                    label="Send message unavailable while generating"
                    className="bg-line-strong text-white"
                  >
                    <ArrowUpIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
                  </IconButton>
                </span>
                <IconButton
                  onClick={stopStreaming}
                  label="Stop generating"
                >
                  <SquareIcon className="h-3 w-3 fill-current" strokeWidth={0} />
                </IconButton>
              </>
            ) : (
              <IconButton
                onClick={() => void submit()}
                disabled={!value.trim() || Boolean(unavailableReason)}
                title={unavailableReason ?? undefined}
                label="Send message"
                variant="primary"
                className="disabled:bg-line-strong"
              >
                <ArrowUpIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
              </IconButton>
            )}
          </div>
          {value.length >= MAX_MESSAGE_LENGTH * 0.9 && (
            <p className="px-3 pb-2 text-right text-[11px] text-ink-faint">
              {value.length.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
