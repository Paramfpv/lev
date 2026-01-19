# Memory Promotion Engine Rules

This document defines the strict logic for promoting, demoting, and ignoring user memories.

## 1. Thresholds & Verification

| Metric | Threshold | logic |
| :--- | :--- | :--- |
| **Repetition Count** | **3x** | A fact must be stated or used 3 times to move up a scope. |
| **Confirmation** | **Explicit** | "Yes, remember that" immediately sets Confidence to 1.0. |
| **Time Window** | **7 Days** | Repetitions must occur within 7 days to count towards promotion. |
| **Cross-Project** | **2+ Projects** | If a Project Memory is verified in a *different* project, it becomes Global. |

## 2. Confidence Score Updates

*   **Initial Extraction**: `0.5` (Unverified inference).
*   **User Stated Explicitly**: `1.0` (e.g., "I am vegan").
*   **Successful Retrieval**: `+0.1` (User didn't correct the bot when it used the memory).
*   **Correction/Rejection**: `-0.5` (User corrected the bot's assumption).
*   **Decay**: `-0.05` per week of inactivity.

**Rule**: If Confidence < `0.3`, **DELETE** the memory.

## 3. Promotion Logic (The "Engine")

### Input Processing
```python
def evaluate_memory_candidate(candidate, current_scope, repetitions, cross_project_count):
    if is_emotional_or_transient(candidate):
        return "IGNORE"
    
    if candidate.is_explicit_command:
        return "STORE_IMMEDIATELY"
        
    if repetitions >= 3 and current_scope == 'session':
        return "PROMOTE_TO_PROJECT"
        
    if cross_project_count >= 2 and current_scope == 'project':
        return "PROMOTE_TO_GLOBAL"
        
    return "KEEP_CURRENT_SCOPE"
```

### Action Table

| Condition | Action | Scope Change |
| :--- | :--- | :--- |
| **Transient Data** ("I'm tired", "It's raining") | **IGNORE** | None |
| **Explicit Rule** ("Always use Python") | **STORE** | Session -> Project |
| **Repeated 3x in Session** | **PROMOTE** | Session -> Project |
| **Used in 2nd Project** | **PROMOTE** | Project -> Global |
| **Contradicted by User** | **DEMOTE** | Global -> Project (or Delete) |

## 4. Examples (Allowed vs Rejected)

### ✅ ALLOWED (Promotable)
*   **Pattern**: "Prefer bullet points." (User edits output to be bullets 3 times).
    *   **Result**: Promoted to **Project Memory**.
*   **Fact**: "I am 30 years old."
    *   **Result**: Stored as **Global Memory** (High Importance).
*   **Preference**: "Don't use emojis."
    *   **Result**: Stored as **Project Memory**.

### ❌ REJECTED (Ignore/Transient)
*   **Emotion**: "I'm so frustrated with this bug."
    *   **Reason**: Transient state. Irrelevant in 1 week.
*   **Navigational**: "Go back to the previous file."
    *   **Reason**: Action-oriented, not a persistent fact.
*   **One-off Context**: "The meeting is at 5 PM."
    *   **Reason**: Expired data.

## 5. Strict Demotion (Garbage Collection)
A memory is **Demoted (Deleted)** if:
1.  It conflicts with a newer, High-Confidence memory.
2.  Confidence drops below `0.3` due to decay or corrections.
3.  It explicitly violates a "Global" rule (Global overrides Project).
