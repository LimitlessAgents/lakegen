import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MoreHorizontalIcon } from 'lucide-react';
import type { CatalogResponse } from '../../api/types';
import { StatusDot } from '../ui/StatusDot';
import { TypeBadge } from '../ui/TypeBadge';

const MENU_WIDTH = 164;

interface CatalogRowProps {
  catalog: CatalogResponse;
  isActive: boolean;
  onSetActive: () => void;
  onRemove: () => void;
}

export function CatalogRow({ catalog, isActive, onSetActive, onRemove }: CatalogRowProps) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });

  function positionMenu() {
    const button = buttonRef.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const menuHeight = menuRef.current?.offsetHeight ?? 80;
    const spaceBelow = window.innerHeight - rect.bottom;
    const top =
      spaceBelow < menuHeight + 8 ? Math.max(8, rect.top - menuHeight - 4) : rect.bottom + 4;
    const left = Math.min(
      Math.max(8, rect.right - MENU_WIDTH),
      window.innerWidth - MENU_WIDTH - 8,
    );
    setMenuPos({ top, left });
  }

  useLayoutEffect(() => {
    if (!open) return;
    positionMenu();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div className="grid grid-cols-[200px_64px_1fr_220px_36px] items-center gap-4 border-b border-line-soft px-4 py-2.5 transition-colors duration-150 hover:bg-line-soft/40">
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

      <div className="flex justify-end">
        <button
          ref={buttonRef}
          type="button"
          onClick={() => {
            if (open) {
              setOpen(false);
              return;
            }
            positionMenu();
            setOpen(true);
          }}
          aria-label={`Actions for ${catalog.name}`}
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-6 w-6 items-center justify-center rounded text-ink-faint transition-colors hover:bg-line hover:text-ink"
        >
          <MoreHorizontalIcon className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{ top: menuPos.top, left: menuPos.left, width: MENU_WIDTH }}
            className="fixed z-50 overflow-hidden rounded-lg border border-line bg-panel py-1 shadow-pop"
          >
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onSetActive();
              }}
              disabled={isActive}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-ink transition-colors hover:bg-line-soft disabled:text-ink-faint disabled:hover:bg-transparent"
            >
              Set as active
            </button>
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onRemove();
              }}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-err transition-colors hover:bg-[#FBF0EE]"
            >
              Remove catalog
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}
