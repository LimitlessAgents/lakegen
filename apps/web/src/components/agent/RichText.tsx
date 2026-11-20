import { Children, createContext, isValidElement, useContext, type ReactElement, type ReactNode } from 'react';
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

type ElementWithChildren = ReactElement<{ children?: ReactNode }>;

function elementChildren(node: ReactNode): ElementWithChildren[] {
  return Children.toArray(node).filter((child): child is ElementWithChildren =>
    isValidElement<{ children?: ReactNode }>(child),
  );
}

/** The header row defines the column count used to repair short body rows. */
function countTableColumns(children: ReactNode): number {
  for (const section of elementChildren(children)) {
    for (const row of elementChildren(section.props.children)) {
      const cells = elementChildren(row.props.children);
      if (cells.length > 0) return cells.length;
    }
  }
  return 0;
}

const TableColumnsContext = createContext(0);
const RowCellCountContext = createContext(0);
const CellIndexContext = createContext(0);

function codeBlockInfo(node: ReactNode): { text: string; language: string | null } {
  if (isValidElement<{ className?: string; children?: ReactNode }>(node)) {
    const className = node.props.className ?? '';
    const language = /language-([\w+#-]+)/.exec(className)?.[1] ?? null;
    return { text: textFromNode(node.props.children).replace(/\n$/, ''), language };
  }
  return { text: textFromNode(node), language: null };
}

/** Numeric cells align right so columns of counts and sizes can be scanned. */
const NUMERIC_CELL = /^[\s$€£¥]?[+-]?(?:\d[\d,._/-]*\s*)+[%a-zA-Z]*$/;

/** Split a GFM table row into trimmed cells, honoring escaped pipes. */
function splitTableRow(line: string): string[] {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);

  const cells: string[] = [];
  let cell = '';
  for (let i = 0; i < row.length; i += 1) {
    const char = row[i];
    if (char === '\\' && row[i + 1] === '|') {
      cell += '|';
      i += 1;
    } else if (char === '|') {
      cells.push(cell.trim());
      cell = '';
    } else {
      cell += char;
    }
  }
  cells.push(cell.trim());
  return cells;
}

function isDelimiterRow(line: string | undefined): boolean {
  if (!line || !line.includes('|') || !line.includes('-')) return false;
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-+:?$/.test(cell));
}

function isTableRow(line: string): boolean {
  return line.includes('|') && line.trim().length > 0;
}

/**
 * A GFM table body row with fewer cells than the header is malformed — usually
 * a stray sentence that belongs to the answer, not the grid. remark pads such a
 * row with empty cells, which renders as one wide first column and shifts the
 * rest of the table. Lift those rows out and emit them after the table as prose
 * so every table keeps a consistent column count.
 */
