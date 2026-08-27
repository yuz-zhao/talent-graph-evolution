-- ============================================================
-- 006_ops.sql
-- 运维与投影：pipeline_run / projection_checkpoint / algorithm_version
--            / audit_log / dead_letter
-- ============================================================

BEGIN;

CREATE TABLE ops.pipeline_run (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_name     text NOT NULL,          -- import-gold / project-neo4j / project-qdrant
  code_version      text,
  input_uri         text,
  output_uri        text,
  status            text NOT NULL DEFAULT 'running',
  error             text,
  metrics           jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at        timestamptz NOT NULL DEFAULT now(),
  finished_at       timestamptz
);

CREATE TABLE ops.projection_checkpoint (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target        text NOT NULL,               -- neo4j / qdrant
  entity_type   text NOT NULL,
  last_version  bigint NOT NULL DEFAULT 0,
  watermark_at  timestamptz,
  status        text NOT NULL DEFAULT 'idle',
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_projection_checkpoint UNIQUE (target, entity_type)
);

CREATE TABLE ops.algorithm_version (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  algo_name       text NOT NULL,             -- skill_extraction / match / evidence_score / embedding
  version         text NOT NULL,
  config_hash     text,
  params          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_algorithm_version UNIQUE (algo_name, version)
);

CREATE TABLE ops.audit_log (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor       text,
  action      text NOT NULL,
  entity_type text,
  entity_id   text,
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.dead_letter (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stage           text NOT NULL,             -- ingest / project / embed
  reason          text,
  record_id       text,
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
  retryable       boolean NOT NULL DEFAULT true,
  retry_count     integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.system_config (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  config_key    text NOT NULL UNIQUE,
  config_value  jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at    timestamptz NOT NULL DEFAULT now()
);

COMMIT;
