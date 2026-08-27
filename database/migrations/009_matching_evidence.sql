BEGIN;

ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS skill_state text NOT NULL DEFAULT 'mentioned';
ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS proficiency_level smallint;
ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS years_experience numeric(5,2);
ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS last_used_at date;
ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS evidence_type text;
ALTER TABLE app.resume_skill ADD COLUMN IF NOT EXISTS responsibility text;

ALTER TABLE app.resume_skill DROP CONSTRAINT IF EXISTS ck_resume_skill_level;
ALTER TABLE app.resume_skill ADD CONSTRAINT ck_resume_skill_level CHECK (proficiency_level IS NULL OR proficiency_level BETWEEN 1 AND 5);
ALTER TABLE app.resume_skill DROP CONSTRAINT IF EXISTS ck_resume_skill_years;
ALTER TABLE app.resume_skill ADD CONSTRAINT ck_resume_skill_years CHECK (years_experience IS NULL OR years_experience BETWEEN 0 AND 50);

COMMIT;
