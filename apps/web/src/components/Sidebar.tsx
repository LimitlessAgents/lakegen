import { useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  DatabaseIcon,
  MessagesSquareIcon,
  PencilIcon,
  PlusIcon,
  Trash2Icon,
} from 'lucide-react';
import { useLakeGen } from '../state/LakeGenContext';
import type { SessionResponse } from '../api/types';
import { Button } from './ui/Button';
import { ConfirmDialog } from './ui/ConfirmDialog';

const SESSION_NAME_MAX_LENGTH = 100;

function sessionTitle(session: SessionResponse): string {
  const createdAt = new Date(session.created_at);
  const fallback = Number.isNaN(createdAt.getTime())
    ? 'Untitled session'
    : createdAt.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
  return session.name?.trim() || fallback;
}

const items = [
  { to: '/agent', label: 'Agent', icon: MessagesSquareIcon },
  { to: '/catalogs', label: 'Catalogs', icon: DatabaseIcon },
];

function navClass(isActive: boolean, compact = false) {
  return `flex items-center gap-2 rounded-md text-[13px] transition-colors duration-150 ${compact ? 'h-7 px-2' : 'h-[30px] gap-2.5 px-2.5'
    } ${isActive
      ? 'bg-accent-soft font-medium text-accent shadow-[inset_2px_0_0_0_theme(colors.accent.DEFAULT)]'
      : 'text-ink-muted hover:bg-line/60 hover:text-ink'
    }`;
}

