-- ============================================================================
-- hr_chatbot Database Schema - HITL Escalations
-- ============================================================================
-- Purpose: Human-in-the-loop escalation tracking
-- Database: hr_chatbot (PostgreSQL)
-- ============================================================================

-- HITL Escalations
-- Tracks escalations to human reviewers
CREATE TABLE IF NOT EXISTS hitl_escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escalation_id VARCHAR(255) UNIQUE NOT NULL,
    employee_id VARCHAR(255),
    session_id VARCHAR(255) REFERENCES chat_sessions(session_id),
    request_id VARCHAR(255) NOT NULL,
    
    -- Escalation Details
    query TEXT NOT NULL,
    reason VARCHAR(100) NOT NULL,  -- 'low_confidence', 'policy_conflict', 'edge_case', 'user_request'
    priority VARCHAR(50) NOT NULL DEFAULT 'normal',  -- 'low', 'normal', 'high', 'urgent'
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_review', 'resolved', 'closed'
    
    -- Context
    context JSONB,  -- Additional context for human reviewer
    agent_reasoning JSONB,  -- Agent reasoning that led to escalation
    original_response TEXT,  -- Original agent response (if any)
    
    -- Assignment
    assigned_to VARCHAR(255),  -- Human reviewer ID/name
    assigned_at TIMESTAMP WITH TIME ZONE,
    
    -- Resolution
    human_response TEXT,
    resolution VARCHAR(50),  -- 'resolved', 'needs_followup', 'referred_to_hr'
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    estimated_response_time VARCHAR(50),  -- '2-4 business hours'
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hitl_escalations_escalation_id ON hitl_escalations(escalation_id);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_employee_id ON hitl_escalations(employee_id);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_session_id ON hitl_escalations(session_id);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_status ON hitl_escalations(status);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_priority ON hitl_escalations(priority);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_assigned_to ON hitl_escalations(assigned_to);
CREATE INDEX IF NOT EXISTS idx_hitl_escalations_created_at ON hitl_escalations(created_at DESC);

COMMENT ON TABLE hitl_escalations IS 'Tracks human-in-the-loop escalations for review and resolution';

