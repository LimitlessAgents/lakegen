export function StatusDot({
  connected,
  className = '',
}: {
  connected: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-[6px] w-[6px] shrink-0 rounded-full ${
        connected ? 'bg-ok' : 'bg-err'
      } ${className}`}
    />
  );
}
