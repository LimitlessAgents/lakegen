import { NavLink } from 'react-router-dom';
import { DatabaseIcon, MessagesSquareIcon } from 'lucide-react';
import { useLakeGen } from '../state/LakeGenContext';
import { StatusDot } from './ui/StatusDot';

const items = [
  { to: '/agent', label: 'Agent', icon: MessagesSquareIcon },
  { to: '/catalogs', label: 'Catalogs', icon: DatabaseIcon },
];

export function Sidebar() {
  const { activeCatalog, catalogs } = useLakeGen();

  return (
    <aside className="flex w-[212px] shrink-0 flex-col border-r border-line bg-canvas">
      <div className="flex h-[52px] items-center gap-2 px-4">
        <img src="/logo.png" alt="LakeGen" className="h-[18px] w-[18px] rounded-[4px] object-contain" />
        <span className="text-[14px] font-semibold tracking-[-0.01em]">LakeGen</span>
      </div>

      <nav className="flex flex-col gap-0.5 px-2.5 pt-1" aria-label="Primary">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex h-[30px] items-center gap-2.5 rounded-md px-2.5 text-[13px] transition-colors duration-150 ${
                isActive
                  ? 'bg-line-soft font-medium text-ink'
                  : 'text-ink-muted hover:bg-line-soft/70 hover:text-ink'
              }`
            }
          >
            <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto border-t border-line px-4 py-3">
        <div className="text-2xs uppercase tracking-wider text-ink-faint">Active catalog</div>
        {activeCatalog ? (
          <div className="mt-1.5 flex items-center gap-2">
            <StatusDot connected={activeCatalog.connected} />
            <span className="truncate font-mono text-[12px] text-ink">{activeCatalog.name}</span>
          </div>
        ) : (
          <div className="mt-1.5 text-[12px] text-ink-faint">
            {catalogs.length === 0 ? 'None configured' : 'None selected'}
          </div>
        )}
      </div>
    </aside>
  );
}
