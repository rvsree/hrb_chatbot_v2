-- ============================================================================
-- Error Logs Table Schema
-- ============================================================================
-- Purpose: Store error logs for troubleshooting and analysis
-- Database: hr_chatbot (PostgreSQL)
-- ============================================================================

-- Error Logs Table
CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request Context
    request_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    user_id VARCHAR(255),
    endpoint VARCHAR(255) NOT NULL,
    use_case VARCHAR(100),
    
    -- Error Classification
    error_code VARCHAR(100) NOT NULL,  -- Programmatic error code
    error_type VARCHAR(100) NOT NULL,  -- Exception type name
    error_message TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,  -- validation, network, llm, etc.
    severity VARCHAR(20) NOT NULL,  -- low, medium, high, critical
    
    -- Error Source
    source VARCHAR(50) NOT NULL,  -- router, service, agent, tool, llm, etc.
    component VARCHAR(100),  -- Component name (e.g., "MCPClient", "Orchestrator")
    operation VARCHAR(100),  -- Operation name (e.g., "execute_tool", "chat")
    
    -- Error Details
    stack_trace TEXT,  -- Full stack trace
    error_context JSONB,  -- Additional context (tool_name, args, etc.)
    
    -- Recovery Information
    retryable BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 0,
    recovery_action VARCHAR(50),  -- retry, fallback, fail, continue
    request_continued BOOLEAN DEFAULT FALSE,  -- Did request continue after error?
    
    -- Impact
    request_status VARCHAR(50),  -- success, partial, error, timeout
    user_impact TEXT,  -- How did this affect the user?
    
    -- Resolution Tracking
    resolution_status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, resolved, closed, wont_fix, duplicate
    resolution_comments TEXT,  -- Notes about resolution, fix details, workaround
    resolution_timestamp TIMESTAMP WITH TIME ZONE,  -- When error was resolved
    resolved_by VARCHAR(255),  -- Who resolved it (user_id, system, automated)
    resolution_type VARCHAR(50),  -- fixed, workaround, ignored, duplicate, false_positive
    
    -- Error Correlation & Tracking
    error_fingerprint VARCHAR(255),  -- Hash of error signature for grouping similar errors
    occurrence_count INTEGER DEFAULT 1,  -- How many times this error occurred
    first_occurrence TIMESTAMP WITH TIME ZONE,  -- First time this error was seen
    last_occurrence TIMESTAMP WITH TIME ZONE,  -- Most recent occurrence
    related_error_id UUID,  -- Link to related/parent error
    assigned_to VARCHAR(255),  -- Who is working on this error
    priority VARCHAR(20),  -- p0, p1, p2, p3 (separate from severity)
    tags TEXT[],  -- Custom tags for categorization
    
    -- Environment & Version
    environment VARCHAR(50),  -- dev, staging, prod
    code_version VARCHAR(100),  -- Git commit, version tag
    deployment_id VARCHAR(255),  -- Deployment identifier
    
    -- Notification & SLA
    notification_sent BOOLEAN DEFAULT FALSE,  -- Was alert/notification sent?
    notification_channels TEXT[],  -- email, slack, pagerduty, etc.
    sla_deadline TIMESTAMP WITH TIME ZONE,  -- SLA deadline based on severity
    time_to_resolution_minutes INTEGER,  -- Calculated: resolution_timestamp - created_at
    
    -- Metadata
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_error_logs_request_id ON error_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_session_id ON error_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_error_code ON error_logs(error_code);
CREATE INDEX IF NOT EXISTS idx_error_logs_category ON error_logs(category);
CREATE INDEX IF NOT EXISTS idx_error_logs_severity ON error_logs(severity);
CREATE INDEX IF NOT EXISTS idx_error_logs_source ON error_logs(source);
CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at DESC);

-- Resolution tracking indexes
CREATE INDEX IF NOT EXISTS idx_error_logs_resolution_status ON error_logs(resolution_status);
CREATE INDEX IF NOT EXISTS idx_error_logs_resolution_timestamp ON error_logs(resolution_timestamp);
CREATE INDEX IF NOT EXISTS idx_error_logs_resolved_by ON error_logs(resolved_by);
CREATE INDEX IF NOT EXISTS idx_error_logs_assigned_to ON error_logs(assigned_to);
CREATE INDEX IF NOT EXISTS idx_error_logs_error_fingerprint ON error_logs(error_fingerprint);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_error_logs_troubleshooting ON error_logs(category, severity, source, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_unresolved ON error_logs(resolution_status, severity, created_at DESC) WHERE resolution_status IN ('pending', 'in_progress');
CREATE INDEX IF NOT EXISTS idx_error_logs_environment ON error_logs(environment, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_recurring ON error_logs(error_fingerprint, occurrence_count DESC, last_occurrence DESC);

-- Comments for documentation
COMMENT ON TABLE error_logs IS 'Stores error logs for troubleshooting and analysis';
COMMENT ON COLUMN error_logs.error_fingerprint IS 'Hash of error signature for grouping similar errors';
COMMENT ON COLUMN error_logs.occurrence_count IS 'Number of times this error occurred (updated for duplicate errors)';
COMMENT ON COLUMN error_logs.resolution_status IS 'Error resolution status: pending, in_progress, resolved, closed, wont_fix, duplicate';
COMMENT ON COLUMN error_logs.resolution_type IS 'Type of resolution: fixed, workaround, ignored, duplicate, false_positive';
