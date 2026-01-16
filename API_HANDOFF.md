# Lev Project - API Handoff & Frontend Guide

## 🚀 Project Vision: "Mind, Body, Soul"
We are building a hierarchical, tree-structured chat application.
- **Root Domains**: Every user starts with three default projects: **Mind**, **Body**, and **Soul**.
- **Infinite Nesting**: Users can create sub-projects inside projects (e.g., *Body -> Fitness -> Marathon Training*).
- **Contextual Chat**: Users create Chat Sessions *inside* these projects.

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
    "parent_id": "uuid-of-parent" // Optional. If omitted, it becomes a Root (avoid this, stick to M/B/S roots).
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

### 4. Messaging
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

#### Get History
- **GET** `/history/{session_id}`
- **Response**: `{"history": [{"question": "...", "answer": "...", "timestamp": "..."}]}`

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

### 3. Tech Stack Recommendation
Since you mentioned a "beginner friendly" but "hirarichal" structure:
- **Framework**: React, Vue, or Vanilla JS (if simple).
- **State**: Need a way to store the `projectTree` and `currentUser`.
- **Styling**: Clean, perhaps dark mode (Terminal/Cyberpunk or Zen/Minimalist).
