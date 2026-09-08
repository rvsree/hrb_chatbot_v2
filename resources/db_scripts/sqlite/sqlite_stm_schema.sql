-- ============================================================================
-- SQLite Schema for Agent Short-Term Memory (STM)
-- ============================================================================
-- This file contains DDL for agent session and STM tables.
-- SQLite is used for ephemeral, session-based memory that doesn't need
-- to persist across server restarts.
--
-- Tables:
--   - agent_sessions: Active conversation sessions
--   - agent_stm: Short-term memory within sessions
--   - agent_checkpoints: LangGraph state checkpoints
-- ============================================================================


-- ============================================================================
-- AGENT SESSIONS
-- ============================================================================
-- Tracks active agent conversation sessions.

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    user_id TEXT,
    agent_type TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    UNIQUE(thread_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_thread ON agent_sessions(thread_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON agent_sessions(status);


-- ============================================================================
-- SHORT-TERM MEMORY (STM)
-- ============================================================================
-- Stores recent messages and context within a session.
-- This is cleared when session ends or after TTL expires.

CREATE TABLE IF NOT EXISTS agent_stm (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_type TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    tool_name TEXT,
    tool_input TEXT,
    tool_output TEXT,
    sequence_num INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stm_session ON agent_stm(session_id);
CREATE INDEX IF NOT EXISTS idx_stm_sequence ON agent_stm(session_id, sequence_num);


-- ============================================================================
-- LANGGRAPH STATE CHECKPOINTS
-- ============================================================================
-- Stores serialized graph state for LangGraph agents.
-- Used by MemorySaver/SqliteSaver for state persistence.

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT DEFAULT '',
    parent_checkpoint_id TEXT,
    checkpoint_data TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, checkpoint_ns)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON agent_checkpoints(thread_id);


-- ============================================================================
-- PENDING WRITES (for LangGraph)
-- ============================================================================
-- Stores pending writes for LangGraph checkpoint system.

CREATE TABLE IF NOT EXISTS agent_pending_writes (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    write_type TEXT NOT NULL,
    write_data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pending_thread ON agent_pending_writes(thread_id, checkpoint_id);

