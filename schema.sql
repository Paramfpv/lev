-- ==============================================================================
-- LEV PROJECT DATABASE SCHEMA
-- ==============================================================================
-- This file documents the database structure for the Lev RAG Chatbot.
-- It serves as the "Source of Truth" for your database architecture.
--
-- TO APPLY THESE CHANGES:
-- 1. Run these commands in the Supabase SQL Editor.
-- 2. NOTE: "chat_history" already exists. You may need to run the MIGRATION
--    commands at the bottom to clean up your existing table.
-- ==============================================================================

-- 1. USERS (Managed by Supabase Auth)
-- ------------------------------------------------------------------------------
-- Supabase handles user signup/login in the "auth.users" table automatically.
-- We can reference "auth.users.id" in our own tables.

-- 2. CHAT HISTORY (The "Memory" of the bot)
-- ------------------------------------------------------------------------------
-- This table stores every interaction between a user and the bot.
-- Note: We are using a clean structure here. Your current database has
-- redundant columns ("user_question", "bot_answer") which should be ignored or removed.

CREATE TABLE IF NOT EXISTS public.chat_history (
    id SERIAL PRIMARY KEY,                          -- Unique ID for every message pair
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE, -- Link to the user
    question TEXT NOT NULL,                         -- What the user asked
    answer TEXT NOT NULL,                           -- What the bot replied
    timestamp TIMESTAMPTZ DEFAULT NOW()             -- When it happened (auto-set)
);

-- 3. INDEXES (For Speed)
-- ------------------------------------------------------------------------------
-- As the chat history grows to thousands of rows, searching becomes slow.
-- Indexes make looking up a specific user's history instant.

CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON public.chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON public.chat_history(timestamp DESC);

-- ==============================================================================
-- 4. RECOMMENDED MIGRATION (Clean up your existing mess)
-- ==============================================================================
-- Your current table has duplicate columns:
-- - Used: "question", "answer"
-- - Unused/Empty: "user_question", "bot_answer"
--
-- Uncomment and run the following lines to clean your database:

-- ALTER TABLE public.chat_history DROP COLUMN IF EXISTS user_question;
-- ALTER TABLE public.chat_history DROP COLUMN IF EXISTS bot_answer;

-- ==============================================================================
-- 5. MULTI-SESSION CHAT SUPPORT
-- ==============================================================================

-- 5.1 Create the Sessions Table
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT,                            -- "New Chat", "Longevity Protocols", etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5.2 Add session_id to chat_history
-- We use ALTER TABLE to add the column if it doesn't exist.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_history' AND column_name = 'session_id') THEN
        ALTER TABLE public.chat_history ADD COLUMN session_id UUID REFERENCES public.chat_sessions(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 5.3 Indexes for Sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON public.chat_history(session_id);

-- Note: The previous "FUTURE ROADMAP" section is now implemented above.

-- ==============================================================================
-- 6. PROJECT STRUCTURE (Mind, Body, Soul)
-- ==============================================================================

-- 6.1 Create Projects Table (Tree Structure)
-- "parent_id" references "id" in the same table, allowing infinite nesting.
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES public.projects(id) ON DELETE CASCADE, -- Null for Root Projects
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6.2 Index for Parent Lookup
CREATE INDEX IF NOT EXISTS idx_projects_parent_id ON public.projects(parent_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON public.projects(user_id);

-- 6.3 Update Chat Sessions to belong to a Project
-- If you already created the table, run this ALTER command:
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'project_id') THEN
        ALTER TABLE public.chat_sessions ADD COLUMN project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_project_id ON public.chat_sessions(project_id);


-- ==============================================================================
-- 7. AUTOMATION: Default "Mind, Body, Soul" Projects
-- ==============================================================================
-- This trigger automatically creates the 3 root projects for every NEW user.

-- 7.1 Function to insert defaults
CREATE OR REPLACE FUNCTION public.create_default_projects()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.projects (user_id, name, parent_id, description) VALUES 
    (NEW.id, 'Mind', NULL, 'Cognitive enhancement, learning, and mental clarity.'),
    (NEW.id, 'Body', NULL, 'Physical health, fitness, and nutrition.'),
    (NEW.id, 'Soul', NULL, 'Emotional balance, purpose, and spiritual well-being.');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 7.2 Trigger Definition (Runs after a user signs up)
-- DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users; 
-- Note: You might need to run the DROP manually if it conflicts.
-- In Supabase SQL Editor:
-- CREATE TRIGGER on_auth_user_created
-- AFTER INSERT ON auth.users
-- FOR EACH ROW EXECUTE FUNCTION public.create_default_projects();

-- NOTE: Since I cannot execute triggers on "auth.users" from here via migration easily without 
-- superuser sometimes, please copy-paste the Trigger creation manually if it fails.
-- But the standard definition is:

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created') THEN
        CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.create_default_projects();
    END IF;
END $$;
-- ==============================================================================
-- LEV MEMORY SYSTEM
-- ==============================================================================
-- Run this in your Supabase SQL Editor to enable the Memory System.

-- 1. Enable pgvector (Required for embeddings/smart retrieval)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the Memory Table
CREATE TABLE IF NOT EXISTS public.user_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- CORE CONTENT
    content TEXT NOT NULL,
    
    -- SCOPE & HIERARCHY
    -- 'session': Context relevant only to a specific chat.
    -- 'project': Context relevant to a whole project (e.g. "Body").
    -- 'global': Universal facts about the user (e.g. "User is vegan").
    scope TEXT NOT NULL CHECK (scope IN ('session', 'project', 'global')),
    
    -- LINKING (Nullable based on scope)
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    
    -- AI METADATA
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1.0),
    importance INTEGER DEFAULT 1, -- 1-10 scale. Used for retrieval weighting or decay.
    
    -- RETRIEVAL & FUTURE PROOFING
    -- 'embedding': Vector representation for semantic search.
    -- 'metadata': JSONB for flexible extras (e.g. { "origin_message_id": "...", "tags": ["diet"] })
    embedding vector(1536), 
    metadata JSONB DEFAULT '{}'::jsonb,

    -- TIMESTAMPS
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),

    -- DATA INTEGRITY
    CONSTRAINT valid_scope_context CHECK (
        (scope = 'session' AND session_id IS NOT NULL) OR
        (scope = 'project' AND project_id IS NOT NULL) OR
        (scope = 'global')
    )
);

-- 3. INDEXES
-- Speed up retrieval by user and scope
CREATE INDEX IF NOT EXISTS idx_memory_user_scope ON public.user_memory(user_id, scope);
-- Speed up project-specific memory lookups
CREATE INDEX IF NOT EXISTS idx_memory_project ON public.user_memory(project_id);
-- Speed up vector similarity search (Uncomment when you have data)
-- CREATE INDEX idx_memory_embedding ON public.user_memory USING ivfflat (embedding vector_cosine_ops);
