import { NavLink } from 'react-router-dom';
import { DatabaseIcon, MessagesSquareIcon } from 'lucide-react';
import { useLakeGen } from '../state/LakeGenContext';
import { StatusDot } from './ui/StatusDot';

const items = [
  { to: '/agent', label: 'Agent', icon: MessagesSquareIcon },
  { to: '/catalogs', label: 'Catalogs', icon: DatabaseIcon },
];

function navClass(isActive: boolean, compact = false) {
  return `flex items-center gap-2 rounded-md text-[13px] transition-colors duration-150 ${
    compact ? 'h-7 px-2' : 'h-[30px] gap-2.5 px-2.5'
  } ${
    isActive
      ? 'bg-line-soft font-medium text-ink'
      : 'text-ink-muted hover:bg-line-soft/70 hover:text-ink'
  }`;
}

export function Sidebar() {
  const {
    activeCatalog,
    catalogs,
    sessions,
    sessionsLoading,
    sessionsLoadingMore,
    sessionsError,
    sessionsHasMore,
    loadMoreSessions,
    selectedSessionId,
    selectSession,
  } = useLakeGen();

  return (
    <>
      <nav
        className="flex h-header shrink-0 items-center gap-1 border-b border-line bg-canvas px-3 md:hidden"
        aria-label="Primary"
      >
        <img src="/logo.png" alt="LakeGen" className="h-[18px] w-[18px] rounded-[4px] object-contain" />
        <span className="mr-2 text-[14px] font-semibold tracking-[-0.01em]">LakeGen</span>
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => navClass(isActive, true)}>
            <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>

      <aside className="hidden w-[212px] shrink-0 flex-col border-r border-line bg-canvas md:flex">
        <div className="flex h-header items-center gap-2 px-4">
          <img src="/logo.png" alt="LakeGen" className="h-[18px] w-[18px] rounded-[4px] object-contain" />
          <span className="text-[14px] font-semibold tracking-[-0.01em]">LakeGen</span>
        </div>

        <nav className="flex flex-col gap-0.5 px-2.5 pt-1" aria-label="Primary">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => navClass(isActive)}>
              <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-5 min-h-0 px-2.5">
          <div className="px-2.5 text-2xs uppercase tracking-wider text-ink-faint">Sessions</div>
          <div className="lg-scroll mt-1 max-h-[35vh] overflow-y-auto">
            {sessionsLoading && (
              <p className="px-2.5 py-1.5 text-[12px] text-ink-faint">Loading sessions…</p>
            )}
            {!sessionsLoading && sessions.length === 0 && !sessionsError && (
              <p className="px-2.5 py-1.5 text-[12px] text-ink-faint">No sessions yet</p>
            )}
            {sessions.map((session) => {
              const createdAt = new Date(session.created_at);
              const fallback = Number.isNaN(createdAt.getTime())
                ? 'Untitled session'
                : createdAt.toLocaleString(undefined, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  });
              const title = session.name?.trim() || fallback;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => void selectSession(session)}
                  className={`block w-full truncate rounded-md px-2.5 py-1.5 text-left text-[12px] transition-colors ${
                    session.id === selectedSessionId
                      ? 'bg-line-soft font-medium text-ink'
                      : 'text-ink-muted hover:bg-line-soft/70 hover:text-ink'
                  }`}
                  title={`${title}${session.live ? '' : ' (history only)'}`}
                >
                  {title}
                </button>
              );
            })}
            {sessionsError && (
              <p role="alert" className="px-2.5 py-1.5 text-[12px] text-err">
                {sessionsError}
              </p>
            )}
            {(sessionsHasMore || (sessionsError && sessions.length === 0)) && (
              <button
                type="button"
                disabled={sessionsLoadingMore}
                onClick={() => void loadMoreSessions()}
                className="block w-full rounded-md px-2.5 py-1.5 text-left text-[12px] font-medium text-accent hover:bg-line-soft/70 disabled:cursor-wait disabled:text-ink-faint"
              >
                {sessionsLoadingMore ? 'Loading…' : sessions.length === 0 ? 'Retry' : 'Load 10 more'}
              </button>
            )}
          </div>
        </div>

        <div className="mt-auto border-t border-line px-4 py-3">
          <div className="text-2xs uppercase tracking-wider text-ink-faint">Active catalog</div>
          {activeCatalog ? (
            <div className="mt-1.5 flex items-center gap-2">
              <StatusDot state={activeCatalog.connected ? 'connected' : 'unverified'} />
              <span className="sr-only">
                {activeCatalog.connected ? 'Connection cached' : 'Connection not verified'}
              </span>
              <span className="truncate font-mono text-[12px] text-ink">{activeCatalog.name}</span>
            </div>
          ) : (
            <div className="mt-1.5 text-[12px] text-ink-faint">
              {catalogs.length === 0 ? 'None configured' : 'None selected'}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
