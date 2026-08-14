import { useEffect, useRef, useState } from 'react';
import { ChevronDownIcon, PlusIcon } from 'lucide-react';
import { useLakeGen } from '../../state/LakeGenContext';
import { StatusDot } from '../ui/StatusDot';
import { TypeBadge } from '../ui/TypeBadge';

export function AgentHeader() {
  const { catalogs, activeCatalog, setActiveCatalogName, newConversation } = useLakeGen();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-line bg-canvas px-8">
      <h1 className="text-[13px] font-medium text-ink">Agent</h1>
      <span aria-hidden="true" className="text-ink-faint">
        ·
      </span>

      <div className="relative" ref={wrapperRef}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="flex h-7 items-center gap-2 rounded-md border border-transparent px-2 text-[13px] text-ink-muted transition-colors hover:border-line hover:bg-panel"
        >
          <span>Active catalog</span>
          {activeCatalog ? (
            <span className="flex items-center gap-1.5">
              <StatusDot connected={activeCatalog.connected} />
              <span className="font-mono text-ink">{activeCatalog.name}</span>
            </span>
          ) : (
            <span className="text-ink-faint">none</span>
          )}
          <ChevronDownIcon className="h-3.5 w-3.5 text-ink-faint" strokeWidth={2} />
        </button>

        {open && (
          <div
            role="listbox"
            className="absolute left-0 top-[34px] z-20 w-[300px] overflow-hidden rounded-lg border border-line bg-panel py-1 shadow-pop"
          >
            {catalogs.length === 0 && (
              <p className="px-3 py-2 text-[13px] text-ink-faint">No catalogs configured</p>
            )}
            {catalogs.map((catalog) => (
              <button
                key={catalog.name}
                role="option"
                aria-selected={catalog.name === activeCatalog?.name}
                onClick={() => {
                  setActiveCatalogName(catalog.name);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-line-soft ${
                  catalog.name === activeCatalog?.name ? 'bg-line-soft/70' : ''
                }`}
              >
                <StatusDot connected={catalog.connected} />
                <span className="font-mono text-[13px] text-ink">{catalog.name}</span>
                <span className="ml-auto">
                  <TypeBadge type={catalog.catalog_type} />
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={newConversation}
        className="ml-auto flex h-7 items-center gap-1.5 rounded-md px-2 text-[13px] text-ink-muted transition-colors hover:bg-line-soft hover:text-ink"
      >
        <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
        New conversation
      </button>
    </header>
  );
}
