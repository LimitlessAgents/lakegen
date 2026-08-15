import { AnimatePresence, motion } from 'framer-motion';
import { Loader2Icon } from 'lucide-react';
import { StatusDot } from '../ui/StatusDot';

export type ConnectStatus = 'connecting' | 'success' | 'error';

interface ConnectStatusDialogProps {
  status: ConnectStatus | null;
  catalogName: string;
  message?: string | null;
}

export function ConnectStatusDialog({
  status,
  catalogName,
  message,
}: ConnectStatusDialogProps) {
  return (
    <AnimatePresence>
      {status && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/10"
        >
          <motion.div
            role="status"
            aria-live="polite"
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
              </>
            )}
            {status === 'success' && (
              <>
                <div className="flex items-center justify-center gap-2">
                  <StatusDot connected />
                  <p className="text-[13px] font-medium text-ink">Connected</p>
                </div>
                <p className="mt-1.5 font-mono text-[12px] text-ink-muted">{catalogName}</p>
              </>
            )}
            {status === 'error' && (
              <>
                <div className="flex items-center justify-center gap-2">
                  <StatusDot connected={false} />
                  <p className="text-[13px] font-medium text-err">Could not connect</p>
                </div>
                <p className="mt-1.5 text-[12.5px] leading-snug text-ink-muted">
                  {message ?? 'Check the endpoint, credentials, and warehouse.'}
                </p>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
