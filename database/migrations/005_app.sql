-- ============================================================
-- 005_app.sql
-- 用户业务层：用户/简历/匹配/学习计划（重构外键，业务表只存 skill_id）
-- 说明：本 schema 承载“从 MySQL 迁入的用户业务数据”，首批不填充。
-- ============================================================

BEGIN;

CREATE TABLE app.user_account (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username       text NOT NULL UNIQUE,
  password_hash  text NOT NULL,          -- Argon2id/bcrypt，禁止明文
  real_name      text,
  role           text NOT NULL DEFAULT 'user',
  status         text NOT NULL DEFAULT 'active',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.user_profile (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES app.user_account(id),
  school         text,
  major          text,
  education      text,
  target_location text,
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.resume (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES app.user_account(id),
  file_uri       text,
  file_hash      text,
  status         text NOT NULL DEFAULT 'parsed',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.resume_version (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id      uuid NOT NULL REFERENCES app.resume(id),
  version_no     integer NOT NULL,
  parse_status   text,
  parse_engine   text,
  skills_json    jsonb,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.resume_skill (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_version_id uuid NOT NULL REFERENCES app.resume_version(id),
  skill_id        uuid NOT NULL REFERENCES core.skill(id),
  confidence      numeric(5,4),
  evidence_text   text,
  CONSTRAINT uq_resume_skill UNIQUE (resume_version_id, skill_id)
);

CREATE TABLE app.resume_project (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_version_id uuid NOT NULL REFERENCES app.resume_version(id),
  project_name   text,
  description    text,
  start_at       timestamptz,
  end_at         timestamptz
);

CREATE TABLE app.resume_project_skill (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_project_id uuid NOT NULL REFERENCES app.resume_project(id),
  skill_id       uuid NOT NULL REFERENCES core.skill(id),
  CONSTRAINT uq_resume_project_skill UNIQUE (resume_project_id, skill_id)
);

-- 用户对岗位的行为（唯一键含 action_type，避免“收藏后无法记不感兴趣”）
CREATE TABLE app.user_job_action (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES app.user_account(id),
  job_id         uuid NOT NULL REFERENCES core.entity(id),   -- 指向 core.entity 而非悬空字符串
  action_type    text NOT NULL,        -- favorite / not_interested / applied / viewed
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_user_job_action UNIQUE (user_id, job_id, action_type)
);

CREATE TABLE app.match_run (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES app.user_account(id),
  resume_version_id uuid REFERENCES app.resume_version(id),
  model_version   text,
  params          jsonb,
  status          text NOT NULL DEFAULT 'pending',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.match_result (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  match_run_id    uuid NOT NULL REFERENCES app.match_run(id),
  job_id          uuid NOT NULL REFERENCES core.entity(id),
  total_score     numeric(5,4),
  dim_scores      jsonb NOT NULL DEFAULT '{}'::jsonb,   -- 各维度分
  CONSTRAINT uq_match_result UNIQUE (match_run_id, job_id)
);

CREATE TABLE app.match_result_skill (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  match_result_id uuid NOT NULL REFERENCES app.match_result(id),
  skill_id        uuid NOT NULL REFERENCES core.skill(id),
  matched         boolean NOT NULL,
  contribution    numeric(5,4),
  evidence_id     text,
  CONSTRAINT uq_match_result_skill UNIQUE (match_result_id, skill_id)
);

CREATE TABLE app.gap_analysis (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES app.user_account(id),
  target_job_id   uuid REFERENCES core.entity(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.gap_skill (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gap_analysis_id uuid NOT NULL REFERENCES app.gap_analysis(id),
  skill_id        uuid NOT NULL REFERENCES core.skill(id),
  gap_level       text,
  CONSTRAINT uq_gap_skill UNIQUE (gap_analysis_id, skill_id)
);

CREATE TABLE app.learning_plan (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES app.user_account(id),
  target_skill_id uuid REFERENCES core.skill(id),
  status          text NOT NULL DEFAULT 'active',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.learning_task (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id          uuid NOT NULL REFERENCES app.learning_plan(id),
  skill_id         uuid REFERENCES core.skill(id),
  course_id        uuid REFERENCES core.entity(id),      -- course/certificate/project 公共实体
  title            text,
  status           text NOT NULL DEFAULT 'pending',
  sort_order       integer NOT NULL DEFAULT 0
);

COMMIT;
