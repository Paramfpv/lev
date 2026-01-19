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
**Base URL**: `http://localhost:8000`

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

## 🧠 Memory System Architecture

### How It Works
1. **Memory Router** (`core/memory/memory_router.py`): Classifies user intent and decides which memory scopes to query.
2. **Memory Store** (`core/memory/memory_store.py`): Handles database reads/writes with strict scope filtering.
3. **Memory Extractor** (`core/memory/memory_extractor.py`): Extracts facts from user messages and applies promotion rules.

### Memory Scopes
| Scope | Description | Example |
|-------|-------------|---------|
| **Session** | Temporary context for the current chat | "I'm working on the login feature" |
| **Project** | Rules and preferences for a specific project | "Use Python for all code in this project" |
| **Global** | Universal facts about the user | "My name is Param" |

### Automatic Behavior
- **Extraction**: Happens automatically after every user message.
- **Retrieval**: Happens automatically before generating responses (when relevant).
- **Promotion**: Facts are promoted from Session → Project → Global based on repetition and confidence.

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
  confidence FLOAT,
  importance INTEGER,
  metadata JSONB,
  created_at TIMESTAMPTZ
)
```
