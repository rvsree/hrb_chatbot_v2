-- ============================================================================
-- PostgreSQL Schema for Agent Memory
-- ============================================================================
-- This file contains DDL for agent memory tables:
--   - agent_ltm: Long-Term Memory storage
--   - agent_entities: Named entity memory
--   - agent_conversations: Conversation history (for analytics)
--
-- Tables are designed for agent persistence and memory management.
-- ============================================================================


-- ============================================================================
-- LONG-TERM MEMORY (LTM)
-- ============================================================================
-- Stores persistent facts, preferences, and learned information about users.
-- Memory types: 'fact', 'preference', 'history', 'learned'

CREATE TABLE IF NOT EXISTS agent_ltm (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_agent_ltm_user_id 
    ON agent_ltm(user_id);

-- Index for filtering by memory type
CREATE INDEX IF NOT EXISTS idx_agent_ltm_user_type 
    ON agent_ltm(user_id, memory_type);

-- Index for timestamp-based queries
CREATE INDEX IF NOT EXISTS idx_agent_ltm_created 
    ON agent_ltm(created_at DESC);


-- ============================================================================
-- ENTITY MEMORY
-- ============================================================================
-- Tracks named entities mentioned in conversations.
-- Entity types: 'document', 'person', 'organization', 'concept', 'date', 'location'

CREATE TABLE IF NOT EXISTS agent_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    description TEXT,
    source_context TEXT,
    first_mentioned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_mentioned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    metadata JSONB,
    CONSTRAINT uq_entity_name UNIQUE (entity_name)
);

-- Index for entity name lookups
CREATE INDEX IF NOT EXISTS idx_agent_entities_name 
    ON agent_entities(entity_name);

-- Index for filtering by type
CREATE INDEX IF NOT EXISTS idx_agent_entities_type 
    ON agent_entities(entity_type);

-- Index for frequently mentioned entities
CREATE INDEX IF NOT EXISTS idx_agent_entities_mentions 
    ON agent_entities(mention_count DESC);


-- ============================================================================
-- CONVERSATION HISTORY
-- ============================================================================
-- Persistent storage of conversation messages for analytics and auditing.
-- Note: Short-term session state uses SQLite; this is for long-term storage.

CREATE TABLE IF NOT EXISTS agent_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for thread lookups
CREATE INDEX IF NOT EXISTS idx_agent_conv_thread 
    ON agent_conversations(thread_id);

-- Index for user history
CREATE INDEX IF NOT EXISTS idx_agent_conv_user 
    ON agent_conversations(user_id);

-- Index for chronological ordering within thread
CREATE INDEX IF NOT EXISTS idx_agent_conv_thread_time 
    ON agent_conversations(thread_id, created_at);


-- ============================================================================
-- UPDATE TRIGGER FOR LTM
-- ============================================================================
-- Automatically update the updated_at timestamp

CREATE OR REPLACE FUNCTION update_ltm_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_ltm_timestamp ON agent_ltm;

CREATE TRIGGER trigger_update_ltm_timestamp
    BEFORE UPDATE ON agent_ltm
    FOR EACH ROW
    EXECUTE FUNCTION update_ltm_timestamp();

