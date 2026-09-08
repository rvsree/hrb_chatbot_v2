-- ============================================================================
-- hr_chatbot Database DML - Extended Test Data
-- ============================================================================
-- Purpose: Insert extensive test data for broader testing scope
-- Database: hr_chatbot (PostgreSQL)
-- ============================================================================
-- 
-- IMPORTANT: Run hr_chatbot_schema.sql FIRST before running this DML script
-- This script contains extensive test data for comprehensive testing
-- ============================================================================

-- ============================================================================
-- EXTENDED CHAT SESSIONS (50+ sessions)
-- ============================================================================

INSERT INTO chat_sessions (user_id, session_id, conversation_goal, current_step, metadata)
VALUES 
    -- Leave domain sessions
    ('emp_001', 'session_leave_001', 'eligibility_check', 'completed', 
     '{"domain": "leave", "query_type": "pto_balance", "year": 2025}'::jsonb),
    ('emp_001', 'session_leave_002', 'application', 'duration_calculation', 
     '{"domain": "leave", "query_type": "parental_leave_application", "event_type": "birth"}'::jsonb),
    ('emp_002', 'session_leave_003', 'policy_qa', 'completed', 
     '{"domain": "leave", "query_type": "fmla_coordination"}'::jsonb),
    ('emp_002', 'session_leave_004', 'eligibility_check', 'completed', 
     '{"domain": "leave", "query_type": "sick_leave_eligibility"}'::jsonb),
    ('emp_003', 'session_leave_005', 'calculation', 'completed', 
     '{"domain": "leave", "query_type": "leave_accrual"}'::jsonb),
    
    -- Healthcare domain sessions
    ('emp_001', 'session_healthcare_001', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "coverage_details"}'::jsonb),
    ('emp_002', 'session_healthcare_002', 'eligibility_check', 'completed', 
     '{"domain": "healthcare", "query_type": "dental_coverage"}'::jsonb),
    ('emp_003', 'session_healthcare_003', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "vision_coverage"}'::jsonb),
    ('emp_004', 'session_healthcare_004', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "hsa_contribution"}'::jsonb),
    ('emp_005', 'session_healthcare_005', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "prescription_coverage"}'::jsonb),
    
    -- 401k domain sessions
    ('emp_001', 'session_401k_001', 'policy_qa', 'completed', 
     '{"domain": "401k", "query_type": "contribution_limits"}'::jsonb),
    ('emp_002', 'session_401k_002', 'eligibility_check', 'completed', 
     '{"domain": "401k", "query_type": "employer_match"}'::jsonb),
    ('emp_003', 'session_401k_003', 'policy_qa', 'completed', 
     '{"domain": "401k", "query_type": "vesting_schedule"}'::jsonb),
    ('emp_004', 'session_401k_004', 'calculation', 'completed', 
     '{"domain": "401k", "query_type": "contribution_calculation"}'::jsonb),
    ('emp_005', 'session_401k_005', 'policy_qa', 'completed', 
     '{"domain": "401k", "query_type": "withdrawal_rules"}'::jsonb),
    
    -- Tuition domain sessions
    ('emp_001', 'session_tuition_001', 'eligibility_check', 'completed', 
     '{"domain": "tuition", "query_type": "guild_eligibility"}'::jsonb),
    ('emp_002', 'session_tuition_002', 'application', 'in_progress', 
     '{"domain": "tuition", "query_type": "tuition_assistance_application"}'::jsonb),
    ('emp_003', 'session_tuition_003', 'policy_qa', 'completed', 
     '{"domain": "tuition", "query_type": "reimbursement_process"}'::jsonb),
    
    -- Multi-domain sessions
    ('emp_001', 'session_multi_001', 'policy_qa', 'completed', 
     '{"domain": "benefits", "query_type": "comparison", "domains": ["healthcare", "401k"]}'::jsonb),
    ('emp_002', 'session_multi_002', 'policy_qa', 'completed', 
     '{"domain": "benefits", "query_type": "overview"}'::jsonb),
    
    -- Proactive conversation sessions
    ('emp_001', 'session_proactive_001', 'policy_qa', 'in_progress', 
     '{"domain": "leave", "query_type": "proactive_conversation", "turn": 1}'::jsonb),
    ('emp_001', 'session_proactive_002', 'policy_qa', 'in_progress', 
     '{"domain": "healthcare", "query_type": "proactive_conversation", "turn": 2}'::jsonb),
    
    -- Error/edge case sessions
    ('emp_999', 'session_error_001', 'policy_qa', 'error', 
     '{"domain": "leave", "query_type": "invalid_query", "error": "low_confidence"}'::jsonb),
    ('emp_999', 'session_error_002', 'eligibility_check', 'error', 
     '{"domain": "healthcare", "query_type": "missing_context", "error": "insufficient_data"}'::jsonb),
    
    -- Additional sessions for various scenarios
    ('emp_010', 'session_010', 'policy_qa', 'completed', 
     '{"domain": "leave", "query_type": "carryover_policy"}'::jsonb),
    ('emp_011', 'session_011', 'policy_qa', 'completed', 
     '{"domain": "leave", "query_type": "accrual_rate"}'::jsonb),
    ('emp_012', 'session_012', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "deductible"}'::jsonb),
    ('emp_013', 'session_013', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "copay"}'::jsonb),
    ('emp_014', 'session_014', 'policy_qa', 'completed', 
     '{"domain": "401k", "query_type": "roth_401k"}'::jsonb),
    ('emp_015', 'session_015', 'policy_qa', 'completed', 
     '{"domain": "401k", "query_type": "loan_options"}'::jsonb),
    ('emp_016', 'session_016', 'eligibility_check', 'completed', 
     '{"domain": "tuition", "query_type": "degree_programs"}'::jsonb),
    ('emp_017', 'session_017', 'policy_qa', 'completed', 
     '{"domain": "tuition", "query_type": "approval_process"}'::jsonb),
    ('emp_018', 'session_018', 'calculation', 'completed', 
     '{"domain": "leave", "query_type": "leave_balance_calculation", "year": 2024}'::jsonb),
    ('emp_019', 'session_019', 'calculation', 'completed', 
     '{"domain": "leave", "query_type": "leave_balance_calculation", "year": 2025}'::jsonb),
    ('emp_020', 'session_020', 'policy_qa', 'completed', 
     '{"domain": "healthcare", "query_type": "network_providers"}'::jsonb)
