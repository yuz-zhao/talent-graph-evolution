-- ============================================================
-- 001_schemas.sql
-- TalentGraph 新数据事实库（PostgreSQL）· 数据库与 Schema 划分
--
-- 用法：先创建数据库（单独执行，不在事务内）
--   CREATE DATABASE talentgraph_dev ENCODING 'UTF8' TEMPLATE template0;
-- 再执行本文件：
--   psql -h 127.0.0.1 -U postgres -d talentgraph_dev -f 001_schemas.sql
-- ============================================================

BEGIN;

-- 四个业务 schema：采集 / 核心实体 / 应用 / 运维
CREATE SCHEMA IF NOT EXISTS ingest;   -- 采集、原始记录、血缘、质量
CREATE SCHEMA IF NOT EXISTS core;     -- 规范实体、版本、技能与证据
CREATE SCHEMA IF NOT EXISTS app;      -- 用户、简历、匹配、学习计划
CREATE SCHEMA IF NOT EXISTS ops;      -- 同步、算法版本、审计

-- 扩展
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() / 摘要
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- 模糊检索（中文分词另行评估）

COMMIT;
