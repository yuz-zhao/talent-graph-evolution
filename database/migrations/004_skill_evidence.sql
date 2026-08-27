-- ============================================================
-- 004_skill_evidence.sql
-- 技能本体与证据：skill / skill_alias / skill_relation / entity_skill_evidence
-- ============================================================

BEGIN;

-- 技能本体
CREATE TABLE core.skill (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_code       text NOT NULL UNIQUE,   -- skill_xxx
  name             text NOT NULL,          -- 标准名
  category         text,
  skill_type       text,                   -- technology/soft/...
  lifecycle        text,                   -- emerging/growth/mature/observed/declining
  ontology_version text,
  deprecated       boolean NOT NULL DEFAULT false,
  replaced_by_skill_id uuid REFERENCES core.skill(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_skill_name ON core.skill (name);

-- 技能别名（业务表只保存 skill_id）
CREATE TABLE core.skill_alias (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id         uuid NOT NULL REFERENCES core.skill(id),
  alias            text NOT NULL,
  normalized_alias text,
  language         text,
  source           text,
  valid_from       timestamptz,
  valid_to         timestamptz,
  CONSTRAINT uq_skill_alias UNIQUE (skill_id, alias)
);
CREATE INDEX idx_skill_alias_normalized ON core.skill_alias (normalized_alias);

-- 技能间关系
CREATE TABLE core.skill_relation (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_skill_id    uuid NOT NULL REFERENCES core.skill(id),
  to_skill_id      uuid NOT NULL REFERENCES core.skill(id),
  relation_type    text NOT NULL,          -- parent/related/replaced_by
  confidence       numeric(5,4),
  evidence_id      text,
  valid_from       timestamptz,
  valid_to         timestamptz
);
CREATE INDEX idx_skill_relation_from ON core.skill_relation (from_skill_id);

-- 实体-技能证据（图关系的事实来源）
CREATE TABLE core.entity_skill_evidence (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 主体
  entity_id                 uuid NOT NULL REFERENCES core.entity(id),
  skill_id                  uuid NOT NULL REFERENCES core.skill(id),
  relation_type             text,           -- REQUIRES_SKILL / MENTIONS_TECH / HAS_SKILL ...
  -- 证据
  claim_type                text,
  evidence_text             text,
  source_record_id          uuid REFERENCES ingest.source_record(id),
  source_url                text,
  -- 评分
  extraction_confidence     numeric(5,4) CHECK (extraction_confidence BETWEEN 0 AND 1),
  source_reliability        numeric(5,4) CHECK (source_reliability BETWEEN 0 AND 1),
  relevance                 numeric(5,4) CHECK (relevance BETWEEN 0 AND 1),
  freshness                 numeric(5,4) CHECK (freshness BETWEEN 0 AND 1),
  evidence_score            numeric(5,4) CHECK (evidence_score BETWEEN 0 AND 1),
  -- 独立性
  independent_group_id      text,
  is_independent_representative boolean,
  -- 时间 / 算法
  observed_at               timestamptz,
  time_window               text,
  extraction_method         text,
  algorithm_version         text,
  evidence_hash             text,
  -- NULLS NOT DISTINCT：source_record_id 可能为空，仍视为同一证据以支持幂等
  CONSTRAINT uq_evidence UNIQUE NULLS NOT DISTINCT (entity_id, skill_id, relation_type, source_record_id, evidence_hash)
);
CREATE INDEX idx_evidence_skill_time ON core.entity_skill_evidence (skill_id, time_window);
CREATE INDEX idx_evidence_entity ON core.entity_skill_evidence (entity_id, relation_type);
CREATE INDEX idx_evidence_algo ON core.entity_skill_evidence (algorithm_version);

COMMIT;
