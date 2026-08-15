import { useEffect, useRef, useState } from 'react';
import { MoreHorizontalIcon } from 'lucide-react';
import type { CatalogResponse } from '../../api/types';
import { StatusDot } from '../ui/StatusDot';
import { TypeBadge } from '../ui/TypeBadge';

interface CatalogRowProps {
  catalog: CatalogResponse;
  isActive: boolean;
  onSetActive: () => void;
  onRemove: () => void;
}

export function CatalogRow({ catalog, isActive, onSetActive, onRemove }: CatalogRowProps) {
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
    <div className="group grid grid-cols-[200px_64px_1fr_220px_36px] items-center gap-4 border-b border-line-soft px-4 py-2.5 transition-colors duration-150 hover:bg-line-soft/40">
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate font-mono text-[13px] text-ink">{catalog.name}</span>
        {isActive && (
          <span className="shrink-0 rounded border border-line bg-panel px-1 text-[10px] uppercase tracking-wider text-ink-faint">
            active
          </span>
        )}
      </div>

      <TypeBadge type={catalog.catalog_type} />

      <span className="truncate font-mono text-[12.5px] text-ink-muted">
        {catalog.warehouse ?? '—'}
      </span>

      <div className="flex min-w-0 items-center gap-2">
        <StatusDot connected={catalog.connected} />
        <span className={`text-[13px] ${catalog.connected ? 'text-ink' : 'text-err'}`}>
          {catalog.connected ? 'Connected' : 'Unreachable'}
        </span>
      </div>

      <div className="relative flex justify-end" ref={wrapperRef}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={`Actions for ${catalog.name}`}
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-6 w-6 items-center justify-center rounded text-ink-faint opacity-0 transition-all duration-150 hover:bg-line hover:text-ink focus-visible:opacity-100 group-hover:opacity-100"
        >
          <MoreHorizontalIcon className="h-4 w-4" strokeWidth={2} />
        </button>

        {open && (
          <div
            role="menu"
            className="absolute right-0 top-7 z-20 w-[164px] overflow-hidden rounded-lg border border-line bg-panel py-1 shadow-pop"
          >
            <button
              role="menuitem"
              onClick={() => {
                onSetActive();
                setOpen(false);
              }}
              disabled={isActive}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-ink transition-colors hover:bg-line-soft disabled:text-ink-faint disabled:hover:bg-transparent"
            >
              Set as active
            </button>
            <button
              role="menuitem"
              onClick={() => {
                onRemove();
                setOpen(false);
              }}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-err transition-colors hover:bg-[#FBF0EE]"
            >
              Remove catalog
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
