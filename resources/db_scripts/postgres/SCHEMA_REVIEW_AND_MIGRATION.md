# Database Schema Review and Migration Guide

## ✅ Existing Tables (Already Created)

### coco Database

#### From `coco_schema_extensions.sql`:
- ✅ `policy_versions` - Policy versioning (all 5 domains)
- ✅ `leave_rules` - Leave policy rules
- ✅ `agent_tasks` - Agent task tracking
- ✅ `leave_requests` - Extended with agent fields

#### From `coco_schema_dml.sql`:
- ✅ Policy versions for all 5 domains
- ✅ Leave rules (parental, critical caregiver, FMLA, sick, bereavement, coordination)

### hr_chatbot Database

#### From `hr_chatbot_schema.sql`:
- ✅ `chat_sessions` - Conversation sessions
- ✅ `chat_history` - Chat history with agent reasoning
- ✅ `user_feedback` - User feedback collection

## ❌ Missing Tables (Need to be Created)

### coco Database

#### Policy Rules Tables:
- ❌ `disability_rules` - Disability/STD/LTD rules
- ❌ `retirement_rules` - 401k/retirement rules
- ❌ `healthcare_rules` - Healthcare plan rules
- ❌ `tuition_rules` - Tuition assistance rules

#### Application/Decision Tables:
- ❌ `disability_applications` - Disability application submissions
- ❌ `tuition_applications` - Tuition application submissions
- ❌ `retirement_decisions` - 401k contribution decisions
- ❌ `enrollment_decisions` - Healthcare enrollment decisions

#### Workflow Tables:
- ❌ `workflow_state` - Multi-step workflow execution state

### hr_chatbot Database

#### HITL Tables:
- ❌ `hitl_escalations` - Human-in-the-loop escalation tracking

## 📋 Migration Scripts Created

### 1. `coco_schema_missing_tables.sql`
**Purpose:** Creates missing tables for all benefit domains

**Tables Created:**
- `disability_rules`
- `retirement_rules`
- `healthcare_rules`
- `tuition_rules`
- `disability_applications`
- `tuition_applications`
- `retirement_decisions`
- `enrollment_decisions`
- `workflow_state`

**Usage:**
```bash
psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables.sql
```

### 2. `coco_schema_missing_tables_dml.sql`
**Purpose:** Inserts initial rules data for all domains

**Data Inserted:**
- Disability rules (STD/LTD)
- Retirement rules (401k match, contribution limits)
- Healthcare rules (medical, dental, vision plans)
- Tuition rules (reimbursement, eligibility)

**Usage:**
```bash
psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables_dml.sql
```

### 3. `hr_chatbot_schema_hitl.sql`
**Purpose:** Creates HITL escalations table

**Tables Created:**
- `hitl_escalations`

**Usage:**
```bash
psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema_hitl.sql
```

## 🔄 Migration Execution Order

### For Existing Database (Alter/Add Only)

1. **coco Database:**
   ```bash
   # Add missing tables
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables.sql
   
   # Add initial rules data
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables_dml.sql
   ```

2. **hr_chatbot Database:**
   ```bash
   # Add HITL escalations table
   psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema_hitl.sql
   ```

### For Fresh Database (Full Setup)

1. **coco Database:**
   ```bash
   # Existing schema
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_extensions.sql
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_dml.sql
   
   # New missing tables
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables.sql
   psql -d coco -f src/app/common/db_scripts/postgres/coco_schema_missing_tables_dml.sql
   ```

2. **hr_chatbot Database:**
   ```bash
   # Existing schema
   psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema.sql
   
   # HITL table
   psql -d hr_chatbot -f src/app/common/db_scripts/postgres/hr_chatbot_schema_hitl.sql
   ```

## ✅ Verification Queries

### Check All Tables Exist

```sql
-- coco database
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'policy_versions', 'leave_rules', 'agent_tasks',
    'disability_rules', 'retirement_rules', 'healthcare_rules', 'tuition_rules',
    'disability_applications', 'tuition_applications',
    'retirement_decisions', 'enrollment_decisions',
    'workflow_state'
  )
ORDER BY table_name;

-- hr_chatbot database
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'chat_sessions', 'chat_history', 'user_feedback', 'hitl_escalations'
  )
ORDER BY table_name;
```

### Check Rules Data

```sql
-- Count rules by domain
SELECT 'leave' as domain, COUNT(*) as rule_count FROM leave_rules
UNION ALL
SELECT 'disability', COUNT(*) FROM disability_rules
UNION ALL
SELECT 'retirement', COUNT(*) FROM retirement_rules
UNION ALL
SELECT 'healthcare', COUNT(*) FROM healthcare_rules
UNION ALL
SELECT 'tuition', COUNT(*) FROM tuition_rules;
```

## 📝 Notes

1. **Idempotent Scripts:** All scripts use `CREATE TABLE IF NOT EXISTS` and `ON CONFLICT DO NOTHING` for safety
2. **No Data Loss:** Migration scripts only ADD tables, they don't modify existing ones
3. **Backward Compatible:** Existing functionality continues to work
4. **Indexes:** All tables have appropriate indexes for query performance

---

**Status:** Migration scripts ready for execution  
**Date:** January 2025

