import type { CatalogType } from '../../api/types';

const styles: Record<CatalogType, string> = {
  glue: 'text-badge-glue bg-badge-glue-soft border-badge-glue-border',
  rest: 'text-accent bg-accent-soft border-badge-rest-border',
  sql: 'text-badge-sql bg-badge-sql-soft border-badge-sql-border',
};

export function TypeBadge({ type }: { type?: string | null }) {
  if (!type || !(type in styles)) {
    return (
      <span className="inline-flex h-[18px] items-center rounded border border-line px-1.5 font-mono text-[10px] font-medium tracking-wider text-ink-faint">
        —
      </span>
    );
  }
  return (
    <span
      className={`inline-flex h-[18px] items-center rounded border px-1.5 font-mono text-[10px] font-medium tracking-wider ${styles[type as CatalogType]}`}
    >
      {type.toUpperCase()}
    </span>
  );
}
