import { cloneElement, isValidElement, useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react';

interface MenuProps {
  label: string;
  trigger: ReactElement<Record<string, unknown>>;
  children: ReactNode | ((close: () => void) => ReactNode);
  className?: string;
}

export function Menu({ label, trigger, children, className = '' }: MenuProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!isValidElement(trigger)) return null;

  return (
    <div ref={wrapperRef} className="relative">
      {cloneElement(trigger, {
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        onClick: () => setOpen((current) => !current),
      })}
      {open && (
        <div
          role="menu"
          aria-label={label}
          className={`absolute left-0 top-[34px] z-dropdown overflow-hidden rounded-lg border border-line bg-panel py-1 shadow-pop ${className}`}
          onKeyDown={(event) => {
            if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
            const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role^="menuitem"]'));
            const index = items.indexOf(document.activeElement as HTMLElement);
            const next = event.key === 'ArrowDown' ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
            items[next]?.focus();
            event.preventDefault();
          }}
        >
          {typeof children === 'function' ? (children as (close: () => void) => ReactNode)(() => setOpen(false)) : children}
        </div>
      )}
    </div>
  );
}
