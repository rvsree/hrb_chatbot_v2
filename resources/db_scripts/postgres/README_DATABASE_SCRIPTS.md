# Database Scripts - HR Benefits Agentic Assistant

**Version:** 1.2  
**Date:** January 18, 2025

---

## Overview

This directory contains DDL (Data Definition Language) and DML (Data Manipulation Language) scripts for the HR Benefits Agentic Assistant databases.

---

## Database Scripts

### coco Database (PostgreSQL)

**Purpose**: Transactional data, structured rules, agent task tracking

#### DDL Scripts
- **`coco_schema_extensions.sql`** - Creates tables: `policy_versions`, `leave_rules`, `agent_tasks`, extends `leave_requests`

#### DML Scripts
- **`coco_schema_dml.sql`** - Inserts initial data:
  - Policy versions for all 5 domains (leave, disability, 401k, healthcare, tuition)
  - Leave rules based on JPMC policies:
    - Parental leave (16 weeks, 100% pay)
    - Critical caregiver (4 weeks, unpaid)
    - FMLA (12 weeks, unpaid, service requirements)
    - Sick leave rules
    - Bereavement leave rules
    - Coordination rules

**Usage**:
```bash
# 1. Run DDL first
psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_extensions.sql

# 2. Then run DML for initial data
psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_dml.sql
```

---

### hr_chatbot Database (PostgreSQL)

**Purpose**: Conversation management, chat history, user feedback

#### DDL Scripts
- **`hr_chatbot_schema.sql`** - Creates tables: `chat_sessions`, `chat_history`, `user_feedback`

#### DML Scripts
- **`hr_chatbot_schema_dml.sql`** - Inserts sample data:
  - Sample chat sessions (3 sessions)
  - Sample chat history (2 conversations with full reasoning traces)
  - Sample user feedback (2 feedback entries)

**Usage**:
```bash
# 1. Run DDL first
psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema.sql

# 2. Then run DML for sample data (optional, for testing)
psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema_dml.sql
```

---

## Script Execution Order

### For Fresh Database Setup

1. **coco Database**:
   ```bash
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_extensions.sql
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_dml.sql
   ```

2. **hr_chatbot Database**:
   ```bash
   psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema.sql
   psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema_dml.sql
   ```

### For Production

- Run DDL scripts only (DML scripts are for testing/development)
- Initial policy versions and rules should be loaded from actual policy documents
- Use data migration scripts for production data

---

## Data Verification

After running scripts, verify data with:

### coco Database
```sql
-- Check policy versions
SELECT policy_type, version, effective_date, source_doc_name 
FROM policy_versions 
ORDER BY policy_type, version;

-- Check leave rules
SELECT leave_type_name, attribute, value, priority 
FROM leave_rules 
WHERE leave_type_name = 'parental_leave'
ORDER BY priority DESC, attribute;

-- Count rules by type
SELECT leave_type_name, COUNT(*) as rule_count
FROM leave_rules
GROUP BY leave_type_name
ORDER BY leave_type_name;
```

### hr_chatbot Database
```sql
-- Check chat sessions
SELECT session_id, user_id, conversation_goal, current_step 
FROM chat_sessions 
ORDER BY created_at DESC;

-- Check chat history
SELECT session_id, sequence_num, role, content, confidence_score 
FROM chat_history 
WHERE session_id = 'session_001'
ORDER BY sequence_num;

-- Check feedback
SELECT feedback_type, rating, is_helpful, COUNT(*) 
FROM user_feedback 
GROUP BY feedback_type, rating, is_helpful;
```

---

## Important Notes

1. **DDL First**: Always run DDL scripts before DML scripts
2. **Idempotent**: DDL scripts use `CREATE TABLE IF NOT EXISTS` and `ON CONFLICT DO NOTHING` for safety
3. **Sample Data**: DML scripts contain sample/test data - modify as needed for your environment
4. **Policy Versions**: Update `source_doc_hash` with actual SHA-256 hashes of policy documents
5. **Production**: For production, load actual policy data from source documents, not sample data

---

## Schema Documentation

- **coco Extensions**: See `coco_schema_extensions.sql` for table definitions
- **hr_chatbot Schema**: See `hr_chatbot_schema.sql` for table definitions
- **Architecture**: See [HRB_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md](../../../../HRB_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md) for complete data architecture

---

**Last Updated:** January 18, 2025  
**Version:** 1.2



