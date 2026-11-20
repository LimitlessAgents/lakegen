import React from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'sm' | 'md';
}

const base =
  'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-150 disabled:cursor-not-allowed whitespace-nowrap';

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-white enabled:hover:bg-accent-hover disabled:bg-sunken disabled:text-ink-faint',
  secondary:
    'bg-panel text-ink border border-line enabled:hover:bg-line-soft enabled:hover:border-line-strong disabled:border-transparent disabled:bg-sunken disabled:text-ink-faint',
  ghost:
    'text-ink-muted enabled:hover:text-ink enabled:hover:bg-line-soft disabled:text-ink-faint',
  danger: 'text-err enabled:hover:bg-err-soft disabled:text-ink-faint',
};

const sizes = {
  sm: 'h-8 px-2.5 text-[13px]',
  md: 'h-8 px-3 text-[13px]',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      type={props.type ?? 'button'}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  );
}
