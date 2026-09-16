import { useEffect, useState } from 'react';
import { PlusIcon, RefreshCwIcon } from 'lucide-react';
import { useLakeGen } from '../state/LakeGenContext';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';
import { CatalogRow } from '../components/catalogs/CatalogRow';
import { AddCatalogPanel } from '../components/catalogs/AddCatalogPanel';

export function Catalogs() {
  const { notify } = useToast();
  const {
    catalogs,
    catalogsError,
    catalogsLoading,
    catalogsRefreshing,
    refreshCatalogs,
    activeCatalogName,
    setActiveCatalogName,
    removeCatalog,
  } = useLakeGen();
  const [panelOpen, setPanelOpen] = useState(false);
  const [catalogToRemove, setCatalogToRemove] = useState<string | null>(null);
  const [removingName, setRemovingName] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const connected = catalogs.filter((c) => c.connected).length;

  useEffect(() => {
    document.title = 'Catalogs · LakeGen';
  }, []);

  async function confirmRemove() {
    if (!catalogToRemove) return;

    setRemovingName(catalogToRemove);
    setRemoveError(null);
    try {
      await removeCatalog(catalogToRemove);
      setCatalogToRemove(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not remove the catalog.';
      setRemoveError(message);
      notify({ tone: 'error', message });
      setCatalogToRemove(null);
    } finally {
      setRemovingName(null);
    }
  }

  return (
    <main className="flex h-full min-w-0 flex-1 flex-col bg-canvas">
      <header className="flex h-header shrink-0 items-center gap-3 border-b border-line px-8">
        <h1 className="text-[13px] font-medium text-ink">Catalogs</h1>
        {catalogs.length > 0 && (
          <span className="text-[13px] text-ink-faint">
            {connected} cached connection{connected === 1 ? '' : 's'}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void refreshCatalogs()}
            disabled={catalogsLoading || catalogsRefreshing}
          >
            <RefreshCwIcon
              className={`h-3.5 w-3.5 ${catalogsRefreshing ? 'animate-spin' : ''}`}
              strokeWidth={2}
            />
            Refresh
          </Button>
          <Button variant="secondary" onClick={() => setPanelOpen(true)}>
            <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
            Add catalog
          </Button>
        </div>
      </header>

      <div className="lg-scroll flex-1 overflow-y-auto">
        {removeError && (
          <p role="alert" className="px-8 pt-4 text-[13px] text-err">
            {removeError}
          </p>
        )}
        {catalogsLoading ? (
          <p className="px-8 pt-10 text-[13px] text-ink-faint">Loading catalogs…</p>
        ) : catalogsError && catalogs.length === 0 ? (
          <div className="px-8 pt-10">
            <p role="alert" className="text-[13px] text-err">{catalogsError}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => void refreshCatalogs()}>
              Retry
            </Button>
          </div>
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
            <div className="overflow-x-auto rounded-xl border border-line bg-panel">
              <table className="min-w-[720px] w-full border-collapse text-left">
                <thead className="border-b border-line bg-canvas">
                  <tr>
                    <th scope="col" className="px-4 py-2 text-2xs font-medium uppercase tracking-wider text-ink-faint">Name</th>
                    <th scope="col" className="px-4 py-2 text-2xs font-medium uppercase tracking-wider text-ink-faint">Type</th>
                    <th scope="col" className="px-4 py-2 text-2xs font-medium uppercase tracking-wider text-ink-faint">Warehouse</th>
                    <th scope="col" className="px-4 py-2 text-2xs font-medium uppercase tracking-wider text-ink-faint">Connection</th>
                    <th scope="col" className="w-10 px-2 py-2"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {catalogs.map((catalog) => (
                    <CatalogRow
                      key={catalog.name}
                      catalog={catalog}
                      isActive={catalog.name === activeCatalogName}
                      removing={catalog.name === removingName}
                      onSetActive={() => setActiveCatalogName(catalog.name)}
                      onRemove={() => {
                        setRemoveError(null);
                        setCatalogToRemove(catalog.name);
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <AddCatalogPanel open={panelOpen} onClose={() => setPanelOpen(false)} />
      {/* TODO(backend): `connected` is an in-process cache flag (core/catalog/service.py:110-118),
          not a health check. Expose an on-demand catalog probe before treating it as one. */}
      <ConfirmDialog
        open={catalogToRemove !== null}
        title="Remove catalog?"
        description={`Remove ${catalogToRemove ?? ''} and delete its stored credentials. This cannot be undone.`}
        confirmLabel="Remove catalog"
        busy={removingName !== null}
        onCancel={() => setCatalogToRemove(null)}
        onConfirm={() => {
          void confirmRemove();
        }}
      />
    </main>
  );
}
