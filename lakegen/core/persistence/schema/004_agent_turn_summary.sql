-- History summaries live on the turn they compact so one row is the complete
-- record of what the agent saw. `summary` means "history through this turn id
-- is summarized"; raw turns after it are replayed verbatim.
ALTER TABLE agent_turns
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS summary_kind TEXT,
    ADD COLUMN IF NOT EXISTS context_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS context_source TEXT;

CREATE INDEX IF NOT EXISTS agent_turns_session_summary_idx
    ON agent_turns (session_id, id DESC)
    WHERE summary IS NOT NULL;

-- Move the latest legacy compaction for each session onto its turn. The
-- guard keeps later summaries written by the new code from being overwritten.
-- The legacy in-memory tail is intentionally not migrated: raw turns are the
-- canonical history and are replayed verbatim after the summary.
UPDATE agent_turns AS turn
SET summary = latest.data,
    summary_kind = 'history',
    context_source = 'legacy'
FROM (
    SELECT DISTINCT ON (session_id)
           session_id, last_compressed_turn_id, data
    FROM compressions
    ORDER BY session_id, id DESC
) AS latest
WHERE turn.id = latest.last_compressed_turn_id
  AND turn.summary IS NULL;
