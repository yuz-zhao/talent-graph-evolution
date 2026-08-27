-- ============================================================
-- 002_ingest.sql
-- 采集与血缘层：data_source / crawl_batch / source_record / quality_check
-- ============================================================

BEGIN;

-- 数据源（可配置，code 唯一）
CREATE TABLE ingest.data_source (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code              text NOT NULL UNIQUE,
  name              text NOT NULL,
  source_type       text NOT NULL,                 -- public_page / public_api / manual
  base_url          text,
  reliability_score numeric(5,4) CHECK (reliability_score BETWEEN 0 AND 1),
  enabled           boolean NOT NULL DEFAULT true,
  config            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- 一次采集批次
CREATE TABLE ingest.crawl_batch (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_batch_id text NOT NULL UNIQUE,          -- 如 20260802T164235Z_arbeitnow_76b304a7
  source_id         uuid REFERENCES ingest.data_source(id),
  source_code       text,
  started_at        timestamptz,
  finished_at       timestamptz,
  status            text NOT NULL DEFAULT 'pending',
  record_count      integer NOT NULL DEFAULT 0,
  success_count     integer NOT NULL DEFAULT 0,
  error_count       integer NOT NULL DEFAULT 0,
  manifest_uri      text,
  content_hash      text,
  pipeline_version  text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- 原始/标准化记录（追溯锚点）
CREATE TABLE ingest.source_record (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id           text NOT NULL UNIQUE,        -- 平台归一化 record id（sha）
  batch_id            uuid REFERENCES ingest.crawl_batch(id),
  source_id           uuid REFERENCES ingest.data_source(id),
  data_type           text NOT NULL,               -- job/paper/company/.../public_profile
  source_platform     text,
  source_type         text,
  source_url          text,
  normalized_url_hash text,
  source_published_at date,
  crawled_at          timestamptz,
  content_hash        text NOT NULL,
  previous_content_hash text,
  raw_uri             text,                        -- bronze 原始文件 URI
  lineage_uri         text,
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,  -- 审计留底，线上查询不得全表扫 JSONB
  content             text,                        -- 原始正文（岗位描述等）
  collection_status   text,
  lifecycle_status    text,
  first_seen_at       timestamptz,
  last_seen_at        timestamptz,
  ingested_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_source_record UNIQUE (source_platform, source_url, content_hash)
);

CREATE INDEX idx_source_record_crawled_at ON ingest.source_record (crawled_at);
CREATE INDEX idx_source_record_source_url  ON ingest.source_record (source_url);
CREATE INDEX idx_source_record_data_type   ON ingest.source_record (data_type);
CREATE INDEX idx_source_record_platform    ON ingest.source_record (source_platform);

-- 质量检查（导入必须有质量门禁）
CREATE TABLE ingest.quality_check (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id         uuid REFERENCES ingest.crawl_batch(id),
  source_record_id uuid REFERENCES ingest.source_record(id),
  rule_code        text NOT NULL,
  severity         text NOT NULL DEFAULT 'warning',
  passed           boolean NOT NULL,
  details          jsonb NOT NULL DEFAULT '{}'::jsonb,
  checked_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_quality_check_batch ON ingest.quality_check (batch_id);

COMMIT;
