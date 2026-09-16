import { ChevronDownIcon, PlusIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLakeGen } from '../../state/LakeGenContext';
import { StatusDot } from '../ui/StatusDot';
import { TypeBadge } from '../ui/TypeBadge';
import { Menu } from '../ui/Menu';

export function AgentHeader() {
  const { catalogs, activeCatalog, setActiveCatalogName, newConversation } = useLakeGen();

  return (
    <header className="flex h-header shrink-0 items-center gap-3 border-b border-line bg-canvas px-8">
      <h1 className="text-[13px] font-medium text-ink">Agent</h1>
      <span aria-hidden="true" className="text-ink-faint">
        ·
      </span>

      <Menu
        label="Active catalog"
        className="w-[300px]"
        trigger={
        <button
          type="button"
          className="flex h-7 items-center gap-2 rounded-md border border-transparent px-2 text-[13px] text-ink-muted transition-colors hover:border-line hover:bg-panel"
        >
          <span>Active catalog</span>
          {activeCatalog ? (
            <span className="flex items-center gap-1.5">
              <StatusDot state={activeCatalog.connected ? 'connected' : 'unverified'} />
              <span className="sr-only">
                {activeCatalog.connected ? 'Connection cached' : 'Connection not verified'}
              </span>
              <span className="font-mono text-ink">{activeCatalog.name}</span>
            </span>
          ) : (
            <span className="text-ink-faint">none</span>
          )}
          <ChevronDownIcon className="h-3.5 w-3.5 text-ink-faint" strokeWidth={2} />
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
                  catalog.name === activeCatalog?.name ? 'bg-line-soft/70' : ''
                }`}
              >
                <StatusDot state={catalog.connected ? 'connected' : 'unverified'} />
                <span className="font-mono text-[13px] text-ink">{catalog.name}</span>
                <span className="ml-auto">
                  <TypeBadge type={catalog.catalog_type} />
                </span>
              </button>
            ))}
          </>
        )}
      </Menu>

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
