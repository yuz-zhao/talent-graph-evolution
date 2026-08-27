-- ============================================================
-- 007_reference_analytics.sql
-- 参考数据 / 时态数据 / 新岗位候选 / 评估金标集
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS eval;   -- 解析/匹配评估金标

-- 岗位标准词典（reference/job_standard_dict.csv）
CREATE TABLE core.job_standard_dict (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_job_name       text NOT NULL,
  standard_job_name  text NOT NULL,
  job_family         text,
  job_level          text,
  job_direction      text,
  business_scene     text,
  occurrence_count   integer,
  mapping_confidence numeric(5,4),
  mapping_method     text,
  mapping_evidence   jsonb NOT NULL DEFAULT '[]'::jsonb,
  review_status      text,
  CONSTRAINT uq_job_std UNIQUE (raw_job_name, standard_job_name)
);

-- 技能候选（reference/skill_candidates.json）
CREATE TABLE core.skill_candidate (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_name  text NOT NULL UNIQUE,
  skill_id        text,
  standard_name   text,
  skill_type      text,
  aliases         jsonb NOT NULL DEFAULT '[]'::jsonb,
  status          text,
  evidence        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- 技能本体 changelog（reference/skill_ontology.changelog.jsonl）
CREATE TABLE core.ontology_changelog (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version             text NOT NULL UNIQUE,
  released_at         timestamptz,
  added_stable_ids    integer,           -- 新增稳定 ID 计数（部分版本缺失）
  migration_summary   jsonb NOT NULL DEFAULT '{}'::jsonb,
  lifecycle_algorithm text,
  source_policy       text
);

-- 技能本体版本（reference/skill_ontology.version.json）
CREATE TABLE core.ontology_version (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version           text NOT NULL UNIQUE,
  released_at       timestamptz,
  skill_count       integer,
  candidate_count   integer,
  deprecated_count  integer,
  algorithm_version text,
  promotion_rule    text,
  source_policy     text,
  previous_version  text
);

-- 岗位版本历史（temporal/job_versions.jsonl）
CREATE TABLE core.job_version_history (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id          text NOT NULL UNIQUE,
  record_id           text,
  canonical_job_id    text,
  version_number      integer,
  content_hash        text,
  valid_from          timestamptz,
  valid_to            timestamptz,
  is_current          boolean,
  change_type         text,
  changed_fields      jsonb NOT NULL DEFAULT '{}'::jsonb,
  previous_version_id text,
  crawl_batch_id      text
);
CREATE INDEX idx_jvh_job ON core.job_version_history (canonical_job_id);

-- 岗位时态索引（temporal/job_temporal_index.jsonl）
CREATE TABLE core.job_temporal_index (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id              text NOT NULL,
  canonical_job_id       text,
  source                 text,
  source_url             text,
  job_title              text,
  standard_job_name      text,
  location               text,
  first_seen_at          timestamptz,
  last_seen_at           timestamptz,
  observed_at            timestamptz,
  observed_date          date,
  publish_time_raw       text,
  source_published_at    timestamptz,
  time_precision         text,
  time_source            text,
  time_parse_confidence  numeric(5,4),
  publication_quarter    text,
  temporal_eligible      boolean,
  temporal_exclusion_reason text,
  crawl_batch_id         text,
  CONSTRAINT uq_temporal_index UNIQUE (record_id, observed_date)
);
CREATE INDEX idx_jti_job ON core.job_temporal_index (canonical_job_id, observed_date);

-- 新岗位候选（new_jobs/new_job_candidates.json）
CREATE TABLE core.new_job_candidate (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id       text NOT NULL UNIQUE,
  name               text,
  candidate_type     text,
  parent_job         text,
  unique_jd_count    integer,
  job_count          integer,
  cluster_size       integer,
  company_count      integer,
  source_count       integer,
  region_count       integer,
  top_skills         jsonb NOT NULL DEFAULT '[]'::jsonb,
  member_record_ids  jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence           jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ============================================================
-- 评估金标集（eval）
-- ============================================================
CREATE TABLE eval.gold_jd (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sample_id        text NOT NULL UNIQUE,
  split            text,
  dataset_type     text,
  source_job_id    text,
  job_title        text,
  annotation       jsonb NOT NULL DEFAULT '{}'::jsonb,
  full_record      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE eval.gold_resume (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sample_id        text NOT NULL UNIQUE,
  split            text,
  dataset_type     text,
  resume_id        text,
  display_name     text,
  annotation       jsonb NOT NULL DEFAULT '{}'::jsonb,
  full_record      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE eval.match_label (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pair_id          text NOT NULL UNIQUE,
  split            text,
  dataset_type     text,
  jd_sample_id     text,
  source_job_id    text,
  resume_sample_id text,
  annotation       jsonb NOT NULL DEFAULT '{}'::jsonb,
  full_record      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE eval.negative_sample (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sample_id        text NOT NULL UNIQUE,
  split            text,
  dataset_type     text,
  type             text,
  expected_anomaly text,
  annotation       jsonb NOT NULL DEFAULT '{}'::jsonb,
  full_record      jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMIT;
