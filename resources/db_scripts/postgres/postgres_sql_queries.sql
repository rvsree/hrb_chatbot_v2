-- ============================================================================
-- PostgreSQL SQL Queries for Agent Memory
-- ============================================================================
-- This file contains all SQL DML statements used by postgres_db_client.py.
-- Queries are identified by -- NAME: markers and loaded at runtime.
--
-- Naming Convention:
--   - INSERT_* : Insert operations
--   - SELECT_* : Read operations
--   - UPDATE_* : Update operations
--   - DELETE_* : Delete operations
--
-- Note: PostgreSQL uses %s for parameters, but we use named parameters
-- with psycopg's %(name)s syntax for clarity.
-- ============================================================================


-- ============================================================================
-- LONG-TERM MEMORY (LTM) OPERATIONS
-- ============================================================================

-- NAME: INSERT_LTM_MEMORY
INSERT INTO agent_ltm (
    id,
    user_id,
    memory_type,
    content,
    metadata,
    created_at,
    updated_at
) VALUES (
    %(id)s,
    %(user_id)s,
    %(memory_type)s,
    %(content)s,
    %(metadata)s,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_LTM_BY_USER
SELECT 
    id,
    user_id,
    memory_type,
    content,
    metadata,
    created_at,
    updated_at
FROM agent_ltm
WHERE user_id = %(user_id)s
ORDER BY created_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: SELECT_LTM_BY_USER_AND_TYPE
SELECT 
    id,
    user_id,
    memory_type,
    content,
    metadata,
    created_at,
    updated_at
FROM agent_ltm
WHERE user_id = %(user_id)s 
  AND memory_type = %(memory_type)s
ORDER BY created_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: DELETE_LTM_BY_ID
DELETE FROM agent_ltm
WHERE id = %(id)s

-- NAME: DELETE_LTM_BY_USER
DELETE FROM agent_ltm
WHERE user_id = %(user_id)s


-- ============================================================================
-- ENTITY MEMORY OPERATIONS
-- ============================================================================

-- NAME: INSERT_ENTITY
INSERT INTO agent_entities (
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    metadata,
    first_mentioned_at,
    last_mentioned_at,
    mention_count
) VALUES (
    %(id)s,
    %(entity_name)s,
    %(entity_type)s,
    %(description)s,
    %(source_context)s,
    %(metadata)s,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    1
)

-- NAME: SELECT_ENTITY_BY_NAME
SELECT 
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    first_mentioned_at,
    last_mentioned_at,
    mention_count,
    metadata
FROM agent_entities
WHERE entity_name = %(entity_name)s

-- NAME: UPDATE_ENTITY_MENTION
UPDATE agent_entities
SET 
    description = COALESCE(%(description)s, description),
    source_context = COALESCE(%(source_context)s, source_context),
    last_mentioned_at = CURRENT_TIMESTAMP,
    mention_count = mention_count + 1
WHERE id = %(id)s

-- NAME: SELECT_ENTITIES_BY_TYPE
SELECT 
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    first_mentioned_at,
    last_mentioned_at,
    mention_count,
    metadata
FROM agent_entities
WHERE entity_type = %(entity_type)s
ORDER BY mention_count DESC, last_mentioned_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: SELECT_ENTITIES_BY_SEARCH
SELECT 
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    first_mentioned_at,
    last_mentioned_at,
    mention_count,
    metadata
FROM agent_entities
WHERE entity_name ILIKE %(search_term)s
ORDER BY mention_count DESC, last_mentioned_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: SELECT_ENTITIES_BY_TYPE_AND_SEARCH
SELECT 
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    first_mentioned_at,
    last_mentioned_at,
    mention_count,
    metadata
FROM agent_entities
WHERE entity_type = %(entity_type)s
  AND entity_name ILIKE %(search_term)s
ORDER BY mention_count DESC, last_mentioned_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: SELECT_ALL_ENTITIES
SELECT 
    id,
    entity_name,
    entity_type,
    description,
    source_context,
    first_mentioned_at,
    last_mentioned_at,
    mention_count,
    metadata
FROM agent_entities
ORDER BY mention_count DESC, last_mentioned_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: DELETE_ENTITY_BY_ID
DELETE FROM agent_entities
WHERE id = %(id)s


-- ============================================================================
-- CONVERSATION HISTORY OPERATIONS
-- ============================================================================

-- NAME: INSERT_CONVERSATION_MESSAGE
INSERT INTO agent_conversations (
    id,
    thread_id,
    user_id,
    role,
    content,
    tool_calls,
    created_at
) VALUES (
    %(id)s,
    %(thread_id)s,
    %(user_id)s,
    %(role)s,
    %(content)s,
    %(tool_calls)s,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_CONVERSATION_BY_THREAD
SELECT 
    id,
    thread_id,
    user_id,
    role,
    content,
    tool_calls,
    created_at
FROM agent_conversations
WHERE thread_id = %(thread_id)s
ORDER BY created_at ASC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: SELECT_CONVERSATION_BY_USER
SELECT 
    id,
    thread_id,
    user_id,
    role,
    content,
    tool_calls,
    created_at
FROM agent_conversations
WHERE user_id = %(user_id)s
ORDER BY created_at DESC
LIMIT %(limit)s OFFSET %(offset)s

-- NAME: DELETE_CONVERSATION_BY_THREAD
DELETE FROM agent_conversations
WHERE thread_id = %(thread_id)s

-- NAME: COUNT_MESSAGES_BY_THREAD
SELECT COUNT(*) AS message_count
FROM agent_conversations
WHERE thread_id = %(thread_id)s

