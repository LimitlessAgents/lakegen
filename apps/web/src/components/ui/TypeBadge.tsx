import type { CatalogType } from '../../api/types';

const styles: Record<CatalogType, string> = {
  glue: 'text-[#7A5B12] bg-[#FBF5E7] border-[#EEE3C9]',
  rest: 'text-accent bg-accent-soft border-[#D6E5E1]',
  sql: 'text-[#3F5C86] bg-[#EEF2F8] border-[#D9E2EF]',
};

export function TypeBadge({ type }: { type: CatalogType | null }) {
  if (!type) {
    return (
      <span className="inline-flex h-[18px] items-center rounded border border-line px-1.5 font-mono text-[10px] font-medium tracking-wider text-ink-faint">
        —
      </span>
    );
  }
  return (
    <span
      className={`inline-flex h-[18px] items-center rounded border px-1.5 font-mono text-[10px] font-medium tracking-wider ${styles[type]}`}
    >
      {type.toUpperCase()}
    </span>
  );
}
