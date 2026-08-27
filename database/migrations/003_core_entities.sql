-- ============================================================
-- 003_core_entities.sql
-- 统一实体与版本层：entity / entity_source / entity_version + 类型化表
-- ============================================================

BEGIN;

-- 统一实体身份表
CREATE TABLE core.entity (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type      text NOT NULL,      -- job/company/skill/paper/article/project/course/certificate/public_profile
  canonical_key    text NOT NULL,      -- 稳定去重键（平台 ID → 规范化 URL → 字段哈希）
  display_name     text,
  status           text NOT NULL DEFAULT 'active',     -- active/inactive/merged/quarantined
  statistics_scope text NOT NULL DEFAULT 'observed',   -- observed/excluded
  merged_into_id   uuid REFERENCES core.entity(id),    -- 实体合并后的目标
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_entity_canonical UNIQUE (entity_type, canonical_key)
);
CREATE INDEX idx_entity_type ON core.entity (entity_type);
CREATE INDEX idx_entity_status ON core.entity (status);

-- 实体与来源记录的关联（跨来源/跨批次归并）
CREATE TABLE core.entity_source (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id        uuid NOT NULL REFERENCES core.entity(id),
  source_record_id uuid NOT NULL REFERENCES ingest.source_record(id),
  is_primary       boolean NOT NULL DEFAULT false,
  match_method     text,
  match_confidence numeric(5,4) CHECK (match_confidence BETWEEN 0 AND 1),
  linked_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_entity_source UNIQUE (entity_id, source_record_id)
);
CREATE INDEX idx_entity_source_entity ON core.entity_source (entity_id);

-- SCD Type 2 历史版本
CREATE TABLE core.entity_version (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id          uuid NOT NULL REFERENCES core.entity(id),
  version_no         integer NOT NULL,
  content_hash       text,
  valid_from         timestamptz NOT NULL,
  valid_to           timestamptz,
  is_current         boolean NOT NULL DEFAULT true,
  change_type        text,              -- new/update/unchanged/merge
  changed_fields     jsonb NOT NULL DEFAULT '{}'::jsonb,
  snapshot           jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_record_id   uuid REFERENCES ingest.source_record(id),
  previous_version_id uuid REFERENCES core.entity_version(id),
  CONSTRAINT uq_entity_version UNIQUE (entity_id, version_no)
);
-- 每个实体最多一个 current version
CREATE UNIQUE INDEX uq_one_current_version ON core.entity_version (entity_id) WHERE is_current;
CREATE INDEX idx_entity_version_valid_from ON core.entity_version (valid_from);
CREATE INDEX idx_entity_version_entity ON core.entity_version (entity_id);

-- ============================================================
-- 类型化实体表（entity_id 作 PK/FK，只存稳定且需要查询的字段）
-- ============================================================

CREATE TABLE core.company (
  entity_id       uuid PRIMARY KEY REFERENCES core.entity(id),
  canonical_name  text NOT NULL,
  industry        text,
  company_type    text,
  website         text,
  country_region  text
);

CREATE TABLE core.job (
  entity_id         uuid PRIMARY KEY REFERENCES core.entity(id),
  canonical_job_id  text NOT NULL,
  title             text,
  standard_job_name text,
  company_id        uuid REFERENCES core.entity(id),
  company_name      text,
  location          text,
  work_mode         text,
  education         text,
  experience        text,
  salary            text,
  industry          text,
  description       text,
  requirements      text,
  published_at      timestamptz,
  first_seen_at     timestamptz,
  last_seen_at      timestamptz,
  time_precision    text,
  status            text
);
CREATE INDEX idx_job_status_published ON core.job (status, published_at DESC);
CREATE INDEX idx_job_company ON core.job (company_id);

CREATE TABLE core.paper (
  entity_id      uuid PRIMARY KEY REFERENCES core.entity(id),
  arxiv_id       text,
  title          text,
  abstract       text,
  authors        jsonb NOT NULL DEFAULT '[]'::jsonb,
  categories     jsonb NOT NULL DEFAULT '[]'::jsonb,
  published_at   timestamptz,
  updated_at     timestamptz,
  pdf_url        text
);

CREATE TABLE core.technology_article (
  entity_id     uuid PRIMARY KEY REFERENCES core.entity(id),
  article_id    text,
  title         text,
  abstract      text,
  source_name   text,
  article_type  text,
  published_at  timestamptz
);

CREATE TABLE core.technology_project (
  entity_id       uuid PRIMARY KEY REFERENCES core.entity(id),
  repo_id         text,                  -- github 项目可能没有 repo_id，可为空
  owner           text,
  full_name       text,
  language        text,
  stars           integer,
  forks           integer,
  topics          jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at      timestamptz,
  updated_at      timestamptz,
  archived        boolean
);

CREATE TABLE core.course (
  entity_id           uuid PRIMARY KEY REFERENCES core.entity(id),
  course_id           text NOT NULL,       -- course_xxx 稳定平台 ID（证据用它）
  canonical_course_id text NOT NULL,       -- learn.xxx 别名
  course_name         text,
  provider            text,
  language            text,
  difficulty          text,
  duration_value      numeric,
  duration_unit       text,
  course_type         text,
  syllabus            jsonb NOT NULL DEFAULT '[]'::jsonb,
  prerequisites       jsonb NOT NULL DEFAULT '[]'::jsonb,
  price_type          text,
  availability        text
);

CREATE TABLE core.certificate (
  entity_id      uuid PRIMARY KEY REFERENCES core.entity(id),
  certificate_id text NOT NULL,
  name           text,
  issuer         text,
  level          text,
  status         text,
  validity_rule  text
);

CREATE TABLE core.public_profile (
  entity_id            uuid PRIMARY KEY REFERENCES core.entity(id),
  profile_id           text NOT NULL,
  platform_account     text,            -- github_login
  display_name         text,
  bio                  text,
  location             text,
  public_metrics       jsonb NOT NULL DEFAULT '{}'::jsonb,
  authorization_status text,
  retention_until      date,
  statistics_scope     text
);

COMMIT;
