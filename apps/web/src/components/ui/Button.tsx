import React from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'sm' | 'md';
}

const base =
  'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 whitespace-nowrap';

const variants: Record<Variant, string> = {
  primary: 'bg-ink text-white hover:bg-accent-hover',
  secondary:
    'bg-panel text-ink border border-line hover:bg-line-soft hover:border-line-strong',
  ghost: 'text-ink-muted hover:text-ink hover:bg-line-soft',
  danger: 'text-err hover:bg-err-soft',
};

const sizes = {
  sm: 'h-7 px-2.5 text-[13px]',
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
