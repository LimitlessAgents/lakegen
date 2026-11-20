import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
  variant?: 'default' | 'primary' | 'danger';
}

const variants = {
  default:
    'border border-line text-ink-muted enabled:hover:bg-line-soft enabled:hover:text-ink disabled:text-ink-faint',
  primary:
    'bg-accent text-white enabled:hover:bg-accent-hover disabled:bg-sunken disabled:text-ink-faint',
  danger: 'text-err enabled:hover:bg-err-soft disabled:text-ink-faint',
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
      className={`flex h-8 w-8 items-center justify-center rounded-md transition-colors duration-150 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
});
