import { XIcon } from 'lucide-react';
import { createContext, useCallback, useContext, useState } from 'react';

type ToastTone = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastValue {
  notify: (toast: Omit<Toast, 'id'>) => void;
}

const ToastContext = createContext<ToastValue | null>(null);
let nextToastId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = ++nextToastId;
    setToasts((current) => [...current, { ...toast, id }]);
    if (toast.tone !== 'error') {
      window.setTimeout(() => {
        setToasts((current) => current.filter((item) => item.id !== id));
      }, 4_000);
    }
  }, []);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="fixed bottom-4 right-4 z-toast flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === 'error' ? 'alert' : 'status'}
            className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 shadow-pop ${
              toast.tone === 'error'
                ? 'border-err-border bg-err-soft text-err-strong'
                : 'border-line bg-panel text-ink'
            }`}
          >
            <p className="flex-1 text-[13px] leading-[1.45]">{toast.message}</p>
            <button
              type="button"
              onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))}
              className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-faint hover:bg-line-soft hover:text-ink"
              aria-label="Dismiss notification"
            >
              <XIcon className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
}
