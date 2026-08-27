"""
通用配置 — 请求参数、路径、岗位 JD v2 标准定义
"""

import os

# ============================================================
# 路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
BRONZE_DIR = os.path.join(DATA_DIR, "bronze")
SILVER_DIR = os.path.join(DATA_DIR, "silver")
GOLD_DIR = os.path.join(DATA_DIR, "gold")
META_DIR = os.path.join(GOLD_DIR, "reference")
COLLECTION_DIR = os.path.join(DATA_DIR, ".ops", "collection")
RAW_DIR = os.path.join(BRONZE_DIR, "jobs")
CLEAN_DIR = os.path.join(SILVER_DIR, "jobs")

# ============================================================
# 请求配置
# ============================================================
REQUEST_DELAY = 3.0
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# ============================================================
# JD 数据字段（v2：保留原 21 字段并追加血缘、版本和技能证据）
# ============================================================
JD_FIELDS = [
    "job_title",           # 岗位名称（原始）
    "standard_job_name",   # 标准岗位名称
    "company",             # 公司名称
    "industry",            # 所属行业
    "location",            # 工作地点
    "salary",              # 薪资
    "education",           # 学历要求
    "experience",          # 经验要求
    "description",         # 岗位描述（清洗后纯文本）
    "requirements",        # 任职要求（清洗后纯文本）
    "publish_time",        # 发布时间
    "source_url",          # 来源URL
    "source_name",         # 来源名称（中文企业官网/Greenhouse/...）
    "source_language",     # zh / en
    "source_priority",     # 1=中文企业官网 2=中文招聘平台 3=中文公开数据 4=英文ATS
    "crawl_time",          # 采集时间
    "skill_raw",           # 原始技能词 ; 分隔
    "skill_standard",      # 标准技能词 ; 分隔
    "time_slice",          # 时间切片 2026Q3
    "evidence_score",      # 证据可信度 0-1
    "duplicate_score",     # 重复度 0-1
    "source_job_id",       # 来源侧稳定岗位标识
    "canonical_job_id",    # 标准岗位实体标识
    "version_id",          # 当前内容版本标识
    "valid_from",          # 版本生效/首次观测日期
    "valid_to",            # 版本失效日期，空表示当前有效
    "raw_description",     # 来源原始正文，不被清洗字段覆盖
    "required_skills",     # 有明确要求证据的必备技能
    "preferred_skills",    # 原文明确“优先/加分”的技能
    "mentioned_skills",    # 出现在职责/标题但未明确要求的技能
    "skill_evidence",      # JSON：技能、原词、证据片段、字段、置信度
    "skill_extraction_method",
    "skill_confidence",
    "company_type",        # 央企/国企/民营/外企/事业单位/科研院所/未知
    "company_type_source", # 企业性质判定依据
    "publish_time_source", # source_page/relative_display/missing
    "requirements_source", # source_detail/source_page/missing
    "source_url_status",   # syntax_valid/verified_live/invalid
    "source_url_checked_at",
    "statistics_scope",    # china_main/overseas_reference
    "data_provenance",     # observed/inferred/synthetic
    "is_synthetic",
    "lifecycle_status",
    "job_family",
    "region_standard",
]

# ============================================================
# 输出文件
# ============================================================
JD_RAW_CSV = os.path.join(RAW_DIR, "jd_raw.csv")
JD_CLEAN_CSV = os.path.join(CLEAN_DIR, "jd_clean.csv")
SKILL_ONTOLOGY = os.path.join(META_DIR, "skill_ontology.json")
JOB_STANDARD_DICT = os.path.join(META_DIR, "job_standard_dict.csv")

# ============================================================
# 便捷路径别名
# ============================================================
JD_RAW_PATH = JD_RAW_CSV
JD_CLEAN_PATH = JD_CLEAN_CSV


def ensure_dirs():
    for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR, RAW_DIR, CLEAN_DIR, META_DIR, COLLECTION_DIR]:
        os.makedirs(d, exist_ok=True)
