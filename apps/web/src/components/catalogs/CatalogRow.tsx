import { Loader2Icon, Trash2Icon } from 'lucide-react';
import type { CatalogResponse } from '../../api/types';
import { IconButton } from '../ui/IconButton';
import { TypeBadge } from '../ui/TypeBadge';

interface CatalogRowProps {
  catalog: CatalogResponse;
  removing?: boolean;
  onRemove: () => void;
}

export function CatalogRow({
  catalog,
  removing = false,
  onRemove,
}: CatalogRowProps) {
  return (
    <tr className="border-b border-line-soft transition-colors duration-150 hover:bg-line-soft/40 last:border-0">
      <td className="w-1/3 px-4 py-2.5">
        <span className="block truncate font-mono text-[13px] text-ink">{catalog.name}</span>
      </td>

      <td className="w-1/3 px-4 py-2.5 text-center"><TypeBadge type={catalog.catalog_type} /></td>

      <td className="w-1/3 px-4 py-2.5 text-right">
        <IconButton
          variant="danger-quiet"
          className="ml-auto mr-1.5"
          label={`Delete ${catalog.name}`}
          title={removing ? 'Deleting…' : 'Delete catalog'}
          onClick={onRemove}
          disabled={removing}
        >
          {removing ? (
            <Loader2Icon className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
          ) : (
            <Trash2Icon className="h-3.5 w-3.5" strokeWidth={2} />
          )}
        </IconButton>
      </td>
    </tr>
  );
}
