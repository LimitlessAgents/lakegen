-- History summaries live on the turn they compact so one row is the complete
-- record of what the agent saw. `summary` means "history through this turn id
-- is summarized". Later turns are replayed exactly as stored (compressed).
-- Legacy compaction rows are moved here by the one-time Python migration,
-- which runs before this file and then drops the old table.
ALTER TABLE agent_turns
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS summary_kind TEXT,
    ADD COLUMN IF NOT EXISTS context_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS context_source TEXT;

CREATE INDEX IF NOT EXISTS agent_turns_session_summary_idx
    ON agent_turns (session_id, id DESC)
    WHERE summary IS NOT NULL;
