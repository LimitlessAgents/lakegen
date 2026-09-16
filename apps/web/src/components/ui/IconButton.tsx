import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
  variant?: 'default' | 'primary' | 'danger';
}

const variants = {
  default: 'border border-line text-ink-muted hover:bg-line-soft hover:text-ink',
  primary: 'bg-ink text-white hover:bg-accent-hover',
  danger: 'text-err hover:bg-err-soft',
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton({
  label,
  children,
  variant = 'default',
  className = '',
  type = 'button',
  ...props
}, ref) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
});
