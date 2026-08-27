"""
数据清洗工具 — HTML 清洗 / 语言检测 / 排序 / 规范化
"""

import html as html_mod
import re
from datetime import datetime
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """去除 HTML 标签和转义字符，返回纯文本"""
    if not text:
        return ""
    # HTML 转义字符还原
    text = html_mod.unescape(str(text))
    # BeautifulSoup 去标签
    # 使用标准库解析器，避免部署环境未安装 lxml 时整个清洗流程中断。
    text = BeautifulSoup(text, "html.parser").get_text() if "<" in text else text
    # 去除特殊空白
    text = text.replace(" ", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_language(text: str) -> str:
    """
    语言检测：中文字符比例判断，排除日文干扰。

    日文同时包含 CJK 汉字和假名 (ぁ-ゟ, ァ-ヿ)。
    如果假名数量 > 中文字符数量，判定为日文 (非中文)。
    """
    if not text:
        return "en"
    text_str = str(text)
    chinese_chars = len(re.findall(r"[一-鿿]", text_str))
    japanese_kana = len(re.findall(r"[぀-ゟ゠-ヿ]", text_str))

    # 日文: 假名多 → 不是中文
    if japanese_kana > chinese_chars * 0.5:
        return "en" if chinese_chars < 10 else "zh"
    return "zh" if chinese_chars > 5 else "en"


def get_time_slice(date=None) -> str:
    """返回当前时间切片，如 2026Q3"""
    d = date or datetime.now()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}"


def sort_jobs_by_language_and_priority(jobs: list) -> list:
    """中文优先，同语言内按 source_priority 升序"""
    def sort_key(j):
        lang = j.get("source_language", "en")
        priority = j.get("source_priority", 9)
        try:
            priority = int(priority)
        except (ValueError, TypeError):
            priority = 9
        return (0 if lang == "zh" else 1, priority)
    return sorted(jobs, key=sort_key)


def normalize_job_record(record: dict, fields: list) -> dict:
    """
    补全所有字段，清洗文本，自动填充缺失值。
    """
    try:
        from .skill_mapping import identify_skills
        from .job_standardize import standardize_job_name
    except ImportError:  # 脚本入口将 crawler 加入 sys.path
        from utils.skill_mapping import identify_skills
        from utils.job_standardize import standardize_job_name

    desc_raw = record.get("description", "")
    reqs_raw = record.get("requirements", "")
    desc_clean = clean_text(desc_raw)
    reqs_clean = clean_text(reqs_raw)

    combined_text = f"{desc_clean} {reqs_clean}"

    # 语言检测
    lang = record.get("source_language") or detect_language(combined_text)

    # 优先级
    priority = record.get("source_priority")
    if priority is None or priority == "":
        priority = 2 if lang == "zh" else 4

    # 岗位标准化
    job_title = record.get("job_title", "")
    std_name = record.get("standard_job_name") or standardize_job_name(job_title)

    # 技能：标题能提供关键的岗位领域证据，正文负责补充具体技术栈。
    skill_text = f"{job_title} {std_name} {combined_text}"
    identified_raw, identified_std = identify_skills(skill_text)
    skill_raw = record.get("skill_raw") or ";".join(identified_raw)
    skill_std = record.get("skill_standard") or ";".join(identified_std)

    # 时间
    time_slice = record.get("time_slice") or get_time_slice()

    # 证据分
    evidence = record.get("evidence_score")
    if evidence is None or evidence == "":
        if lang == "zh" and int(priority) == 1:
            evidence = 0.9
        elif lang == "zh":
            evidence = 0.8
        else:
            evidence = 0.75
    else:
        try:
            evidence = float(evidence)
        except (ValueError, TypeError):
            evidence = 0.75

    # 重复分
    dup = record.get("duplicate_score")
    if dup is None or dup == "":
        dup = 0.0
    try:
        dup = float(dup)
    except (ValueError, TypeError):
        dup = 0.0

    try:
        from .job_schema import enrich_job_record
    except ImportError:
        from utils.job_schema import enrich_job_record

    working = dict(record)
    working.update({
        "description": desc_clean,
        "requirements": reqs_clean,
        "standard_job_name": std_name,
        "skill_raw": str(skill_raw) if not isinstance(skill_raw, list) else ";".join(skill_raw),
        "skill_standard": str(skill_std) if not isinstance(skill_std, list) else ";".join(skill_std),
        "source_language": lang,
        "source_priority": str(priority),
        "time_slice": time_slice,
        "evidence_score": str(evidence),
        "duplicate_score": str(dup),
    })
    if not working.get("crawl_time"):
        working["crawl_time"] = datetime.now().strftime("%Y-%m-%d")
    working = enrich_job_record(working)

    result = {}
    for f in fields:
        val = working.get(f, "")
        if isinstance(val, list):
            val = ";".join(str(v) for v in val)
        elif val is None:
            val = ""
        result[f] = str(val)
    return result
