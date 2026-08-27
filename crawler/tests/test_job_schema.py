import json

from crawler.config.settings import JD_FIELDS
from crawler.utils.clean_utils import normalize_job_record
from crawler.utils.job_schema import enrich_job_record


def base_record(**overrides):
    row = {
        "job_title": "大模型应用开发工程师",
        "standard_job_name": "大模型应用开发工程师",
        "company": "腾讯",
        "location": "深圳",
        "description": "负责使用 Python 和 LangChain 建设大模型应用。",
        "requirements": "要求熟练掌握 Python；具有 RAG 项目经验者优先。",
        "publish_time": "2026-08-01",
        "source_url": "https://careers.tencent.com/jobdesc.html?postId=123456789",
        "source_name": "腾讯招聘官网",
        "source_language": "zh",
        "crawl_time": "2026-08-02 10:00:00",
    }
    row.update(overrides)
    return row


def test_ids_are_stable_and_version_changes_with_content():
    first = enrich_job_record(base_record())
    second = enrich_job_record(base_record())
    changed = enrich_job_record(base_record(requirements="要求熟练掌握 Python 和 PyTorch。"))
    assert first["source_job_id"] == second["source_job_id"]
    assert first["canonical_job_id"] == second["canonical_job_id"]
    assert first["version_id"] == second["version_id"]
    assert first["version_id"] != changed["version_id"]


def test_required_preferred_and_evidence_are_separated():
    row = enrich_job_record(base_record())
    assert "Python" in row["required_skills"].split(";")
    assert "检索增强生成" in row["preferred_skills"].split(";")
    evidence = json.loads(row["skill_evidence"])
    assert evidence
    assert all(item["snippet"] and item["field"] and item["confidence"] for item in evidence)


def test_english_is_reference_and_chinese_is_main_scope():
    assert enrich_job_record(base_record())["statistics_scope"] == "china_main"
    en = enrich_job_record(base_record(source_language="en", source_name="Greenhouse"))
    assert en["statistics_scope"] == "overseas_reference"
    overseas_zh = enrich_job_record(base_record(location="新加坡", source_language="zh"))
    assert overseas_zh["statistics_scope"] == "overseas_reference"


def test_normalizer_outputs_complete_v2_schema():
    row = normalize_job_record(base_record(), JD_FIELDS)
    assert list(row) == JD_FIELDS
    assert row["raw_description"]
    assert row["skill_evidence"]
    assert row["is_synthetic"] == "false"
