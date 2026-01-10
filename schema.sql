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
