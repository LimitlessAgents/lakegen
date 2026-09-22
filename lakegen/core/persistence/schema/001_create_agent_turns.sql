CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    name VARCHAR,
    owner_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_turns (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id),
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS agent_turns_session_id_created_at_idx
    ON agent_turns (session_id, created_at);

CREATE INDEX IF NOT EXISTS sessions_owner_created_at_idx
    ON sessions (owner_id, created_at DESC);