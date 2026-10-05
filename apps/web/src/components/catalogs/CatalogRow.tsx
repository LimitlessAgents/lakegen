import type { CatalogResponse } from '../../api/types';
import { Button } from '../ui/Button';
import { TypeBadge } from '../ui/TypeBadge';

interface CatalogRowProps {
  catalog: CatalogResponse;
  isActive: boolean;
  removing?: boolean;
  onRemove: () => void;
}

export function CatalogRow({
  catalog,
  isActive,
  removing = false,
  onRemove,
}: CatalogRowProps) {
  return (
    <tr className="border-b border-line-soft transition-colors duration-150 hover:bg-line-soft/40 last:border-0">
      <td className="w-1/3 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-mono text-[13px] text-ink">{catalog.name}</span>
          {isActive && (
            <span className="shrink-0 rounded border border-line bg-panel px-1 text-[10px] uppercase tracking-wider text-ink-faint">
              active
            </span>
          )}
        </div>
      </td>

      <td className="w-1/3 px-4 py-2.5 text-center"><TypeBadge type={catalog.catalog_type} /></td>

      <td className="w-1/3 px-4 py-2.5 text-right">
        <Button
          variant="danger"
          size="sm"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Delete ${catalog.name}`}
        >
          Delete
        </Button>
      </td>
    </tr>
  );
}
