-- RUN THIS IN SUPABASE SQL EDITOR

-- 1. Create Projects Table
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_parent_id ON public.projects(parent_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON public.projects(user_id);

-- 2. Add project_id to Chat Sessions
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'project_id') THEN
        ALTER TABLE public.chat_sessions ADD COLUMN project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 3. Automate Mind/Body/Soul for NEW users
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

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.create_default_projects();

-- 4. (OPTIONAL) BACKFILL for EXISTING Users
-- Run this ONCE if you already have users who need these projects.
-- INSERT INTO public.projects (user_id, name, parent_id, description)
-- SELECT id, 'Mind', NULL, 'Cognitive enhancement' FROM auth.users
-- WHERE NOT EXISTS (SELECT 1 FROM public.projects WHERE user_id = auth.users.id AND name = 'Mind');
-- 
-- INSERT INTO public.projects (user_id, name, parent_id, description)
-- SELECT id, 'Body', NULL, 'Physical health' FROM auth.users
-- WHERE NOT EXISTS (SELECT 1 FROM public.projects WHERE user_id = auth.users.id AND name = 'Body');
-- 
-- INSERT INTO public.projects (user_id, name, parent_id, description)
-- SELECT id, 'Soul', NULL, 'Emotional balance' FROM auth.users
-- WHERE NOT EXISTS (SELECT 1 FROM public.projects WHERE user_id = auth.users.id AND name = 'Soul');
