import { useId } from 'react';

interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
}

export function Checkbox({ label, checked, onChange, hint }: CheckboxProps) {
  const id = useId();
  const hintId = `${id}-hint`;

  return (
    <div>
      <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          aria-describedby={hint ? hintId : undefined}
          className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded border-line text-accent accent-ink"
        />
        <span className="text-[12.5px] leading-snug text-ink">{label}</span>
      </label>
      {hint && <p id={hintId} className="mt-1 pl-6 text-xs leading-snug text-ink-faint">{hint}</p>}
    </div>
  );
}
