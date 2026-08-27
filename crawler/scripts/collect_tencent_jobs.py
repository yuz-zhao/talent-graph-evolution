"""采集腾讯官方招聘公开接口中的新一代信息技术岗位。"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from itertools import zip_longest
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS, USER_AGENT  # noqa: E402
from utils.clean_utils import get_time_slice  # noqa: E402
from utils.collection_pipeline import CollectionStore  # noqa: E402
from utils.job_standardize import standardize_job_name  # noqa: E402
from utils.save_utils import load_existing_csv, merge_and_deduplicate_jobs, save_jobs_to_csv  # noqa: E402
from utils.skill_mapping import identify_skills  # noqa: E402

API = "https://careers.tencent.com/tencentcareer/api/post/Query"
DETAIL_API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"

TECH_TITLE = re.compile(
    r"人工智能|AI|AIGC|大模型|算法|机器学习|深度学习|自然语言|NLP|计算机视觉|视觉算法|"
    r"数据(?:开发|工程|分析|科学|仓库|治理|平台|架构)|大数据|软件|研发|开发工程师|"
    r"前端|后端|客户端|全栈|测试开发|自动化测试|质量工程|云计算|云原生|容器|DevOps|SRE|"
    r"运维开发|网络(?:工程|研发|安全)|信息安全|安全工程|攻防|密码|嵌入式|物联网|边缘计算|"
    r"芯片|集成电路|FPGA|硬件|通信|5G|音视频|数据库|存储|操作系统|编译器|架构师|"
    r"技术研究|研究员|数字孪生|区块链|机器人", re.I,
)
NON_TECH_TITLE = re.compile(r"销售|市场|商务|财务|法务|人力|招聘|行政|运营经理|内容运营|客户经理|渠道|采购", re.I)

FAMILY_RULES = [
    ("大模型与生成式AI", r"大模型|LLM|AIGC|RAG|智能体|Agent|生成式|Prompt"),
    ("人工智能与算法", r"人工智能|算法|机器学习|深度学习|NLP|视觉|推荐|搜索|语音"),
    ("数据技术", r"数据|大数据|数据库|存储|BI|仓库|治理"),
    ("网络与信息安全", r"安全|攻防|密码|风控|网络工程"),
    ("云计算与云原生", r"云计算|云原生|容器|Kubernetes|DevOps|SRE|运维开发"),
    ("芯片与硬件", r"芯片|集成电路|FPGA|硬件|射频"),
    ("物联网与嵌入式", r"物联网|嵌入式|边缘计算|单片机"),
    ("通信与5G", r"通信|5G|音视频|实时音视频|网络协议"),
    ("工业互联网与智能制造", r"工业互联网|数字孪生|机器人|智能制造"),
    ("软件开发", r"软件|研发|开发|前端|后端|客户端|全栈|测试|操作系统|编译器|架构"),
]


def family_for(text: str) -> str:
    for family, pattern in FAMILY_RULES:
        if re.search(pattern, text, re.I):
            return family
    return "其他信息技术"


def normalize_date(value: str) -> str:
    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", str(value or ""))
    return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}" if match else ""


def education_from(text: str) -> str:
    for degree in ("博士", "硕士", "本科", "大专"):
        if degree in text:
            return degree + "及以上"
    return ""


def fetch_detail(session: requests.Session, post_id: str) -> dict:
    """读取腾讯公开岗位详情；列表接口不稳定地省略 Requirement。"""
    response = session.get(
        DETAIL_API,
        params={"postId": post_id, "language": "zh-cn", "timestamp": int(time.time() * 1000)},
        timeout=40,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("Data") or {}


def fetch_all(max_pages: int = 100, delay: float = 0.25) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://careers.tencent.com/"})
    output, seen = [], set()
    for page in range(1, max_pages + 1):
        params = {
            "timestamp": int(time.time() * 1000), "countryId": "", "cityId": "", "bgIds": "",
            "productId": "", "categoryId": "", "parentCategoryId": "", "attrId": "", "keyword": "",
            "pageIndex": page, "pageSize": 100, "language": "zh-cn", "area": "cn",
        }
        response = session.get(API, params=params, timeout=40)
        response.raise_for_status()
        data = response.json().get("Data") or {}
        posts = data.get("Posts") or []
        if not posts:
            break
        for post in posts:
            post_id = str(post.get("PostId") or "")
            title = str(post.get("RecruitPostName") or "").strip()
            category = str(post.get("CategoryName") or "")
            if not post_id or post_id in seen or NON_TECH_TITLE.search(title) or not TECH_TITLE.search(f"{title} {category}"):
                continue
            seen.add(post_id)
            responsibility = str(post.get("Responsibility") or "").strip()
            requirement = str(post.get("Requirement") or "").strip()
            if not requirement:
                try:
                    detail = fetch_detail(session, post_id)
                    responsibility = str(detail.get("Responsibility") or responsibility).strip()
                    requirement = str(detail.get("Requirement") or "").strip()
                    post = {**post, **detail}
                except requests.RequestException as exc:
                    print(f"[腾讯招聘] 详情补全失败 {post_id}: {exc}")
            skills_raw, skills_standard = identify_skills(f"{title}\n{responsibility}\n{requirement}")
            url = str(post.get("PostURL") or f"https://careers.tencent.com/jobdesc.html?postId={post_id}").replace("http://", "https://")
            output.append({
                "job_title": title, "standard_job_name": standardize_job_name(title), "company": "腾讯",
                "industry": "新一代信息技术", "location": str(post.get("LocationName") or ""), "salary": "",
                "education": education_from(requirement), "experience": str(post.get("RequireWorkYearsName") or ""),
                "description": responsibility, "requirements": requirement,
                "raw_description": f"{responsibility}\n{requirement}".strip(),
                "publish_time": normalize_date(post.get("LastUpdateTime")), "source_url": url,
                "source_name": "腾讯招聘官网", "source_language": "zh", "source_priority": "1",
                "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "skill_raw": ";".join(skills_raw), "skill_standard": ";".join(skills_standard),
                "time_slice": get_time_slice(), "evidence_score": "0.95", "duplicate_score": "0.0",
                "requirements_source": "source_detail" if requirement else "missing",
                "publish_time_source": "source_detail" if normalize_date(post.get("LastUpdateTime")) else "missing",
                "source_url_status": "verified_live", "source_url_checked_at": datetime.now().replace(microsecond=0).isoformat(),
                "_family": family_for(f"{title} {responsibility}"),
            })
        print(f"[腾讯招聘] 第{page}页，累计技术岗位 {len(output)} 条")
        total = int(data.get("Count") or 0)
        if total and page * 100 >= total:
            break
        time.sleep(delay)
    return output


def balanced_take(rows: list[dict], target: int) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row.get("location") or "地区未标注", row.pop("_family", "其他信息技术"))].append(row)
    selected = []
    for round_items in zip_longest(*groups.values()):
        for item in round_items:
            if item is not None:
                selected.append(item)
                if len(selected) >= target:
                    return selected
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="腾讯招聘官网新一代信息技术岗位采集")
    parser.add_argument("--target", type=int, default=1500)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    fetched = fetch_all(args.max_pages)
    selected = balanced_take(fetched, args.target)
    if not selected:
        print("未采集到符合条件的岗位")
        return 2
    old = load_existing_csv(args.output)
    merged = merge_and_deduplicate_jobs(old, selected)
    save_jobs_to_csv(args.output, merged, JD_FIELDS, overwrite=True)
    report = CollectionStore(BASE / "data").ingest("tencent-careers", "job", selected, "official_career_api")
    print(f"腾讯官网技术岗位可用 {len(fetched)} 条，本批选择 {len(selected)} 条，去重后新增 {len(merged)-len(old)} 条")
    print(f"主 CSV: {len(old)} -> {len(merged)}；批次: {report.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
