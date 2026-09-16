import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangleIcon, Loader2Icon } from 'lucide-react';
import type { ErrorCode } from '../../api/types';
import { presentError } from '../../api/errors';
import { StatusDot } from '../ui/StatusDot';
import { Button } from '../ui/Button';

export type ConnectStatus = 'connecting' | 'success' | 'error';

interface ConnectStatusDialogProps {
  status: ConnectStatus | null;
  catalogName: string;
  message?: string | null;
  errorCode?: ErrorCode | null;
  onCancel: () => void;
  onBack: () => void;
  onClose: () => void;
}

export function ConnectStatusDialog({
  status,
  catalogName,
  message,
  errorCode,
  onCancel,
  onBack,
  onClose,
}: ConnectStatusDialogProps) {
  const error = presentError(errorCode);

  return (
    <AnimatePresence>
      {status && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-popover flex items-center justify-center bg-ink/10"
        >
          <motion.div
            role={status === 'error' ? 'alertdialog' : 'dialog'}
            aria-modal="true"
            aria-live="polite"
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                if (status === 'connecting') onCancel();
                else onClose();
              }
            }}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-[320px] rounded-xl border border-line bg-panel px-6 py-8 text-center shadow-pop"
          >
            {status === 'connecting' && (
              <>
                <Loader2Icon
                  className="mx-auto h-5 w-5 animate-spin text-ink-muted"
                  strokeWidth={1.75}
                />
                <p className="mt-4 text-[13px] font-medium text-ink">Connecting</p>
                <p className="mt-1 font-mono text-[12px] text-ink-muted">{catalogName}</p>
                <Button variant="ghost" size="sm" className="mt-4" onClick={onCancel} autoFocus>
                  Cancel
                </Button>
              </>
            )}
            {status === 'success' && (
              <>
                <div className="flex items-center justify-center gap-2">
                  <StatusDot state="connected" />
                  <p className="text-[13px] font-medium text-ink">Connected</p>
                </div>
                <p className="mt-1.5 font-mono text-[12px] text-ink-muted">{catalogName}</p>
              </>
            )}
            {status === 'error' && (
              <>
                <div className="flex items-center justify-center gap-2">
                  <AlertTriangleIcon className="h-4 w-4 text-err" strokeWidth={2} />
                  <p className="text-[13px] font-medium text-err">{error.title}</p>
                </div>
                <p className="mt-1.5 text-sm leading-snug text-ink-muted">
                  {message ?? error.hint}
                </p>
                <div className="mt-5 flex justify-center gap-2">
                  <Button variant="secondary" size="sm" onClick={onBack} autoFocus>
                    Back to form
                  </Button>
                  <Button variant="ghost" size="sm" onClick={onClose}>
                    Close
                  </Button>
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

