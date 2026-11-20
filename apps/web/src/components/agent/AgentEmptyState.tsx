import { ArrowRightIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLakeGen } from '../../state/LakeGenContext';

export function AgentEmptyState() {
  const { activeCatalog, catalogs } = useLakeGen();

  if (catalogs.length === 0) {
    return (
      <div className="text-center">
        <h2 className="text-[24px] font-medium tracking-[-0.02em] text-ink">
          Connect a catalog to get started.
        </h2>
        <p className="mx-auto mt-2 max-w-[440px] text-[14px] leading-[1.6] text-ink-muted">
          LakeGen needs a catalog before it can inspect your lakehouse.
        </p>
        <Link
          to="/catalogs"
          className="mx-auto mt-5 inline-flex h-8 items-center gap-1.5 rounded-md bg-accent px-3 text-[13px] font-medium text-white hover:bg-accent-hover"
        >
          Add catalog
          <ArrowRightIcon className="h-3.5 w-3.5" strokeWidth={2} />
        </Link>
      </div>
    );
  }

  if (!activeCatalog) {
    return (
      <div className="text-center">
        <h2 className="text-[24px] font-medium tracking-[-0.02em] text-ink">
          Select a catalog to get started.
        </h2>
        <p className="mx-auto mt-2 max-w-[440px] text-[14px] leading-[1.6] text-ink-muted">
          Choose an active catalog from the header above, then ask your first question.
        </p>
      </div>
    );
  }

  return (
    <div className="text-center">
      <h2 className="text-[24px] font-medium tracking-[-0.02em] text-ink">
        What would you like to explore?
      </h2>
    </div>
  );
}
