-- ============================================================================
-- SQLite SQL Queries for Agent Short-Term Memory (STM)
-- ============================================================================
-- This file contains DML statements for STM operations.
-- Queries are identified by -- NAME: markers.
-- ============================================================================


-- ============================================================================
-- SESSION OPERATIONS
-- ============================================================================

-- NAME: INSERT_SESSION
INSERT INTO agent_sessions (
    id,
    thread_id,
    user_id,
    agent_type,
    status,
    metadata,
    started_at,
    last_activity_at
) VALUES (
    :id,
    :thread_id,
    :user_id,
    :agent_type,
    'active',
    :metadata,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_SESSION_BY_THREAD
SELECT 
    id,
    thread_id,
    user_id,
    agent_type,
    status,
    started_at,
    last_activity_at,
    metadata
FROM agent_sessions
WHERE thread_id = :thread_id

-- NAME: UPDATE_SESSION_ACTIVITY
UPDATE agent_sessions
SET last_activity_at = CURRENT_TIMESTAMP
WHERE thread_id = :thread_id

-- NAME: UPDATE_SESSION_STATUS
UPDATE agent_sessions
SET status = :status,
    last_activity_at = CURRENT_TIMESTAMP
WHERE thread_id = :thread_id

-- NAME: DELETE_SESSION
DELETE FROM agent_sessions
WHERE thread_id = :thread_id

-- NAME: SELECT_ACTIVE_SESSIONS
SELECT 
    id,
    thread_id,
    user_id,
    agent_type,
    status,
    started_at,
    last_activity_at,
    metadata
FROM agent_sessions
WHERE status = 'active'
ORDER BY last_activity_at DESC
LIMIT :limit OFFSET :offset

-- NAME: DELETE_EXPIRED_SESSIONS
DELETE FROM agent_sessions
WHERE status = 'active'
  AND datetime(last_activity_at) < datetime('now', :ttl_interval)


-- ============================================================================
-- STM MESSAGE OPERATIONS
-- ============================================================================

-- NAME: INSERT_STM_MESSAGE
INSERT INTO agent_stm (
    id,
    session_id,
    message_type,
    role,
    content,
    tool_name,
    tool_input,
    tool_output,
    sequence_num,
    created_at
) VALUES (
    :id,
    :session_id,
    :message_type,
    :role,
    :content,
    :tool_name,
    :tool_input,
    :tool_output,
    :sequence_num,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_STM_BY_SESSION
SELECT 
    id,
    session_id,
    message_type,
    role,
    content,
    tool_name,
    tool_input,
    tool_output,
    sequence_num,
    created_at
FROM agent_stm
WHERE session_id = :session_id
ORDER BY sequence_num ASC
LIMIT :limit OFFSET :offset

-- NAME: SELECT_RECENT_STM
SELECT 
    id,
    session_id,
    message_type,
    role,
    content,
    tool_name,
    tool_input,
    tool_output,
    sequence_num,
    created_at
FROM agent_stm
WHERE session_id = :session_id
ORDER BY sequence_num DESC
LIMIT :limit

-- NAME: GET_NEXT_SEQUENCE_NUM
SELECT COALESCE(MAX(sequence_num), 0) + 1 AS next_seq
FROM agent_stm
WHERE session_id = :session_id

-- NAME: DELETE_STM_BY_SESSION
DELETE FROM agent_stm
WHERE session_id = :session_id

-- NAME: COUNT_STM_MESSAGES
SELECT COUNT(*) AS message_count
FROM agent_stm
WHERE session_id = :session_id


-- ============================================================================
-- CHECKPOINT OPERATIONS (for LangGraph)
-- ============================================================================

-- NAME: UPSERT_CHECKPOINT
INSERT INTO agent_checkpoints (
    id,
    thread_id,
    checkpoint_ns,
    parent_checkpoint_id,
    checkpoint_data,
    metadata,
    created_at
) VALUES (
    :id,
    :thread_id,
    :checkpoint_ns,
    :parent_checkpoint_id,
    :checkpoint_data,
    :metadata,
    CURRENT_TIMESTAMP
)
ON CONFLICT(thread_id, checkpoint_ns) DO UPDATE SET
    parent_checkpoint_id = excluded.parent_checkpoint_id,
    checkpoint_data = excluded.checkpoint_data,
    metadata = excluded.metadata,
    created_at = CURRENT_TIMESTAMP

-- NAME: SELECT_CHECKPOINT
SELECT 
    id,
    thread_id,
    checkpoint_ns,
    parent_checkpoint_id,
    checkpoint_data,
    metadata,
    created_at
FROM agent_checkpoints
WHERE thread_id = :thread_id
  AND checkpoint_ns = :checkpoint_ns

-- NAME: SELECT_LATEST_CHECKPOINT
SELECT 
    id,
    thread_id,
    checkpoint_ns,
    parent_checkpoint_id,
    checkpoint_data,
    metadata,
    created_at
FROM agent_checkpoints
WHERE thread_id = :thread_id
ORDER BY created_at DESC
LIMIT 1

-- NAME: DELETE_CHECKPOINTS_BY_THREAD
DELETE FROM agent_checkpoints
WHERE thread_id = :thread_id


-- ============================================================================
-- PENDING WRITES OPERATIONS (for LangGraph)
-- ============================================================================

-- NAME: INSERT_PENDING_WRITE
INSERT INTO agent_pending_writes (
    id,
    thread_id,
    checkpoint_ns,
    checkpoint_id,
    task_id,
    channel,
    write_type,
    write_data,
    created_at
) VALUES (
    :id,
    :thread_id,
    :checkpoint_ns,
    :checkpoint_id,
    :task_id,
    :channel,
    :write_type,
    :write_data,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_PENDING_WRITES
SELECT 
    id,
    thread_id,
    checkpoint_ns,
    checkpoint_id,
    task_id,
    channel,
    write_type,
    write_data,
    created_at
FROM agent_pending_writes
WHERE thread_id = :thread_id
  AND checkpoint_id = :checkpoint_id
ORDER BY created_at ASC

-- NAME: DELETE_PENDING_WRITES
DELETE FROM agent_pending_writes
WHERE thread_id = :thread_id
  AND checkpoint_id = :checkpoint_id

