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
-- 5. FUTURE ROADMAP: "ChatGPT Style" (Sessions)
-- ==============================================================================
-- Currently, all messages for a user are in one big pile.
-- Modern chatbots use "Sessions" or "Threads" to organize topics.
--
-- Future structure (Suggestion):
--
-- TABLE chat_sessions (
--   id UUID PRIMARY KEY,
--   user_id UUID,
--   title TEXT, ("New Chat", "Longevity Protocols", etc.)
--   created_at TIMESTAMPTZ
-- );
--
-- TABLE chat_messages (
--   id UUID PRIMARY KEY,
--   session_id UUID REFERENCES chat_sessions(id),
--   role TEXT, ("user" or "assistant")
--   content TEXT,
--   created_at TIMESTAMPTZ
-- );
