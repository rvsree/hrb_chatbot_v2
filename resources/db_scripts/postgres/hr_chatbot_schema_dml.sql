-- ============================================================================
-- hr_chatbot Database DML - Sample Data for HR Benefits Agentic Assistant
-- ============================================================================
-- Purpose: Insert sample data for testing and development
-- Database: hr_chatbot (PostgreSQL)
-- Phase: 1 (MVP - Leave Domain)
-- ============================================================================
-- 
-- IMPORTANT: Run hr_chatbot_schema.sql FIRST before running this DML script
-- This script contains sample data for testing - modify as needed
-- ============================================================================

-- ============================================================================
-- SAMPLE CHAT SESSIONS
-- ============================================================================
-- Insert sample chat sessions for testing

INSERT INTO chat_sessions (user_id, session_id, conversation_goal, current_step, metadata)
VALUES 
    ('emp_12345', 'session_001', 'eligibility_check', 'completed', 
     '{"domain": "leave", "query_type": "parental_leave_eligibility"}'::jsonb),
    
    ('emp_67890', 'session_002', 'application', 'duration_calculation', 
     '{"domain": "leave", "query_type": "parental_leave_application", "event_type": "birth"}'::jsonb),
    
    ('emp_11111', 'session_003', 'policy_qa', 'completed', 
     '{"domain": "leave", "query_type": "fmla_coordination"}'::jsonb)
ON CONFLICT (session_id) DO NOTHING;

-- ============================================================================
-- SAMPLE CHAT HISTORY
-- ============================================================================
-- Insert sample chat history entries for testing

-- Sample conversation 1: Eligibility check
INSERT INTO chat_history (
    session_id, request_id, message_type, role, content, sequence_num,
    domain, agent_type, namespace, response_status, confidence_score,
    sources, tools_used, agent_reasoning, execution_metrics
)
VALUES 
    (
        'session_001',
        'req_001',
        'user_query',
        'user',
        'Am I eligible for parental leave?',
        1,
        'leave',
        'leave_mcp',
        'leave_policies',
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL
    ),
    (
        'session_001',
        'req_001',
        'assistant_response',
        'assistant',
        'Yes, you are eligible for parental leave. You can take up to 16 weeks of paid leave at 100% of your salary. This leave runs concurrent with FMLA, satisfying 12 weeks of FMLA and providing 4 additional weeks of job-protected leave.',
        2,
        'leave',
        'leave_mcp',
        'leave_policies',
        'success',
        0.95,
        ARRAY['JPMC-Paid-TimeOff.pdf:Section-3:Parental-Leave'],
        ARRAY['check_leave_eligibility'],
        '{
            "workflow_id": "eligibility_check_001",
            "steps": [
                {
                    "step": 1,
                    "thought": "Need to check eligibility for parental leave",
                    "action": "check_leave_eligibility",
                    "observation": "Employee eligible for 16 weeks at 100% pay",
                    "policy_citations": ["JPMC-Paid-TimeOff.pdf:Section-3"]
                }
            ],
            "confidence": 0.95
        }'::jsonb,
        '{
            "total_time_ms": 450,
            "llm_calls": 1,
            "total_tokens": 250,
            "total_cost_usd": 0.001
        }'::jsonb
    )
ON CONFLICT DO NOTHING;

-- Sample conversation 2: Application workflow
INSERT INTO chat_history (
    session_id, request_id, message_type, role, content, sequence_num,
    domain, agent_type, namespace, response_status, confidence_score,
    sources, tools_used, agent_reasoning, execution_metrics
)
VALUES 
    (
        'session_002',
        'req_002',
        'user_query',
        'user',
        'I want to apply for parental leave starting June 1st for birth of child',
        1,
        'leave',
        'leave_mcp',
        'leave_policies',
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL
    ),
    (
        'session_002',
        'req_002',
        'assistant_response',
        'assistant',
        'I can help you apply for parental leave. Based on your request, you are eligible for 16 weeks of paid leave at 100% of your salary. I need a few details: 1) Birth certificate or adoption papers, 2) Confirmation of the start date. Would you like to proceed with the application?',
        2,
        'leave',
        'leave_mcp',
        'leave_policies',
        'success',
        0.92,
        ARRAY['JPMC-Paid-TimeOff.pdf:Section-3:Parental-Leave'],
        ARRAY['check_leave_eligibility', 'calculate_leave_duration'],
        '{
            "workflow_id": "parental_leave_application_002",
            "steps": [
                {
                    "step": 1,
                    "action": "check_leave_eligibility",
                    "result": {"eligible": true, "max_duration_weeks": 16}
                },
                {
                    "step": 2,
                    "action": "calculate_leave_duration",
                    "result": {"total_duration_weeks": 16, "pay_structure": {"weeks_1_16": "100%"}}
                }
            ],
            "status": "collection_needed"
        }'::jsonb,
        '{
            "total_time_ms": 1200,
            "llm_calls": 2,
            "total_tokens": 450,
            "total_cost_usd": 0.002
        }'::jsonb
    )
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE USER FEEDBACK
-- ============================================================================
-- Insert sample user feedback for testing

INSERT INTO user_feedback (
    user_id, session_id, request_id, query, response_id,
    feedback_type, rating, feedback_text, is_helpful,
    domain, agent_type, sources_used
)
VALUES 
    (
        'emp_12345',
        'session_001',
        'req_001',
        'Am I eligible for parental leave?',
        'resp_001',
        'thumbs_up',
        5,
        'Very helpful and clear explanation',
        true,
        'leave',
        'leave_mcp',
        ARRAY['JPMC-Paid-TimeOff.pdf:Section-3']
    ),
    (
        'emp_67890',
        'session_002',
        'req_002',
        'I want to apply for parental leave starting June 1st for birth of child',
        'resp_002',
        'rating',
        4,
        'Good guidance, but could be faster',
        true,
        'leave',
        'leave_mcp',
        ARRAY['JPMC-Paid-TimeOff.pdf:Section-3']
    )
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Uncomment to verify data was inserted correctly

-- SELECT session_id, user_id, conversation_goal, current_step 
-- FROM chat_sessions 
-- ORDER BY created_at DESC;

-- SELECT session_id, sequence_num, role, content, confidence_score 
-- FROM chat_history 
-- WHERE session_id = 'session_001'
-- ORDER BY sequence_num;

-- SELECT feedback_type, rating, is_helpful, COUNT(*) 
-- FROM user_feedback 
-- GROUP BY feedback_type, rating, is_helpful;



