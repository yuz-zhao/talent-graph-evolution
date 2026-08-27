-- Preserve legacy business records that cannot be mapped to a current job entity.
BEGIN;

ALTER TABLE app.match_result ALTER COLUMN job_id DROP NOT NULL;
ALTER TABLE app.match_result ADD COLUMN IF NOT EXISTS legacy_job_name text;

ALTER TABLE app.user_job_action ALTER COLUMN job_id DROP NOT NULL;
ALTER TABLE app.user_job_action ADD COLUMN IF NOT EXISTS legacy_job_name text;

ALTER TABLE app.gap_analysis ADD COLUMN IF NOT EXISTS legacy_job_name text;

COMMIT;
