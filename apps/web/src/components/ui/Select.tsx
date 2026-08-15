import { ChevronDownIcon } from 'lucide-react';

interface SelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}

export function Select({ label, value, onChange, options, className = '' }: SelectProps) {
  const id = `select-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-[12.5px] text-ink-muted">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-8 w-full appearance-none rounded-md border border-line bg-panel pl-2.5 pr-7 text-[13px] text-ink outline-none transition-colors duration-150 hover:border-line-strong focus:border-accent"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDownIcon
          className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint"
          strokeWidth={2}
        />
      </div>
    </div>
  );
}
