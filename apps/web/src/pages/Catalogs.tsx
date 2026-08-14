import { useState } from 'react';
import { PlusIcon } from 'lucide-react';
import { useLakeGen } from '../state/LakeGenContext';
import { Button } from '../components/ui/Button';
import { CatalogRow } from '../components/catalogs/CatalogRow';
import { AddCatalogPanel } from '../components/catalogs/AddCatalogPanel';

export function Catalogs() {
  const {
    catalogs,
    catalogsError,
    catalogsLoading,
    activeCatalogName,
    setActiveCatalogName,
    removeCatalog,
  } = useLakeGen();
  const [panelOpen, setPanelOpen] = useState(false);
  const connected = catalogs.filter((c) => c.connected).length;

  return (
    <main className="flex h-full min-w-0 flex-1 flex-col bg-canvas">
      <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-line px-8">
        <h1 className="text-[13px] font-medium text-ink">Catalogs</h1>
        {catalogs.length > 0 && (
          <span className="text-[13px] text-ink-faint">
            {connected} of {catalogs.length} connected
          </span>
        )}
        {catalogs.length > 0 && (
          <Button variant="secondary" className="ml-auto" onClick={() => setPanelOpen(true)}>
            <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
            Add catalog
          </Button>
        )}
      </header>

      <div className="lg-scroll flex-1 overflow-y-auto">
        {catalogsLoading ? (
          <p className="px-8 pt-10 text-[13px] text-ink-faint">Loading catalogs…</p>
        ) : catalogsError ? (
          <p className="px-8 pt-10 text-[13px] text-err">{catalogsError}</p>
        ) : catalogs.length === 0 ? (
          <div className="mx-auto max-w-[560px] px-8 pt-[20vh] text-center">
            <h2 className="text-[16px] font-medium text-ink">No catalogs yet</h2>
            <p className="mt-1.5 text-[14px] text-ink-muted">
              Add a catalog to start talking to your lakehouse.
            </p>
            <div className="mt-5 flex justify-center">
              <Button variant="primary" onClick={() => setPanelOpen(true)}>
                <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
                Add catalog
              </Button>
            </div>
          </div>
        ) : (
          <div className="px-8 py-6">
            <div className="overflow-hidden rounded-xl border border-line bg-panel">
              <div className="grid grid-cols-[200px_64px_1fr_220px_36px] items-center gap-4 border-b border-line bg-canvas px-4 py-2">
                <span className="text-2xs font-medium uppercase tracking-wider text-ink-faint">Name</span>
                <span className="text-2xs font-medium uppercase tracking-wider text-ink-faint">Type</span>
                <span className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                  Warehouse
                </span>
                <span className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                  Connection
                </span>
                <span className="sr-only">Actions</span>
              </div>

              {catalogs.map((catalog) => (
                <CatalogRow
                  key={catalog.name}
                  catalog={catalog}
                  isActive={catalog.name === activeCatalogName}
                  onSetActive={() => setActiveCatalogName(catalog.name)}
                  onRemove={() => {
                    void removeCatalog(catalog.name);
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <AddCatalogPanel open={panelOpen} onClose={() => setPanelOpen(false)} />
    </main>
  );
}
