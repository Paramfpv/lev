# Lev Project - API Handoff & Frontend Guide

## 🚀 Project Vision: "Mind, Body, Soul" + Intelligent Memory
We are building a hierarchical, tree-structured chat application with **intelligent memory**.
- **Root Domains**: Every user starts with three default projects: **Mind**, **Body**, and **Soul**.
- **Infinite Nesting**: Users can create sub-projects inside projects (e.g., *Body -> Fitness -> Marathon Training*).
- **Contextual Chat**: Users create Chat Sessions *inside* these projects.
- **🧠 Memory System**: Lev learns from your conversations and remembers facts, preferences, and rules at Session, Project, and Global scopes.

The Frontend handles the visualization of this Tree and the Chat Interface.

---

## 🛠️ Backend API Reference
**Base URL**: `lev-production.up.railway.app`

### 1. Authentication
Authentication is handled via Supabase, but the backend provides wrappers to simplify headers/user management.

#### Register
- **POST** `/register`
- **Body**: `{"email": "...", "password": "..."}`
- **Response**: `{"user_id": "uuid", ...}`

#### Login
- **POST** `/login`
- **Body**: `{"email": "...", "password": "..."}`
- **Response**: `{"user_id": "uuid", "email": "..."}`
- **Note**: Store `user_id` in LocalStorage/Context.

---

### 2. Projects (The Tree)

#### Get Project Tree
We provide two ways to fetch projects. For the Frontend Tree View, fetching the flat list and building the tree is often easiest.

- **GET** `/projects/tree/{user_id}`
- **Response**:
  ```json
  {
    "projects": [
      {
        "id": "uuid-1",
        "name": "Mind",
        "parent_id": null,  // Root Node
        "description": "..."
      },
      {
        "id": "uuid-2",
        "name": "Meditation", 
        "parent_id": "uuid-1" // Child of Mind
      }
    ]
  }
  ```
- **Frontend Logic**: 
  1. Fetch all projects.
  2. Filter where `parent_id === null` for Top Level (Mind, Body, Soul).
  3. Recursively find children for each node to build the UI tree.

#### Create a Project
- **POST** `/projects`
- **Body**:
  ```json
  {
    "user_id": "uuid",
    "name": "New Project Name",
    "parent_id": "uuid-of-parent", // Optional. If omitted, it becomes a Root (avoid this, stick to M/B/S roots).
    "description": "Optional"
  }
  ```

---

### 3. Chat Sessions
Chats happen *inside* a project (or standalone, but ideally inside a project).

#### Create a Session (New Chat)
- **POST** `/sessions`
- **Body**:
  ```json
  {
    "user_id": "uuid",
    "title": "Chat Topic",
    "project_id": "uuid-of-project" // LINK THE CHAT TO A PROJECT
  }
  ```
- **Response**: `{"id": "session-uuid", "title": "...", "project_id": "..."}`

#### Get Sessions
- **GET** `/sessions/{user_id}?project_id={project_uuid}`
- **Use Case**: When a user clicks a Project in the sidebar, call this to show the list of conversations *within* that project.

---

### 4. Messaging (With Intelligent Memory)

#### Send Message
- **POST** `/chat`
- **Body**:
  ```json
  {
    "user_id": "uuid",
    "question": "Hello",
    "session_id": "session-uuid",
    "project_id": "project-uuid" // Optional context
  }
  ```
- **Response**: `{"answer": "AI Response..."}`
- **🧠 Memory Behavior**:
  - **Read**: Before generating a response, Lev checks for relevant memories (Project + Global scope).
  - **Write**: After responding, Lev extracts facts/preferences from your message and saves them automatically.
  - **Example**: If you say *"I prefer Python"*, Lev will remember this for future chats in that project.

#### Get History
- **GET** `/history/{session_id}`
- **Response**: `{"history": [{"question": "...", "answer": "...", "timestamp": "..."}]}`

---

### 5. Personal Info (User Stats)
Used for the "Optimization %" bar on the dashboard.

#### Get User Stats
- **GET** `/user/stats/{user_id}`
- **Response**:
  ```json
  {
    "optimization_score": 60, // (Covered Domains / 5) * 100
    "domains": {
      "identity": "complete",
      "preferences": "partial",
      "habits": "missing",
      "goals": "partial",
      "constraints": "complete"
    },
    "last_updated": "ISO_TIMESTAMP"
  }
  ```
- **Logic**:
  - Only counts **Global** memories with **Confidence >= 0.85**.
  - Domains: Identity, Preferences, Habits, Goals, Constraints.
  - Score is percentage of domains that have *any* data ("partial" or "complete").

#### Get Next Personal Info Question (Orchestrator)
- **GET** `/personal-info/question/{user_id}?session_count=0&session_id=...`
- **Params**: 
  - `session_count` (int): How many questions asked in *this* session (Frontend tracks this. Max 5).
  - `session_id` (str, optional): The UUID of the current chat session. Used to prevent repeating questions in the same session.
