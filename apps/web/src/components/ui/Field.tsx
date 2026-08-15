import { LockIcon } from 'lucide-react';

interface FieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
  secret?: boolean;
  mono?: boolean;
  required?: boolean;
  type?: string;
  className?: string;
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
  hint,
  secret = false,
  mono = false,
  required = false,
  type = 'text',
  className = '',
}: FieldProps) {
  const id = `field-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 flex items-center gap-1.5 text-[12.5px] text-ink-muted">
        {label}
        {required && <span className="text-ink-faint">required</span>}
        {secret && <LockIcon className="h-3 w-3 text-ink-faint" strokeWidth={2} />}
      </label>
      <input
        id={id}
        type={secret ? 'password' : type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={`h-8 w-full rounded-md border border-line bg-panel px-2.5 text-[13px] text-ink outline-none transition-colors duration-150 placeholder:text-ink-faint hover:border-line-strong focus:border-accent ${
          mono || secret ? 'font-mono' : ''
        }`}
      />
      {hint && <p className="mt-1 text-[11.5px] leading-snug text-ink-faint">{hint}</p>}
    </div>
  );
}
