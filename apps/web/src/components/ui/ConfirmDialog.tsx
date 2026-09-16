import { AlertTriangleIcon } from 'lucide-react';
import { Button } from './Button';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-popover flex items-center justify-center bg-ink/10 p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        className="w-full max-w-[400px] rounded-xl border border-line bg-panel p-5 shadow-pop"
      >
        <div className="flex items-start gap-3">
          <AlertTriangleIcon className="mt-0.5 h-5 w-5 shrink-0 text-err" strokeWidth={1.75} />
          <div>
            <h2 id="confirm-dialog-title" className="text-[14px] font-medium text-ink">
              {title}
            </h2>
            <p id="confirm-dialog-description" className="mt-1.5 text-[13px] leading-[1.5] text-ink-muted">
              {description}
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Removing…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
