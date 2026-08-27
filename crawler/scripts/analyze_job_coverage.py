"""生成新一代信息技术岗位的地区、岗位族和来源覆盖矩阵。"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FAMILIES = [
    ("大模型与生成式AI", r"大模型|LLM|AIGC|RAG|Agent|生成式|prompt|language model|generative ai"),
    ("人工智能与算法", r"人工智能|算法|机器学习|深度学习|NLP|计算机视觉|AI Engineer|Machine Learning|Data Scientist"),
    ("数据技术", r"数据分析|数据开发|数据工程|数据仓库|数据治理|Data Engineer|Data Analyst|Analytics Engineer|BI Engineer"),
    ("云计算与云原生", r"云计算|云原生|Cloud|Kubernetes|Platform Engineer|SRE|DevOps"),
    ("网络与信息安全", r"网络安全|信息安全|安全工程|Security|Cyber|SOC|渗透测试"),
    ("芯片与硬件", r"芯片|集成电路|FPGA|EDA|硬件|Firmware|Hardware|Semiconductor"),
    ("物联网与嵌入式", r"物联网|嵌入式|边缘计算|IoT|Embedded|STM32|单片机"),
    ("通信与5G", r"通信|5G|基站|射频|Telecom|Wireless|Network Engineer"),
    ("工业互联网与智能制造", r"工业互联网|数字孪生|PLC|CNC|SMT|机器人|智能制造|Automation|Robotics"),
    ("软件开发", r"软件|开发工程师|前端|后端|全栈|测试开发|Software|Developer|Backend|Frontend|Full.?stack|QA Engineer"),
]

CHINA_REGIONS = ["北京", "上海", "深圳", "广州", "杭州", "南京", "苏州", "成都", "武汉", "西安", "天津", "重庆", "合肥", "长沙", "济南", "青岛", "大连", "沈阳", "哈尔滨", "长春", "大庆"]


def families_for(text: str) -> list[str]:
    """岗位族允许多标签，避免“含 AI 的 5G 岗位”只被记入 AI。"""
    matched = [name for name, pattern in FAMILIES if re.search(pattern, text, re.I)]
    return matched or ["其他信息技术"]


def region_for(location: str, language: str) -> str:
    value = str(location or "")
    for city in CHINA_REGIONS:
        if city in value:
            return city
    if re.search(r"remote|worldwide|anywhere", value, re.I):
        return "远程/全球"
    if language == "zh":
        return value.split("·")[0].split("-")[0].strip() or "国内地区未标注"
    return "海外其他地区"


def main() -> None:
    path = ROOT / "crawler/data/silver/jobs/jd_clean.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))
    # 地区配额只针对我国岗位主数据；英文岗位是参考集，不进入地区缺口分母。
    rows = [
        row for row in all_rows
        if row.get("statistics_scope") == "china_main"
        or (not row.get("statistics_scope") and row.get("source_language") == "zh")
    ]
    family_counts, region_counts, matrix, source_counts = Counter(), Counter(), defaultdict(Counter), Counter()
    classified = []
    for row in rows:
        text = " ".join(row.get(k, "") for k in ("job_title", "standard_job_name", "description", "requirements", "skill_raw", "skill_standard"))
        families = [item for item in str(row.get("job_family") or "").split(";") if item] or families_for(text)
        region = row.get("region_standard") or region_for(row.get("location", ""), row.get("source_language", ""))
        region_counts[region] += 1; source_counts[row["source_name"]] += 1
        for family in families:
            family_counts[family] += 1
            matrix[region][family] += 1
        classified.append({"source": row["source_name"], "title": row["job_title"], "region": region, "families": families, "url": row["source_url"]})
    priority_regions = CHINA_REGIONS
    gaps = []
    for region in priority_regions:
        for family, _ in FAMILIES:
            count = matrix[region][family]
            if count < 50:
                gaps.append({"region": region, "family": family, "count": count, "target": 50, "gap": 50 - count})
    report = {
        "scope": "china_main", "total_jobs": len(rows),
        "excluded_overseas_reference_jobs": len(all_rows) - len(rows),
        "source_counts": dict(source_counts), "family_counts": dict(family_counts),
        "region_counts": dict(region_counts.most_common()), "region_family_matrix": {r: dict(c) for r, c in matrix.items()},
        "priority_gaps": sorted(gaps, key=lambda x: (-x["gap"], x["region"], x["family"])),
        "classified_sample": classified[:100],
    }
    output = ROOT / "crawler/data/reports/job_coverage_matrix.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total": len(rows), "families": family_counts, "top_regions": region_counts.most_common(15), "gap_cells": len(gaps)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