export function Sidebar() {
  const {
    sessions,
    sessionsLoading,
    sessionsLoadingMore,
    sessionsError,
    sessionsHasMore,
    loadMoreSessions,
    selectedSessionId,
    selectSession,
    renameSession,
    deleteSession,
    newConversation,
  } = useLakeGen();
  const navigate = useNavigate();
  const location = useLocation();
  const [editing, setEditing] = useState<{ id: string; value: string } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SessionResponse | null>(null);
  const [deleting, setDeleting] = useState(false);
  const discardOnBlurRef = useRef(false);

  function startConversation() {
    newConversation();
    if (location.pathname !== '/agent') navigate('/agent');
  }

  function startEditing(session: SessionResponse) {
    discardOnBlurRef.current = false;
    setEditing({ id: session.id, value: session.name ?? '' });
  }

  async function submitRename(session: SessionResponse, rawValue: string) {
    setEditing(null);
    await renameSession(session, rawValue);
  }

  async function confirmDelete() {
    const session = pendingDelete;
    if (!session) return;
    setDeleting(true);
    try {
      await deleteSession(session);
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  return (
    <>
      <nav
        className="flex h-header shrink-0 items-center gap-1 border-b border-line bg-canvas px-3 md:hidden"
        aria-label="Primary"
      >
        <picture className="flex shrink-0">
          <source media="(prefers-color-scheme: dark)" srcSet="/images/brand/lakegen-mark-light.svg" />
          <source media="(prefers-color-scheme: light)" srcSet="/images/brand/lakegen-mark-light.svg" />
          <img src="/images/brand/lakegen-mark-light.svg" alt="LakeGen" className="h-[18px] w-[18px] rounded-[4px] object-contain" />
        </picture>
        <span className="mr-2 text-[14px] font-semibold tracking-[-0.01em]">LakeGen</span>
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => navClass(isActive, true)}>
            <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>

      <aside className="hidden w-[212px] shrink-0 flex-col border-r border-line bg-sunken md:flex">
        <div className="flex h-header items-center gap-2 px-4">
          <picture className="flex shrink-0">
            <source media="(prefers-color-scheme: dark)" srcSet="/images/brand/lakegen-mark-light.svg" />
            <source media="(prefers-color-scheme: light)" srcSet="/images/brand/lakegen-mark-light.svg" />
            <img src="/images/brand/lakegen-mark-light.svg" alt="LakeGen" className="h-[18px] w-[18px] rounded-[4px] object-contain" />
          </picture>
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

        <div className="mt-5 px-2.5">
          <Button
            variant="secondary"
            size="sm"
            className="w-full !justify-start gap-2"
            onClick={startConversation}
          >
            <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
            New conversation
          </Button>
        </div>

        <div className="mt-4 min-h-0 px-2.5">
          <div className="px-2.5 text-2xs uppercase tracking-wider text-ink-muted">Sessions</div>
          <div className="lg-scroll mt-1 max-h-[35vh] overflow-y-auto">
            {sessionsLoading && (
              <p className="px-2.5 py-1.5 text-[12px] text-ink-muted">Loading sessions…</p>
            )}
            {!sessionsLoading && sessions.length === 0 && !sessionsError && (
              <p className="px-2.5 py-1.5 text-[12px] text-ink-muted">No sessions yet</p>
            )}
            {sessions.map((session) => {
              const title = sessionTitle(session);
              if (editing?.id === session.id) {
                return (
                  <input
                    key={session.id}
                    autoFocus
                    value={editing.value}
                    maxLength={SESSION_NAME_MAX_LENGTH}
                    aria-label={`Rename ${title}`}
                    onChange={(event) => setEditing({ id: session.id, value: event.target.value })}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void submitRename(session, event.currentTarget.value);
                      } else if (event.key === 'Escape') {
                        event.preventDefault();
                        discardOnBlurRef.current = true;
                        setEditing(null);
                      }
                    }}
                    onBlur={(event) => {
                      if (discardOnBlurRef.current) {
                        discardOnBlurRef.current = false;
                        return;
                      }
                      void submitRename(session, event.currentTarget.value);
                    }}
                    className="block w-full rounded-md border border-accent/50 bg-panel px-2.5 py-1 text-[12px] text-ink outline-none focus:border-accent"
                  />
                );
              }
              return (
                <div key={session.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => void selectSession(session)}
                    className={`block w-full truncate rounded-md py-1.5 pl-2.5 pr-12 text-left text-[12px] transition-colors ${session.id === selectedSessionId
                      ? 'bg-accent-soft font-medium text-accent shadow-[inset_2px_0_0_0_theme(colors.accent.DEFAULT)]'
                      : 'text-ink-muted hover:bg-line/60 hover:text-ink'
                      }`}
                    title={title}
                  >
                    {title}
                  </button>
                  <div className="absolute right-0.5 top-1/2 flex -translate-y-1/2 items-center">
                    <button
                      type="button"
                      onClick={() => startEditing(session)}
                      aria-label={`Rename ${title}`}
                      title="Rename session"
                      className="flex h-5 w-5 items-center justify-center rounded text-ink-faint opacity-0 transition-opacity hover:bg-line hover:text-ink focus-visible:opacity-100 group-hover:opacity-100 group-focus-within:opacity-100"
                    >
                      <PencilIcon className="h-3 w-3" strokeWidth={2} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDelete(session)}
                      aria-label={`Delete ${title}`}
                      title="Delete session"
                      className="flex h-5 w-5 items-center justify-center rounded text-ink-faint opacity-0 transition-opacity hover:bg-line hover:text-err focus-visible:opacity-100 group-hover:opacity-100 group-focus-within:opacity-100"
                    >
                      <Trash2Icon className="h-3 w-3" strokeWidth={2} />
                    </button>
                  </div>
                </div>
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
                className="block w-full rounded-md px-2.5 py-1.5 text-left text-[12px] font-medium text-accent hover:bg-line/60 disabled:cursor-wait disabled:text-ink-faint"
              >
                {sessionsLoadingMore ? 'Loading…' : sessions.length === 0 ? 'Retry' : 'Load more'}
              </button>
            )}
          </div>
        </div>
      </aside>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete session?"
        description={
          pendingDelete
            ? `Delete “${sessionTitle(pendingDelete)}” and its conversation history. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        busy={deleting}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          void confirmDelete();
        }}
      />
    </>
  );
}
