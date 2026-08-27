"""岗位数据 v2 模式：稳定标识、版本、技能证据和统计口径。

本模块只根据岗位原文和来源元数据生成可复现字段，不调用网络，也不填造
网页未公开的信息。采集器和离线迁移脚本共用这里的规则。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

try:  # 兼容 ``python crawler/main.py`` 与 ``python -m pytest`` 两种入口
    from .skill_mapping import extract_skill_matches
    from .job_standardize import standardize_job_title
except ImportError:  # pragma: no cover - 脚本入口
    from utils.skill_mapping import extract_skill_matches
    from utils.job_standardize import standardize_job_title


PREFERRED_MARKERS = re.compile(
    r"优先|加分|更佳|preferred|preference|nice[ -]to[ -]have|bonus|plus\b|desirable",
    re.I,
)
REQUIRED_MARKERS = re.compile(
    r"必须|要求|需具备|具备|熟悉|掌握|精通|能够|required|requirement|must\b|"
    r"proficien|experience with|knowledge of|hands-on",
    re.I,
)

FAMILY_RULES = (
    ("大模型与生成式AI", r"大模型|LLM|AIGC|RAG|智能体|AI Agent|生成式|Prompt"),
    ("人工智能与算法", r"人工智能|算法|机器学习|深度学习|NLP|计算机视觉|推荐|搜索|语音"),
    ("数据技术", r"数据分析|数据开发|数据工程|数据仓库|数据治理|数据库|大数据|Data Engineer|Data Analyst"),
    ("云计算与云原生", r"云计算|云原生|Cloud|Kubernetes|容器|SRE|DevOps"),
    ("网络与信息安全", r"网络安全|信息安全|安全工程|Security|Cyber|渗透测试|攻防"),
    ("芯片与硬件", r"芯片|集成电路|FPGA|EDA|硬件|Firmware|Hardware|Semiconductor"),
    ("物联网与嵌入式", r"物联网|嵌入式|边缘计算|IoT|Embedded|STM32|单片机"),
    ("通信与5G", r"通信|5G|6G|基站|射频|Telecom|Wireless|光网络|传输"),
    ("工业互联网与智能制造", r"工业互联网|数字孪生|PLC|CNC|SMT|机器人|智能制造|Automation|Robotics"),
    ("软件开发", r"软件|开发工程师|研发工程师|前端|后端|全栈|测试开发|Software|Developer|Backend|Frontend|QA Engineer"),
)

CHINA_CITIES = (
    "北京", "上海", "深圳", "广州", "杭州", "南京", "苏州", "成都", "武汉", "西安",
    "天津", "重庆", "合肥", "长沙", "济南", "青岛", "大连", "沈阳", "哈尔滨", "长春", "大庆",
)
OVERSEAS_LOCATION_MARKERS = (
    "新加坡", "帕罗奥多", "东京", "伦敦", "曼谷", "洛杉矶", "阿姆斯特丹", "迪拜",
    "首尔", "雅加达", "法兰克福", "巴黎", "奥克兰", "India", "United States",
    "United Kingdom", "Thailand", "Indonesia", "Japan", "Korea", "Germany", "France",
    "Netherlands", "New Zealand", "Singapore", "Dubai",
)

KNOWN_COMPANY_TYPES = {
    "腾讯": ("民营", "known_company"),
    "中国信息通信研究院": ("科研院所", "known_institution"),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9一-龥]+", "", str(value or "").casefold())


def _digest(prefix: str, value: str, length: int = 16) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def _source_key(value: str) -> str:
    mapping = {
        "腾讯招聘官网": "tencent", "中国电信招聘官网": "chinatelecom",
        "中国信通院招聘官网": "caict", "智联招聘": "zhaopin", "猎聘": "liepin",
        "国家大学生就业服务平台": "ncss", "Greenhouse": "greenhouse",
        "Arbeitnow": "arbeitnow", "Remotive": "remotive",
    }
    return mapping.get(value, re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "source")


def source_job_id(record: dict) -> str:
    """从公开 URL 提取来源主键；无法提取时对规范 URL 做稳定哈希。"""
    existing = str(record.get("source_job_id") or "").strip()
    source = str(record.get("source_name") or "未知来源").strip()
    url = str(record.get("source_url") or "").strip()
    if existing and not url:
        return existing
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    candidates = (
        "postId", "postIdsAry", "postIdEnc", "gh_jid", "jobId", "job_id",
        "positionId", "position_id", "id",
    )
    raw_id = ""
    for key in candidates:
        values = query.get(key)
        if values and values[0]:
            raw_id = values[0]
            break
    source_key = _source_key(source)
    if not raw_id and source_key == "zhaopin":
        filename = parsed.path.rstrip("/").split("/")[-1]
        raw_id = re.sub(r"\.(?:html?|shtml)$", "", filename, flags=re.I)
    if not raw_id and source_key == "arbeitnow" and parsed.path:
        raw_id = hashlib.sha256(parsed.path.rstrip("/").encode("utf-8")).hexdigest()[:20]
    if not raw_id:
        parts = [p for p in parsed.path.split("/") if p]
        for part in reversed(parts):
            candidate = re.sub(r"\.(?:html?|shtml)$", "", part, flags=re.I)
            if candidate.casefold() in {"job", "jobs", "jobdetail", "position", "detail", "careers"}:
                continue
            if re.fullmatch(r"[A-Za-z0-9_-]{5,}", candidate):
                raw_id = candidate
                break
    if raw_id:
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_id).strip("-")
        return f"SRCJOB_{source_key}_{safe_id}"
    natural = "|".join((source, url, str(record.get("company") or ""), str(record.get("job_title") or ""), str(record.get("location") or "")))
    return _digest(f"SRCJOB_{source_key}", natural)


def canonical_job_id(record: dict) -> str:
    name = str(record.get("standard_job_name") or record.get("job_title") or "未标准化岗位")
    return _digest("CJOB", _norm(name), 14)


def version_id(record: dict, sid: str) -> str:
    core = "|".join(str(record.get(key) or "").strip() for key in (
        "job_title", "company", "location", "description", "requirements", "publish_time",
    ))
    return _digest("JVER", f"{sid}|{core}", 18)


def _date_part(value: str) -> str:
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", str(value or ""))
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return ""


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?；;])\s*|\n+", str(text or ""))
    return [re.sub(r"\s+", " ", part).strip() for part in parts if part.strip()]


def _snippet(text: str, start: int, raw: str) -> str:
    for sentence in _sentences(text):
        if raw.casefold() in sentence.casefold():
            return sentence[:300]
    left = max(0, start - 80)
    right = min(len(text), start + len(raw) + 120)
    return re.sub(r"\s+", " ", text[left:right]).strip()[:300]


def build_skill_fields(record: dict) -> dict:
    """按要求、职责、标题的证据强度生成技能关系，不凭岗位类别硬填技能。"""
    fields = (
        ("requirements", str(record.get("requirements") or "")),
        ("description", str(record.get("description") or "")),
        ("job_title", str(record.get("job_title") or "")),
        ("standard_job_name", str(record.get("standard_job_name") or "")),
    )
    evidence_by_skill: dict[str, dict] = {}
    for field, text in fields:
        for match in extract_skill_matches(text):
            if match.standard in evidence_by_skill:
                continue
            snippet = _snippet(text, match.start, match.raw)
            preferred = bool(PREFERRED_MARKERS.search(snippet))
            explicit_required = field == "requirements" and bool(REQUIRED_MARKERS.search(snippet))
            relation = "preferred" if preferred else "required" if explicit_required else "mentioned"
            confidence = 0.95 if explicit_required else 0.92 if preferred else 0.88 if field == "requirements" else 0.82 if field == "description" else 0.76
            evidence_by_skill[match.standard] = {
                "skill": match.standard,
                "raw": match.raw,
                "relation": relation,
                "field": field,
                "snippet": snippet,
                "method": "alias_rule_v3",
                "confidence": confidence,
            }
    # RAG/AI/CV 等短缩写需要跨字段技术上下文；全局识别后仍回到具体字段取证。
    global_text = "\n".join(text for _field, text in fields if text)
    for match in extract_skill_matches(global_text):
        if match.standard in evidence_by_skill:
            continue
        for field, text in fields:
            start = text.casefold().find(match.raw.casefold())
            if start < 0:
                continue
            snippet = _snippet(text, start, match.raw)
            preferred = bool(PREFERRED_MARKERS.search(snippet))
            explicit_required = field == "requirements" and bool(REQUIRED_MARKERS.search(snippet))
            relation = "preferred" if preferred else "required" if explicit_required else "mentioned"
            confidence = 0.95 if explicit_required else 0.92 if preferred else 0.88 if field == "requirements" else 0.82 if field == "description" else 0.76
            evidence_by_skill[match.standard] = {
                "skill": match.standard, "raw": match.raw, "relation": relation,
                "field": field, "snippet": snippet, "method": "alias_rule_v3",
                "confidence": confidence,
            }
            break
    evidence = list(evidence_by_skill.values())
    required = [item["skill"] for item in evidence if item["relation"] == "required"]
    preferred = [item["skill"] for item in evidence if item["relation"] == "preferred"]
    mentioned = [item["skill"] for item in evidence if item["relation"] == "mentioned"]
    raw = [item["raw"] for item in evidence]
    avg = round(sum(item["confidence"] for item in evidence) / len(evidence), 4) if evidence else 0.0
    return {
        "skill_raw": ";".join(raw),
        "skill_standard": ";".join(item["skill"] for item in evidence),
        "required_skills": ";".join(required),
        "preferred_skills": ";".join(preferred),
        "mentioned_skills": ";".join(mentioned),
        "skill_evidence": json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
        "skill_extraction_method": "alias_rule_v3",
        "skill_confidence": str(avg),
    }


def company_type(record: dict) -> tuple[str, str]:
    existing = str(record.get("company_type") or "").strip()
    if existing:
        return existing, str(record.get("company_type_source") or "existing")
    company = str(record.get("company") or "").strip()
    source = str(record.get("source_name") or "")
    for prefix, result in KNOWN_COMPANY_TYPES.items():
        if company.startswith(prefix):
            return result
    if company.startswith("中国电信"):
        return "央企", "known_company_group"
    if re.search(r"大学|学院|学校|医院|事业单位", company):
        return "事业单位", "organization_keyword"
    if re.search(r"研究院|研究所|实验室", company):
        return "科研院所", "organization_keyword"
    if str(record.get("source_language") or "") == "en" or source in {"Greenhouse", "Arbeitnow", "Remotive"}:
        return "外企", "overseas_reference_source"
    return "未知", "unverified"


def job_families(record: dict) -> str:
    text = " ".join(str(record.get(key) or "") for key in (
        "job_title", "standard_job_name", "description", "requirements", "skill_standard",
    ))
    matched = [name for name, pattern in FAMILY_RULES if re.search(pattern, text, re.I)]
    return ";".join(matched or ["其他信息技术"])


def region_standard(record: dict) -> str:
    location = str(record.get("location") or "")
    for city in CHINA_CITIES:
        if city in location:
            return city
    if re.search(r"remote|worldwide|anywhere", location, re.I):
        return "远程/全球"
    if str(record.get("source_language") or "") == "zh":
        return re.split(r"[-·,/，]", location)[0].strip() or "国内地区未标注"
    return "海外其他地区"


def enrich_job_record(record: dict) -> dict:
    """返回带 v2 派生字段的新字典；输入字典不会被修改。"""
    result = dict(record)
    sid = source_job_id(result)
    result["source_job_id"] = sid
    result["canonical_job_id"] = canonical_job_id(result)
    result["version_id"] = version_id(result, sid)
    result["valid_from"] = str(result.get("valid_from") or _date_part(result.get("publish_time")) or _date_part(result.get("crawl_time")))
    result["valid_to"] = str(result.get("valid_to") or "")
    if not str(result.get("raw_description") or "").strip():
        parts = []
        if str(result.get("description") or "").strip():
            parts.append(f"岗位职责：{str(result['description']).strip()}")
        if str(result.get("requirements") or "").strip():
            parts.append(f"任职要求：{str(result['requirements']).strip()}")
        result["raw_description"] = "\n".join(parts)
    result.update(build_skill_fields(result))
    ctype, csource = company_type(result)
    result["company_type"] = ctype
    result["company_type_source"] = csource
    result["publish_time_source"] = str(result.get("publish_time_source") or ("source_page" if result.get("publish_time") else "missing"))
    result["requirements_source"] = str(result.get("requirements_source") or ("source_page" if result.get("requirements") else "missing"))
    url = str(result.get("source_url") or "").strip()
    result["source_url_status"] = str(result.get("source_url_status") or ("syntax_valid" if re.match(r"^https?://", url, re.I) else "invalid"))
    result["source_url_checked_at"] = str(result.get("source_url_checked_at") or "")
    location = str(result.get("location") or "")
    is_overseas = (
        str(result.get("source_language") or "") == "en"
        or any(marker.casefold() in location.casefold() for marker in OVERSEAS_LOCATION_MARKERS)
    )
    result["statistics_scope"] = "overseas_reference" if is_overseas else "china_main"
    result["data_provenance"] = str(result.get("data_provenance") or "observed")
    result["is_synthetic"] = "true" if str(result.get("is_synthetic") or "").casefold() == "true" else "false"
    result["lifecycle_status"] = str(result.get("lifecycle_status") or "active")
    mapping=standardize_job_title(str(result.get("job_title") or ""))
    result["standard_job_name"]=mapping.standard_job_name
    result["job_family"]=mapping.job_family
    result["job_level"]=mapping.job_level
    result["job_direction"]=mapping.job_direction
    result["business_scene"]=mapping.business_scene
    result["job_mapping_confidence"]=f"{mapping.confidence:.2f}"
    result["job_mapping_method"]=mapping.mapping_method
    result["job_mapping_evidence"]=mapping.mapping_evidence
    result["region_standard"] = region_standard(result)
    return result


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
