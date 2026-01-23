-- ==============================================================================
-- MIGRATION V2: PERSONAL INFO PROJECT
-- ==============================================================================

-- 1. Update the Trigger Function for NEW users
CREATE OR REPLACE FUNCTION public.create_default_projects()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.projects (user_id, name, parent_id, description) VALUES 
    (NEW.id, 'Personal Info', NULL, 'Dedicated space for onboarding and personal facts.'),
    (NEW.id, 'Mind', NULL, 'Cognitive enhancement, learning, and mental clarity.'),
    (NEW.id, 'Body', NULL, 'Physical health, fitness, and nutrition.'),
    (NEW.id, 'Soul', NULL, 'Emotional balance, purpose, and spiritual well-being.');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Backfill for EXISTING users
-- This safely inserts "Personal Info" for any user who doesn't have it yet.
DO $$
DECLARE
    u RECORD;
BEGIN
    FOR u IN SELECT id FROM auth.users LOOP
        INSERT INTO public.projects (user_id, name, parent_id, description)
        SELECT u.id, 'Personal Info', NULL, 'Dedicated space for onboarding and personal facts.'
        WHERE NOT EXISTS (
            SELECT 1 FROM public.projects WHERE user_id = u.id AND name = 'Personal Info'
        );
    END LOOP;
END $$;
