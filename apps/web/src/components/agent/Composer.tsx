import { useEffect, useRef, useState } from 'react';
import { ArrowUpIcon, SquareIcon } from 'lucide-react';
import { useLakeGen } from '../../state/LakeGenContext';

export function Composer() {
  const { sendMessage, isStreaming, stopStreaming, activeCatalog } = useLakeGen();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [value]);

  function submit() {
    if (!value.trim() || isStreaming) return;
    sendMessage(value);
    setValue('');
  }

  return (
    <div className="border-t border-line bg-canvas px-8 py-4">
      <div className="mx-auto max-w-[760px]">
        <div className="rounded-xl border border-line bg-panel shadow-subtle transition-colors duration-150 focus-within:border-line-strong">
          <label htmlFor="composer" className="sr-only">
            Message LakeGen
          </label>
          <textarea
            id="composer"
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="Ask about namespaces, tables, snapshots, or files…"
            className="lg-scroll block w-full resize-none bg-transparent px-3.5 pb-1 pt-3 text-[14px] leading-[1.55] text-ink outline-none placeholder:text-ink-faint"
          />

          <div className="flex items-center gap-2 px-3 pb-2.5 pt-1">
            <span className="flex items-center gap-1.5 text-[12px] text-ink-faint">
              <span>Catalog</span>
              <span className="font-mono text-ink-muted">
                {activeCatalog ? activeCatalog.name : 'none'}
              </span>
            </span>

            <span className="ml-auto hidden text-[12px] text-ink-faint sm:inline">Enter to send</span>

            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="flex h-7 w-7 items-center justify-center rounded-md border border-line text-ink-muted transition-colors hover:bg-line-soft"
                aria-label="Stop generating"
              >
                <SquareIcon className="h-3 w-3 fill-current" strokeWidth={0} />
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!value.trim()}
                className="flex h-7 w-7 items-center justify-center rounded-md bg-ink text-white transition-colors hover:bg-black disabled:bg-line-strong"
                aria-label="Send message"
              >
                <ArrowUpIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