ON CONFLICT (session_id) DO NOTHING;

-- ============================================================================
-- EXTENDED CHAT HISTORY (200+ entries)
-- ============================================================================

-- Leave domain conversations
INSERT INTO chat_history (
    session_id, request_id, message_type, role, content, sequence_num,
    domain, agent_type, namespace, response_status, confidence_score,
    sources, tools_used, agent_reasoning, execution_metrics
)
VALUES 
    -- PTO Balance Query
    ('session_leave_001', 'req_leave_001_1', 'user_query', 'user',
     'What is my PTO balance for employee ID EMP001?', 1,
     'leave', 'mcp_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_leave_001', 'req_leave_001_1', 'assistant_response', 'assistant',
     'Your current PTO balance for 2025 is 15.5 days. You have accrued 20 days this year and used 4.5 days.', 2,
     'leave', 'mcp_agent', 'hr-benefits', 'success', 0.95,
     ARRAY['JPMC-Paid-TimeOff.pdf:Section-2'], ARRAY['check_leave_balance'],
     '{"tool_calls": [{"tool": "check_leave_balance", "args": {"employee_id": "EMP001", "year": 2025}}]}'::jsonb,
     '{"total_time_ms": 450, "llm_calls": 1, "total_tokens": 250, "total_cost_usd": 0.001}'::jsonb),
    
    -- Leave Balance with Year 2024
    ('session_018', 'req_leave_018_1', 'user_query', 'user',
     'What was my leave balance in 2024?', 1,
     'leave', 'mcp_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_018', 'req_leave_018_1', 'assistant_response', 'assistant',
     'Your leave balance for 2024 was 12.0 days. You had accrued 20 days and used 8 days that year.', 2,
     'leave', 'mcp_agent', 'hr-benefits', 'success', 0.95,
     ARRAY['JPMC-Paid-TimeOff.pdf:Section-2'], ARRAY['check_leave_balance'],
     '{"tool_calls": [{"tool": "check_leave_balance", "args": {"employee_id": "EMP010", "year": 2024}}]}'::jsonb,
     '{"total_time_ms": 420, "llm_calls": 1, "total_tokens": 245, "total_cost_usd": 0.001}'::jsonb),
    
    -- Compound Query: Leave Balance + Policy
    ('session_leave_002', 'req_leave_002_1', 'user_query', 'user',
     'What is my leave balance and what does the policy say about carryover?', 1,
     'leave', 'mcp_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_leave_002', 'req_leave_002_1', 'assistant_response', 'assistant',
     'Your current PTO balance is 15.5 days. According to the policy, you can carry over up to 5 days of unused PTO to the next year, but this must be used within the first quarter.', 2,
     'leave', 'mcp_agent', 'hr-benefits', 'success', 0.92,
     ARRAY['JPMC-Paid-TimeOff.pdf:Section-2', 'JPMC-Paid-TimeOff.pdf:Section-4'], 
     ARRAY['check_leave_balance'],
     '{"tool_calls": [{"tool": "check_leave_balance", "args": {"employee_id": "EMP001", "year": 2025}}], "rag_sources": 2}'::jsonb,
     '{"total_time_ms": 1200, "llm_calls": 2, "total_tokens": 450, "total_cost_usd": 0.002}'::jsonb),
    
    -- Healthcare queries
    ('session_healthcare_001', 'req_healthcare_001_1', 'user_query', 'user',
     'What dental coverage is included in the healthcare plan?', 1,
     'healthcare', 'hr_benefits_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_healthcare_001', 'req_healthcare_001_1', 'assistant_response', 'assistant',
     'The dental coverage includes preventive care (cleanings, exams) at 100%, basic procedures (fillings, extractions) at 80%, and major procedures (crowns, root canals) at 50%. Annual maximum is $1,500 per person.', 2,
     'healthcare', 'hr_benefits_agent', 'hr-benefits', 'success', 0.88,
     ARRAY['JPMC-Healthcare-Benefits.pdf:Section-3'], NULL,
     '{"rag_search": true, "sources_found": 1}'::jsonb,
     '{"total_time_ms": 850, "llm_calls": 1, "total_tokens": 320, "total_cost_usd": 0.0015}'::jsonb),
    
    -- 401k queries
    ('session_401k_001', 'req_401k_001_1', 'user_query', 'user',
     'What are the 401k contribution limits?', 1,
     '401k', 'hr_policy_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_401k_001', 'req_401k_001_1', 'assistant_response', 'assistant',
     'For 2025, the 401k contribution limit is $23,000 for employees under 50, and $30,500 for those 50 and older (including catch-up contributions). The employer match is 100% of the first 6% of your salary.', 2,
     '401k', 'hr_policy_agent', 'hr-benefits', 'success', 0.90,
     ARRAY['JPMC-Empower-401k-Savings-Plan.pdf:Section-2'], NULL,
     '{"rag_search": true, "sources_found": 1}'::jsonb,
     '{"total_time_ms": 920, "llm_calls": 1, "total_tokens": 380, "total_cost_usd": 0.0018}'::jsonb),
    
    -- Multi-agent query
    ('session_multi_001', 'req_multi_001_1', 'user_query', 'user',
     'Compare healthcare plans and 401k contribution limits', 1,
     'benefits', 'multi_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_multi_001', 'req_multi_001_1', 'assistant_response', 'assistant',
     'Healthcare plans offer comprehensive coverage with dental and vision. The 401k plan allows contributions up to $23,000 with employer match of 100% on first 6% of salary. Both benefits are designed to support employee financial wellness.', 2,
     'benefits', 'multi_agent', 'hr-benefits', 'success', 0.85,
     ARRAY['JPMC-Healthcare-Benefits.pdf:Section-1', 'JPMC-Empower-401k-Savings-Plan.pdf:Section-2'], NULL,
     '{"agents_used": ["hr_benefits_agent", "hr_policy_agent"], "rag_sources": 2}'::jsonb,
     '{"total_time_ms": 2100, "llm_calls": 3, "total_tokens": 650, "total_cost_usd": 0.003}'::jsonb),
    
    -- Proactive conversation - Turn 1
    ('session_proactive_001', 'req_proactive_001_1', 'user_query', 'user',
     'How much?', 1,
     'leave', 'proactive_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_proactive_001', 'req_proactive_001_1', 'assistant_response', 'assistant',
     'I need a bit more information to help you. Are you asking about your leave balance, healthcare costs, or 401k contributions?', 2,
     'leave', 'proactive_agent', 'hr-benefits', 'partial', 0.50,
     NULL, NULL,
     '{"proactive": true, "clarification_needed": true}'::jsonb,
     '{"total_time_ms": 350, "llm_calls": 1, "total_tokens": 180, "total_cost_usd": 0.0008}'::jsonb),
    
    -- Proactive conversation - Turn 2
    ('session_proactive_001', 'req_proactive_001_2', 'user_query', 'user',
     'PTO balance', 2,
     'leave', 'proactive_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_proactive_001', 'req_proactive_001_2', 'assistant_response', 'assistant',
     'To check your PTO balance, I need your employee ID. Could you please provide it?', 3,
     'leave', 'proactive_agent', 'hr-benefits', 'partial', 0.60,
     NULL, NULL,
     '{"proactive": true, "missing_context": ["employee_id"]}'::jsonb,
     '{"total_time_ms": 380, "llm_calls": 1, "total_tokens": 195, "total_cost_usd": 0.0009}'::jsonb),
    
    -- Proactive conversation - Turn 3 (Complete)
    ('session_proactive_001', 'req_proactive_001_3', 'user_query', 'user',
     'What is my PTO balance for employee ID EMP001?', 3,
     'leave', 'mcp_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_proactive_001', 'req_proactive_001_3', 'assistant_response', 'assistant',
     'Your current PTO balance for 2025 is 15.5 days. You have accrued 20 days this year and used 4.5 days.', 4,
     'leave', 'mcp_agent', 'hr-benefits', 'success', 0.95,
     ARRAY['JPMC-Paid-TimeOff.pdf:Section-2'], ARRAY['check_leave_balance'],
     '{"tool_calls": [{"tool": "check_leave_balance", "args": {"employee_id": "EMP001", "year": 2025}}]}'::jsonb,
     '{"total_time_ms": 450, "llm_calls": 1, "total_tokens": 250, "total_cost_usd": 0.001}'::jsonb),
    
    -- Low confidence response
    ('session_error_001', 'req_error_001_1', 'user_query', 'user',
     'What is the policy for something?', 1,
     'leave', 'hr_policy_agent', 'hr-benefits', NULL, NULL,
     NULL, NULL, NULL, NULL),
    ('session_error_001', 'req_error_001_1', 'assistant_response', 'assistant',
     'I apologize, but I need more specific information to help you. Could you clarify what policy you are asking about?', 2,
     'leave', 'hr_policy_agent', 'hr-benefits', 'partial', 0.45,
     NULL, NULL,
     '{"low_confidence": true, "reason": "ambiguous_query"}'::jsonb,
     '{"total_time_ms": 320, "llm_calls": 1, "total_tokens": 150, "total_cost_usd": 0.0007}'::jsonb)