function liftTableNotes(markdown: string): string {
  if (!markdown.includes('|')) return markdown;

  const lines = markdown.split('\n');
  const out: string[] = [];
  let fence: string | null = null;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const fenceMatch = /^\s*(`{3,}|~{3,})/.exec(line);
    if (fenceMatch) {
      const marker = fenceMatch[1][0];
      fence = fence === null ? marker : fence === marker ? null : fence;
      out.push(line);
      i += 1;
      continue;
    }
    if (fence !== null) {
      out.push(line);
      i += 1;
      continue;
    }

    if (isTableRow(line) && isDelimiterRow(lines[i + 1])) {
      const columns = splitTableRow(line).length;
      out.push(line, lines[i + 1]);
      i += 2;

      const notes: string[] = [];
      while (i < lines.length && isTableRow(lines[i]) && !isDelimiterRow(lines[i])) {
        const cells = splitTableRow(lines[i]);
        if (columns > 1 && cells.length < columns) {
          const note = cells.filter(Boolean).join(' ').trim();
          if (note) notes.push(note);
        } else {
          out.push(lines[i]);
        }
        i += 1;
      }

      if (notes.length > 0) out.push('', notes.join('\n\n'));
      continue;
    }

    out.push(line);
    i += 1;
  }

  return out.join('\n');
}

function MarkdownContent({ text }: { text: string }) {
  const { notify } = useToast();
  const components: Components = {
    a: ({ children, href }) => (
      <a
        href={href}
        className="text-accent underline decoration-accent/30 underline-offset-2 transition-colors hover:decoration-accent"
      >
        {children}
      </a>
    ),
    p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
    h1: ({ children }) => (
      <h1 className="mb-2.5 mt-6 text-xl font-semibold tracking-[-0.02em] text-ink first:mt-0 last:mb-0">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="mb-2 mt-5 text-lg font-semibold tracking-[-0.01em] text-ink first:mt-0 last:mb-0">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="mb-1.5 mt-4 text-base font-semibold text-ink first:mt-0 last:mb-0">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="mb-1.5 mt-4 text-sm font-semibold text-ink first:mt-0 last:mb-0">
        {children}
      </h4>
    ),
    ul: ({ children }) => (
      <ul className="my-3 list-disc pl-5 marker:text-ink-faint last:mb-0 [&_ol]:my-1.5 [&_ul]:my-1.5">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="my-3 list-decimal space-y-1 pl-5 marker:text-ink-faint last:mb-0 [&_ol]:my-1.5 [&_ul]:my-1.5">
        {children}
      </ol>
    ),
    li: ({ children }) => (
      <li className="pl-0.5 [&>p:last-child]:mb-0">{children}</li>
    ),
    blockquote: ({ children }) => (
      <blockquote className="my-3 border-l-2 border-accent/60 pl-3.5 text-ink-muted last:mb-0 [&>p:last-child]:mb-0">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="my-5 border-t border-line-strong" />,
    img: ({ src, alt, title }) => (
      <img
        src={src}
        alt={alt ?? ''}
        title={title}
        className="my-3 max-w-full rounded-lg border border-line"
      />
    ),
    del: ({ children }) => <del className="text-ink-muted">{children}</del>,
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
      const { text: code, language } = codeBlockInfo(children);
      return (
        <div className="my-3 overflow-hidden rounded-lg border border-line last:mb-0">
          <div className="flex items-center justify-between gap-3 border-b border-line bg-line-soft px-3 py-1.5">
            <span className="font-mono text-2xs text-ink-muted">{language ?? 'code'}</span>
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
                className="inline-flex h-6 items-center gap-1 rounded px-1.5 text-2xs font-medium text-ink-muted transition-colors hover:bg-panel hover:text-ink"
                aria-label="Copy code"
              >
                <CopyIcon className="h-3 w-3" strokeWidth={2} />
                Copy
              </button>
            )}
          </div>
          <pre className="overflow-x-auto bg-line-soft/40 p-3 font-mono text-[12px] leading-[1.6] text-ink">
            {children}
          </pre>
        </div>
      );
    },
    strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
    table: ({ children }) => {
      const columns = countTableColumns(children);
      return (
        <div className="my-3 overflow-x-auto rounded-lg border border-line bg-panel last:mb-0">
          <table className="w-full border-collapse text-left">
            <TableColumnsContext.Provider value={columns}>{children}</TableColumnsContext.Provider>
          </table>
        </div>
      );
    },
    thead: ({ children }) => (
      <thead className="border-b border-line bg-canvas">{children}</thead>
    ),
    tbody: ({ children }) => (
      <tbody className="[&>tr:last-child]:border-0">{children}</tbody>
    ),
    tr: ({ children }) => {
      const columns = useContext(TableColumnsContext);
      const cells = elementChildren(children);
      const filled = cells.filter((cell) => textFromNode(cell.props.children).trim().length > 0);
      // GFM pads short rows with empty cells. When a row carries one leading
      // value (typically a note), drop the padding and let that cell span the row.
      const isNoteRow =
        columns > 1 && cells.length > 1 && filled.length === 1 && filled[0] === cells[0];
      const rendered = isNoteRow ? [cells[0]] : cells;

      return (
        <tr className="border-b border-line-soft">
          <RowCellCountContext.Provider value={rendered.length}>
            {rendered.map((cell, index) => (
              <CellIndexContext.Provider key={index} value={index}>
                {cell}
              </CellIndexContext.Provider>
            ))}
          </RowCellCountContext.Provider>
        </tr>
      );
    },
    th: ({ children, style }) => (
      <th
        scope="col"
        style={style}
        className="border-r border-line-soft px-3 py-1.5 align-bottom text-2xs font-medium uppercase tracking-wider text-ink-faint last:border-r-0"
      >
        {children}
      </th>
    ),
    td: ({ children, style }) => {
      const columns = useContext(TableColumnsContext);
      const rowCells = useContext(RowCellCountContext);
      const index = useContext(CellIndexContext);
      const content = textFromNode(children).trim();
      const isNumeric = content.length > 0 && NUMERIC_CELL.test(content);
      const span =
        rowCells > 0 && rowCells < columns && index === rowCells - 1 ? columns - index : undefined;
      const cellClass = isNumeric
        ? 'whitespace-nowrap text-right font-mono'
        : span
          ? 'break-words border-r-0 bg-canvas text-left font-sans text-ink-muted'
          : 'break-words text-left font-mono';

      return (
        <td
          colSpan={span}
          style={style}
          className={`border-r border-line-soft px-3 py-1.5 align-top text-sm tabular-nums text-ink last:border-r-0 ${cellClass}`}
        >
          {children}
        </td>
      );
    },
  };

  return (
    <Markdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
      {liftTableNotes(text)}
    </Markdown>
  );
}

export function RichText({ text }: { text: string }) {
  return (
    <div className="break-words text-[14px] leading-[1.65] text-ink">
      <MarkdownContent text={text} />
    </div>
  );
}
