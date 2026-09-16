import { ArrowRightIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLakeGen } from '../../state/LakeGenContext';

const suggestedPrompts = [
  'List my catalogs',
  'Show namespaces in the active catalog',
  'Describe a table',
  'Show recent snapshots',
];

export function AgentEmptyState() {
  const { activeCatalog, catalogs, sendMessage } = useLakeGen();

  if (catalogs.length === 0) {
    return (
      <div className="mx-auto flex max-w-[760px] flex-col justify-center px-8 pb-16 pt-[18vh]">
        <h2 className="text-[19px] font-medium tracking-[-0.015em] text-ink">Connect a catalog to get started.</h2>
        <p className="mt-1.5 text-[14px] leading-[1.6] text-ink-muted">
          LakeGen needs a catalog before it can inspect your lakehouse.
        </p>
        <Link
          to="/catalogs"
          className="mt-5 inline-flex w-fit items-center gap-1.5 rounded-md bg-ink px-3 py-2 text-[13px] font-medium text-white hover:bg-black"
        >
          Add catalog
          <ArrowRightIcon className="h-3.5 w-3.5" strokeWidth={2} />
        </Link>
      </div>
    );
  }

  if (!activeCatalog) {
    return (
      <div className="mx-auto flex max-w-[760px] flex-col justify-center px-8 pb-16 pt-[18vh]">
        <h2 className="text-[19px] font-medium tracking-[-0.015em] text-ink">Select a catalog to get started.</h2>
        <p className="mt-1.5 text-[14px] leading-[1.6] text-ink-muted">
          Choose an active catalog from the Agent header before asking a question.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[760px] flex-col justify-center px-8 pb-16 pt-[18vh]">
      <h2 className="text-[19px] font-medium tracking-[-0.015em] text-ink">Talk to your lakehouse.</h2>
      <p className="mt-1.5 text-[14px] leading-[1.6] text-ink-muted">
        Ask in plain language. LakeGen operates on the active catalog through the agent API.
      </p>

      <div className="mt-7 border-t border-line-soft">
        {suggestedPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => sendMessage(prompt)}
            className="group flex w-full items-center gap-3 border-b border-line-soft py-2.5 text-left transition-colors duration-150 hover:bg-line-soft/50"
          >
            <span className="text-sm text-ink-muted transition-colors group-hover:text-ink">
              {prompt}
            </span>
            <ArrowRightIcon
              className="ml-auto h-3.5 w-3.5 shrink-0 text-ink-faint opacity-0 transition-opacity duration-150 group-hover:opacity-100"
              strokeWidth={2}
            />
          </button>
        ))}
      </div>
    </div>
  );
}