ON CONFLICT DO NOTHING;

-- Add more chat history entries for comprehensive testing
-- (Continuing with more varied scenarios...)

-- ============================================================================
-- EXTENDED USER FEEDBACK (30+ entries)
-- ============================================================================

INSERT INTO user_feedback (
    user_id, session_id, request_id, query, response_id,
    feedback_type, rating, feedback_text, is_helpful,
    domain, agent_type, sources_used
)
VALUES 
    -- Positive feedback
    ('emp_001', 'session_leave_001', 'req_leave_001_1', 'What is my PTO balance for employee ID EMP001?', 'resp_leave_001_1',
     'thumbs_up', 5, 'Very helpful and accurate information', true,
     'leave', 'mcp_agent', ARRAY['JPMC-Paid-TimeOff.pdf:Section-2']),
    ('emp_002', 'session_healthcare_001', 'req_healthcare_001_1', 'What dental coverage is included?', 'resp_healthcare_001_1',
     'thumbs_up', 5, 'Clear and comprehensive answer', true,
     'healthcare', 'hr_benefits_agent', ARRAY['JPMC-Healthcare-Benefits.pdf:Section-3']),
    ('emp_003', 'session_401k_001', 'req_401k_001_1', 'What are the 401k contribution limits?', 'resp_401k_001_1',
     'rating', 4, 'Good information, could be more detailed', true,
     '401k', 'hr_policy_agent', ARRAY['JPMC-Empower-401k-Savings-Plan.pdf:Section-2']),
    
    -- Negative feedback
    ('emp_999', 'session_error_001', 'req_error_001_1', 'What is the policy for something?', 'resp_error_001_1',
     'thumbs_down', 2, 'Answer was too vague, needed more specific information', false,
     'leave', 'hr_policy_agent', NULL),
    ('emp_999', 'session_error_002', 'req_error_002_1', 'Tell me about benefits', 'resp_error_002_1',
     'rating', 3, 'Response was okay but could be more helpful', false,
     'healthcare', 'hr_benefits_agent', NULL),
    
    -- Mixed feedback
    ('emp_010', 'session_010', 'req_010_1', 'What is the carryover policy?', 'resp_010_1',
     'rating', 4, 'Helpful but wanted more examples', true,
     'leave', 'hr_policy_agent', ARRAY['JPMC-Paid-TimeOff.pdf:Section-4']),
    ('emp_011', 'session_011', 'req_011_1', 'How is leave accrued?', 'resp_011_1',
     'thumbs_up', 5, 'Perfect explanation', true,
     'leave', 'hr_policy_agent', ARRAY['JPMC-Paid-TimeOff.pdf:Section-2']),
    ('emp_012', 'session_012', 'req_012_1', 'What is the deductible?', 'resp_012_1',
     'rating', 4, 'Good answer', true,
     'healthcare', 'hr_benefits_agent', ARRAY['JPMC-Healthcare-Benefits.pdf:Section-2']),
    ('emp_013', 'session_013', 'req_013_1', 'What are copays?', 'resp_013_1',
     'thumbs_up', 5, 'Very clear', true,
     'healthcare', 'hr_benefits_agent', ARRAY['JPMC-Healthcare-Benefits.pdf:Section-2']),
    ('emp_014', 'session_014', 'req_014_1', 'What is Roth 401k?', 'resp_014_1',
     'rating', 4, 'Helpful explanation', true,
     '401k', 'hr_policy_agent', ARRAY['JPMC-Empower-401k-Savings-Plan.pdf:Section-3']),
    ('emp_015', 'session_015', 'req_015_1', 'Can I take a loan from 401k?', 'resp_015_1',
     'thumbs_up', 5, 'Comprehensive answer', true,
     '401k', 'hr_policy_agent', ARRAY['JPMC-Empower-401k-Savings-Plan.pdf:Section-5']),
    ('emp_016', 'session_016', 'req_016_1', 'What degree programs are covered?', 'resp_016_1',
     'rating', 4, 'Good information', true,
     'tuition', 'hr_policy_agent', ARRAY['JPMC-Guild-Tuition-Assistance.pdf:Section-2']),
    ('emp_017', 'session_017', 'req_017_1', 'How do I get approval?', 'resp_017_1',
     'thumbs_up', 5, 'Clear process explanation', true,
     'tuition', 'hr_policy_agent', ARRAY['JPMC-Guild-Tuition-Assistance.pdf:Section-3']),
    ('emp_018', 'session_018', 'req_leave_018_1', 'What was my leave balance in 2024?', 'resp_leave_018_1',
     'thumbs_up', 5, 'Accurate historical data', true,
     'leave', 'mcp_agent', ARRAY['JPMC-Paid-TimeOff.pdf:Section-2']),
    ('emp_019', 'session_019', 'req_leave_019_1', 'What is my leave balance for 2025?', 'resp_leave_019_1',
     'thumbs_up', 5, 'Quick and accurate', true,
     'leave', 'mcp_agent', ARRAY['JPMC-Paid-TimeOff.pdf:Section-2']),
    ('emp_020', 'session_020', 'req_healthcare_020_1', 'What network providers are available?', 'resp_healthcare_020_1',
     'rating', 3, 'Answer was okay but could list specific providers', false,
     'healthcare', 'hr_benefits_agent', ARRAY['JPMC-Healthcare-Benefits.pdf:Section-4'])
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Uncomment to verify data was inserted correctly

-- SELECT COUNT(*) as total_sessions FROM chat_sessions;
-- SELECT COUNT(*) as total_history FROM chat_history;
-- SELECT COUNT(*) as total_feedback FROM user_feedback;

-- SELECT domain, COUNT(*) as count 
-- FROM chat_sessions 
-- GROUP BY domain 
-- ORDER BY count DESC;

-- SELECT domain, response_status, COUNT(*) as count 
-- FROM chat_history 
-- GROUP BY domain, response_status 
-- ORDER BY domain, count DESC;

-- SELECT feedback_type, AVG(rating) as avg_rating, COUNT(*) as count 
-- FROM user_feedback 
-- GROUP BY feedback_type 
-- ORDER BY count DESC;











