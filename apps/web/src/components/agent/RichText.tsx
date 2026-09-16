import { isValidElement, type ReactNode } from 'react';
import { CopyIcon } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { canCopyText, copyText } from '../../lib/clipboard';
import { useToast } from '../ui/Toast';

function textFromNode(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textFromNode).join('');
  return isValidElement<{ children?: ReactNode }>(node) ? textFromNode(node.props.children) : '';
}

function MarkdownContent({ text }: { text: string }) {
  const { notify } = useToast();
  const components: Components = {
  h2: ({ children }) => (
    <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-[13px] font-semibold text-ink">{children}</h3>
  ),
  ul: ({ children }) => (
    <ul className="list-none space-y-1.5 [&>li]:relative [&>li]:pl-3.5 [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[9px] [&>li]:before:h-[3px] [&>li]:before:w-[3px] [&>li]:before:rounded-full [&>li]:before:bg-ink-faint">
      {children}
    </ul>
  ),
  code: ({ className, children }) => {
    if (className) {
      return <code className={`${className} font-mono text-[12px] text-ink`}>{children}</code>;
    }
    return (
      <code className="rounded-[4px] border border-line bg-line-soft/70 px-1 py-[1px] font-mono text-[12px] text-ink">
        {children}
      </code>
    );
  },
  pre: ({ children }) => {
    const code = textFromNode(children);
    return (
      <div className="group relative">
        {canCopyText() && (
          <button
            type="button"
            onClick={() => {
              void copyText(code).then((copied) => {
                notify({
                  tone: copied ? 'success' : 'error',
                  message: copied ? 'Code copied.' : 'Could not copy the code.',
                });
              });
            }}
            className="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded bg-panel/90 text-ink-faint opacity-0 shadow-subtle transition-opacity hover:text-ink focus:opacity-100 group-hover:opacity-100"
            aria-label="Copy code"
          >
            <CopyIcon className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        )}
        <pre className="overflow-x-auto rounded-md border border-line bg-line-soft/70 p-3 font-mono text-[12px] leading-[1.55] text-ink">
          {children}
        </pre>
      </div>
    );
  },
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  table: ({ children }) => (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-line bg-canvas">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="[&>tr:last-child]:border-0">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="border-b border-line-soft">{children}</tr>
  ),
  th: ({ children }) => (
    <th
      scope="col"
      className="whitespace-nowrap border-r border-line-soft px-3 py-1.5 text-2xs font-medium uppercase tracking-wider text-ink-faint last:border-r-0"
    >
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="whitespace-nowrap border-r border-line-soft px-3 py-1.5 font-mono text-sm text-ink last:border-r-0">
      {children}
    </td>
  ),
  };

  return (
    <Markdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
      {text}
    </Markdown>
  );
}

export function RichText({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-[14px] leading-[1.65] text-ink">
      <MarkdownContent text={text} />
    </div>
  );
}
