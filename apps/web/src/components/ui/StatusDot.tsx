export type CatalogConnectionState = 'connected' | 'unverified';

export function StatusDot({
  state,
  className = '',
}: {
  state: CatalogConnectionState;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-[6px] w-[6px] shrink-0 rounded-full ${
        state === 'connected' ? 'bg-ok' : 'bg-ink-faint'
      } ${className}`}
    />
  );
}
