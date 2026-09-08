-- ============================================================================
-- hr_chatbot Database Schema for HR Benefits Agentic Assistant
-- ============================================================================
-- Purpose: Conversation management, chat history, user feedback
-- Database: hr_chatbot (PostgreSQL)
-- Phase: 1 (MVP - Leave Domain)
-- ============================================================================

-- Chat Sessions
-- Tracks conversation sessions with goals and current state
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    conversation_goal VARCHAR(100),  -- 'eligibility_check', 'application', 'policy_qa', 'calculation'
    current_step VARCHAR(100),  -- Current step in multi-step workflow
    metadata JSONB,  -- Additional session context
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX idx_chat_sessions_created_at ON chat_sessions(created_at DESC);

-- Chat History
-- Stores complete chat history for analytics and continuity
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL REFERENCES chat_sessions(session_id),
    request_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL,  -- 'user_query', 'assistant_response', 'system_message'
    role VARCHAR(50) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    sequence_num INTEGER NOT NULL,
    
    -- Context
    domain VARCHAR(50),  -- 'leave', 'disability', '401k', 'healthcare', 'tuition'
    agent_type VARCHAR(100),  -- 'leave_mcp', 'orchestrator', 'disability_mcp', etc.
    namespace VARCHAR(100),  -- ChromaDB namespace/collection
    
    -- Response Details
    response_status VARCHAR(50),  -- 'success', 'partial', 'no_hits', 'error'
    confidence_score FLOAT,  -- 0.0-1.0
    sources TEXT[],  -- Document IDs from ChromaDB
    tools_used TEXT[],  -- MCP tools called
    agent_reasoning JSONB,  -- Full reasoning trace (if agent used)
    
    -- Observability
    execution_metrics JSONB,  -- Tokens, costs, timing
    trace_logs JSONB,  -- If trace logging enabled
    explainability JSONB,  -- If explainability enabled
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX idx_chat_history_request_id ON chat_history(request_id);
CREATE INDEX idx_chat_history_user_session ON chat_history(session_id, sequence_num);
CREATE INDEX idx_chat_history_domain ON chat_history(domain);
CREATE INDEX idx_chat_history_created_at ON chat_history(created_at DESC);

-- User Feedback
-- Collects user feedback for continuous improvement
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    request_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    response_id VARCHAR(255) NOT NULL,
    
    -- Feedback Data
    feedback_type VARCHAR(50) NOT NULL,  -- 'thumbs_up', 'thumbs_down', 'rating', 'text', 'issue', 'suggestion'
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    is_helpful BOOLEAN,
    
    -- Context
    domain VARCHAR(50),  -- 'leave', 'disability', '401k', 'healthcare', 'tuition'
    agent_type VARCHAR(100),  -- Which agent handled the query
    sources_used TEXT[],  -- Document IDs referenced
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_feedback_user_id ON user_feedback(user_id);
CREATE INDEX idx_user_feedback_session_id ON user_feedback(session_id);
CREATE INDEX idx_user_feedback_request_id ON user_feedback(request_id);
CREATE INDEX idx_user_feedback_feedback_type ON user_feedback(feedback_type);
CREATE INDEX idx_user_feedback_created_at ON user_feedback(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE chat_sessions IS 'Tracks conversation sessions with goals and current state';
COMMENT ON TABLE chat_history IS 'Stores complete chat history for analytics and continuity';
COMMENT ON TABLE user_feedback IS 'Collects user feedback for continuous improvement';
COMMENT ON COLUMN chat_history.agent_reasoning IS 'Full reasoning trace from agent (thoughts, actions, observations)';
COMMENT ON COLUMN chat_history.execution_metrics IS 'Performance metrics: tokens, costs, timing, retries';