- **Response**:
  ```json
  {
    "question": "What usually keeps you up at night?",
    "domain": "habits",
    "project_id": "uuid-of-personal-info-project"
  }
  ```
- **Stop Condition**: Returns `null` if Optimization Score >= 70% OR `session_count` >= 5.
- **Flow**:
  1. Call this endpoint.
  2. **CRITICAL**: Create (or resume) a chat session linked specifically to `project_id`. 
     * **Do NOT** use the "Mind/Body/Soul" projects for this.
     * **Do NOT** use a generic session. 
     * The answer MUST be posted to a session belonging to "Personal Info".
  3. Display question.
  4. User answers via standard `POST /chat`.
  5. Memory system extracts fact and links it to the "Personal Info" project scope.
  6. Call `/user/stats` to update progress.

## 🧠 Memory System Architecture

### How It Works
### How It Works (Canonical Lifecycle V1)
1. **Single Authority** (`core/memory_manager.py`): Manages the entire lifecycle (Extraction -> Lookup -> Impact Analysis -> Promotion -> Persistence).
2. **Interactive Learning**:
   - **Extraction**: User input is mined for facts/preferences.
   - **Lookup**: System checks for existing memories to detect duplicates or contradictions.
   - **Impact Analysis**: New facts are judged against old ones.
     - **Exact Match**: Increments repetition.
     - **Contradiction**: Overrides old memory if new confidence is higher.
   - **Promotion**:
     - **Session → Project**: After **3 repetitions** (or 2 if High Importance).
     - **Project → Global**: After verification in a **different project**.

### Memory Scopes
| Scope | Description | Promotion Rule |
|-------|-------------|----------------|
| **Session** | Immediate working memory, strictly scoped to current chat. | Promotes to **Project** if useful & repeated. |
| **Project** | Rules/Context specific to a project domain (e.g., "Fitness"). | Promotes to **Global** if valid across multiple projects. |
| **Global** | Universal User Truths (Identity, Core Values). | Highest tier, strictly verified. |

### Automatic Behavior
- **Write**: Happens automatically. The system "learns" by updating repetition counts and confidence scores rather than just appending rows.
- **Read**: Prioritizes **Session** (Recency) > **Project** (Context) > **Global** (Truths).

---

## 🎨 Frontend Implementation Guidelines

### 1. The Layout
The app should feel like a "Command Center" or "Digital Brain".
- **Sidebar (The Tree)**:
  - Display "Mind", "Body", "Soul" as the permanent roots.
  - Expandable/Collapsible folders for sub-projects.
  - "Right-click" or "Hover" menu on a project to **"Add Sub-project"** or **"New Chat Here"**.
- **Main Area (The Chat)**:
  - When a Session is selected: Show the Chat Interface.
  - When a Project is selected: Show a Dashboard for that project (List of recent chats in this project, maybe sub-projects).

### 2. User Flow
1. **Login** -> Land on Dashboard.
2. Sidebar loads the Tree (`GET /projects/tree`).
3. User expands "Mind" -> sees "Meditation".
4. User clicks "Meditation".
5. Main view shows "Chats in Meditation" (`GET /sessions?project_id=...`).
6. User clicks "New Chat".
7. Main view switches to Empty Chat.
8. User types -> Message sent to backend.
9. **🧠 Memory works silently in the background**.

### 3. Tech Stack Recommendation
Since you mentioned a "beginner friendly" but "hierarchical" structure:
- **Framework**: React, Vue, or Vanilla JS (if simple).
- **State**: Need a way to store the `projectTree` and `currentUser`.
- **Styling**: Clean, perhaps dark mode (Terminal/Cyberpunk or Zen/Minimalist).

---

## 📊 Database Schema Overview

### Core Tables
- **`auth.users`**: Managed by Supabase Auth
- **`projects`**: Hierarchical project tree (Mind/Body/Soul + nested sub-projects)
- **`chat_sessions`**: Chat conversations linked to projects
- **`chat_history`**: Message history for each session
- **`user_memory`**: 🧠 **NEW** - Stores extracted facts, preferences, and rules

### Memory Table Structure
```sql
user_memory (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id),
  content TEXT NOT NULL,
  scope TEXT CHECK (scope IN ('session', 'project', 'global')),
  project_id UUID REFERENCES projects(id),
  session_id UUID REFERENCES chat_sessions(id),
  confidence FLOAT DEFAULT 1.0,
  importance TEXT CHECK (importance IN ('low', 'medium', 'high')),
  repetition_count INTEGER DEFAULT 1,
  keywords TEXT[], -- Array of strings
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed TIMESTAMPTZ DEFAULT NOW()
)
```



