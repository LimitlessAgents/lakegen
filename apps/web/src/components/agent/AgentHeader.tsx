import { ChevronDownIcon, PlusIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLakeGen } from '../../state/LakeGenContext';
import { TypeBadge } from '../ui/TypeBadge';
import { Menu } from '../ui/Menu';
import { StatusDot } from '../ui/StatusDot';

function ConnectionState({ connected }: { connected: boolean }) {
  return (
    <>
      <StatusDot state={connected ? 'connected' : 'unverified'} />
      <span className="sr-only">
        {connected ? 'Connection cached' : 'Connection not verified'}
      </span>
    </>
  );
}

const triggerClass =
  'flex h-7 min-w-0 items-center gap-2 rounded-md px-1.5 text-sm transition-colors';

const catalogChipClass =
  'flex min-w-0 items-center gap-1.5 rounded border border-badge-rest-border bg-accent-soft px-1.5 font-mono text-xs text-accent';

export function AgentHeader() {
  const {
    catalogs,
    activeCatalog,
    activeCatalogName,
    setActiveCatalogName,
    isActiveCatalogLocked,
    newConversation,
  } = useLakeGen();
  const catalogLockedTitle =
    'This session is tied to its catalog. Start a new conversation to use another catalog.';

  return (
    <header className="flex h-header shrink-0 items-center gap-2 border-b border-line bg-canvas px-4 sm:px-8">
      <h1 className="shrink-0 text-sm font-medium text-ink">Agent</h1>
      <span aria-hidden="true" className="h-3.5 w-px shrink-0 bg-line-strong" />

      {isActiveCatalogLocked ? (
        <div title={catalogLockedTitle} className={`${triggerClass} cursor-default`}>
          <span className="shrink-0 text-xs text-ink-faint">Session catalog</span>
          {activeCatalog ? (
            <span className={catalogChipClass}>
              <ConnectionState connected={activeCatalog.connected} />
              <span className="truncate">{activeCatalog.name}</span>
            </span>
          ) : (
            <span className={catalogChipClass}>
              <span className="truncate">{activeCatalogName ?? 'unknown'}</span>
            </span>
          )}
        </div>
      ) : (
        <Menu
          label="Active catalog"
          className="w-[300px]"
          trigger={
            <button type="button" className={`${triggerClass} text-ink-muted hover:bg-line-soft`}>
              <span className="shrink-0 text-xs text-ink-faint">Active catalog</span>
              {activeCatalog ? (
                <span className={catalogChipClass}>
                  <ConnectionState connected={activeCatalog.connected} />
                  <span className="truncate">{activeCatalog.name}</span>
                </span>
              ) : (
                <span className="text-ink-faint">none</span>
              )}
              <ChevronDownIcon className="h-3.5 w-3.5 shrink-0 text-ink-faint" strokeWidth={2} />
            </button>
          }
        >
          {(close) => (
            <>
              {catalogs.length === 0 && (
                <Link
                  to="/catalogs"
                  onClick={close}
                  className="block px-3 py-2 text-sm text-accent hover:bg-line-soft"
                >
                  Add a catalog
                </Link>
              )}
              {catalogs.map((catalog) => (
                <button
                  key={catalog.name}
                  role="menuitemradio"
                  aria-checked={catalog.name === activeCatalog?.name}
                  onClick={() => {
                    setActiveCatalogName(catalog.name);
                    close();
                  }}
                  className={`flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-line-soft ${
                    catalog.name === activeCatalog?.name
                      ? 'bg-accent-soft shadow-[inset_2px_0_0_0_theme(colors.accent.DEFAULT)]'
                      : ''
                  }`}
                >
                  <span className="font-mono text-[13px] text-ink">{catalog.name}</span>
                  <span className="ml-auto">
                    <TypeBadge type={catalog.catalog_type} />
                  </span>
                </button>
              ))}
            </>
          )}
        </Menu>
      )}

      <button
        type="button"
        onClick={newConversation}
        className="ml-auto flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm text-ink-muted transition-colors hover:bg-line-soft hover:text-ink md:hidden"
      >
        <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
        New conversation
      </button>
    </header>
  );
}
