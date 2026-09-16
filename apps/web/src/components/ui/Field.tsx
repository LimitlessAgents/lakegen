import { EyeIcon, EyeOffIcon, LockIcon } from 'lucide-react';
import { useId, useState } from 'react';

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
  error?: string;
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
  error,
  className = '',
}: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const [revealed, setRevealed] = useState(false);

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 flex items-center gap-1.5 text-[12.5px] text-ink-muted">
        {label}
        {required && <span aria-hidden="true" className="text-err">*</span>}
        {secret && <LockIcon className="h-3 w-3 text-ink-faint" strokeWidth={2} />}
      </label>
      <div className="relative">
        <input
          id={id}
          type={secret && !revealed ? 'password' : type}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          required={required}
          aria-required={required || undefined}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={[hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined}
          autoComplete={secret ? 'off' : undefined}
          autoCapitalize={mono || secret ? 'off' : undefined}
          spellCheck={!(mono || secret)}
          className={`h-8 w-full rounded-md border bg-panel px-2.5 text-sm text-ink outline-none transition-colors duration-150 placeholder:text-ink-faint hover:border-line-strong focus:border-accent ${
            error ? 'border-err' : 'border-line'
          } ${mono || secret ? 'font-mono' : ''} ${secret ? 'pr-9' : ''}`}
        />
        {secret && (
          <button
            type="button"
            onClick={() => setRevealed((current) => !current)}
            className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-line-soft hover:text-ink"
            aria-label={revealed ? `Hide ${label}` : `Show ${label}`}
          >
            {revealed ? <EyeOffIcon className="h-3.5 w-3.5" /> : <EyeIcon className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
      {hint && <p id={hintId} className="mt-1 text-xs leading-snug text-ink-faint">{hint}</p>}
      {error && <p id={errorId} className="mt-1 text-xs leading-snug text-err">{error}</p>}
    </div>
  );
}
