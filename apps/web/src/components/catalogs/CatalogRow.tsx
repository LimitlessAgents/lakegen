import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MoreHorizontalIcon } from 'lucide-react';
import type { CatalogResponse } from '../../api/types';
import { StatusDot } from '../ui/StatusDot';
import { TypeBadge } from '../ui/TypeBadge';
import { IconButton } from '../ui/IconButton';

const MENU_WIDTH = 164;

interface CatalogRowProps {
  catalog: CatalogResponse;
  isActive: boolean;
  removing?: boolean;
  onSetActive: () => void;
  onRemove: () => void;
}

export function CatalogRow({
  catalog,
  isActive,
  removing = false,
  onSetActive,
  onRemove,
}: CatalogRowProps) {
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
    <tr className="border-b border-line-soft transition-colors duration-150 hover:bg-line-soft/40 last:border-0">
      <td className="max-w-[200px] px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
        <span className="truncate font-mono text-[13px] text-ink">{catalog.name}</span>
        {isActive && (
          <span className="shrink-0 rounded border border-line bg-panel px-1 text-[10px] uppercase tracking-wider text-ink-faint">
            active
          </span>
        )}
        </div>
      </td>

      <td className="px-4 py-2.5"><TypeBadge type={catalog.catalog_type} /></td>

      <td className="max-w-[420px] truncate px-4 py-2.5 font-mono text-sm text-ink-muted" title={catalog.warehouse ?? undefined}>
        {catalog.warehouse ?? '—'}
      </td>

      <td className="px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
        <StatusDot state={catalog.connected ? 'connected' : 'unverified'} />
        <span
          title={catalog.connected ? undefined : 'The catalog will be connected when it is first used.'}
          className="text-[13px] text-ink-muted"
        >
          {catalog.connected ? 'Connected' : 'Not verified'}
        </span>
        </div>
      </td>

      <td className="w-10 px-2 py-2.5 text-right">
        <IconButton
          ref={buttonRef}
          onClick={() => {
            if (open) {
              setOpen(false);
              return;
            }
            positionMenu();
            setOpen(true);
          }}
          aria-haspopup="menu"
          aria-expanded={open}
          disabled={removing}
          label={`Actions for ${catalog.name}`}
          className="h-6 w-6 border-0 hover:bg-line"
        >
          <MoreHorizontalIcon className="h-4 w-4" strokeWidth={2} />
        </IconButton>
      </td>

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
              disabled={isActive || removing}
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
              disabled={removing}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-err transition-colors hover:bg-[#FBF0EE] disabled:cursor-wait disabled:opacity-40"
            >
              Remove catalog
            </button>
          </div>,
          document.body,
        )}
    </tr>
  );
}
