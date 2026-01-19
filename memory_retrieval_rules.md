# User Memory Retrieval Rules

This document defines the strict SQL-level rules for retrieving memories from the `user_memory` table.

## 1. General Principles
-   **Strict Scoping**: Queries must explicitly filter by `scope` to prevent leaking context (e.g., project secrets leaking into global chat).
-   **Ranking Strategy**: `(Confidence * Importance) > Recency`. reliability > freshness.
-   **Deterministic**: Always include unique ID in ordering to prevent pagination drift.
-   **Safe Defaults**: Always use `LIMIT` to prevent token context overflow.

## 2. Query Templates

### A. Session Memory (Short-term Context)
**Goal**: Get recent context for the *current* active chat.
*   **Filter**: `user_id`, `session_id`, `scope = 'session'`
*   **Limit**: 10 (Focus on immediate conversation turn)
*   **Order**: Newest first (Standard chat history behavior)

```sql
SELECT content, created_at
FROM public.user_memory
WHERE 
  user_id = 'USER_UUID'
  AND session_id = 'SESSION_UUID'
  AND scope = 'session'
ORDER BY 
  created_at DESC, 
  id ASC
LIMIT 10;
```

### B. Project Memory (Medium-term Context)
**Goal**: Get axioms, rules, and facts specific to this project.
*   **Filter**: `user_id`, `project_id`, `scope = 'project'`
*   **Limit**: 20 (Projects can have many rules)
*   **Order**: High Confidence & Importance -> Then Newest.

```sql
SELECT content, confidence, importance
FROM public.user_memory
WHERE 
  user_id = 'USER_UUID'
  AND project_id = 'PROJECT_UUID'
  AND scope = 'project'
ORDER BY 
  confidence DESC, 
  importance DESC, 
  created_at DESC, 
  id ASC
LIMIT 20;
```

### C. Global Memory (Long-term Context)
**Goal**: Get universal facts about the user (Name, Diet, Core Values).
*   **Filter**: `user_id`, `scope = 'global'`
*   **Limit**: 5 (Only the most critical facts to avoid noise)
*   **Order**: Highest Importance first.

```sql
SELECT content, importance
FROM public.user_memory
WHERE 
  user_id = 'USER_UUID'
  AND scope = 'global'
ORDER BY 
  importance DESC, 
  confidence DESC, 
  created_at DESC, 
  id ASC
LIMIT 5;
```

### D. Hybrid Retrieval (Vector Search - Future Proof)
**Goal**: Find relevant memories across Project/Global scopes based on a question.
*   **Filter**: `user_id` AND (`scope='global'` OR `scope='project'`)
*   **Order**: Vector Similarity (Cosine Distance)

```sql
-- Requires pgvector
SELECT content, 1 - (embedding <=> '[VECTOR_ARRAY]') as similarity
FROM public.user_memory
WHERE 
  user_id = 'USER_UUID'
  AND (
    scope = 'global' 
    OR (scope = 'project' AND project_id = 'PROJECT_UUID')
  )
ORDER BY similarity DESC
LIMIT 10;
```

## 3. Max Limits & Constraints
| Parameter | Default | Hard Max | Reason |
| :--- | :--- | :--- | :--- |
| **Session MEM Limit** | 10 rows | 50 rows | Chat history is redundant; strictly for "system notes". |
| **Project MEM Limit** | 20 rows | 100 rows | Projects accumulate rules; rely on Vector Search if >20. |
| **Global MEM Limit** | 5 rows | 20 rows | Global context is expensive; keep it axiomatic. |
| **Min Confidence** | 0.7 | 0.0 | Ignore "low confidence" hallucinations. |
