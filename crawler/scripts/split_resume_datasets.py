"""将历史混合简历拆成公开画像、匿名评测集和合成演示集。"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from utils.skill_mapping import extract_skill_matches  # noqa: E402

LEGACY = BASE / "data/quarantine/resume_clean_mixed_20260802.csv"
TREND = BASE / "data/bronze/github_trend.jsonl"
PUBLIC = BASE / "data/silver/profiles/profiles_github_public.csv"
EVALUATION = BASE / "data/clean/resumes_anonymized_evaluation.jsonl"
SYNTHETIC = BASE / "data/clean/resumes_synthetic_demo.csv"
MANIFEST = BASE / "data/reports/resume_dataset_split_report.json"

SURNAMES = "张王李赵刘陈杨黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文"
GIVEN = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平", "刚", "桂英", "子涵", "宇轩", "雨桐", "欣怡", "浩然", "梓轩"]


def aliases(count: int) -> list[str]:
    names = [surname + given for surname in SURNAMES for given in GIVEN]
    return names[:count]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    return rows


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def repo_skill_evidence(repo: dict) -> list[dict]:
    evidence = []
    channels = [("language", str(repo.get("primary_language") or ""))]
    channels += [("topic", str(topic)) for topic in (repo.get("topics") or [])]
    for channel, text in channels:
        for match in extract_skill_matches(text):
            evidence.append({
                "skill": match.standard, "raw": match.raw, "channel": channel,
                "repo_id": str(repo.get("repo_id") or ""), "repository": repo.get("full_name") or "",
                "repository_url": repo.get("html_url") or "", "evidence": text,
                "method": "public_repo_metadata_alias_rule_v3",
            })
    return evidence


def main() -> int:
    with LEGACY.open("r", encoding="utf-8-sig", newline="") as handle:
        legacy = list(csv.DictReader(handle))
    public_legacy = [row for row in legacy if row.get("source") == "github_public"]
    synthetic_legacy = [row for row in legacy if row.get("source") == "synthetic"]
    repos_by_owner = defaultdict(list)
    for repo in load_jsonl(TREND):
        owner = str(repo.get("owner") or "").casefold()
        if owner and repo.get("repo_id"):
            repos_by_owner[owner].append(repo)

    public_rows = []
    public_aliases = aliases(len(public_legacy))
    for old, public_alias in zip(public_legacy, public_aliases):
        login = str(old.get("username") or old.get("talent_id", "").removeprefix("gh_")).strip()
        evidence, seen = [], set()
        for repo in repos_by_owner.get(login.casefold(), []):
            for item in repo_skill_evidence(repo):
                key = (item["skill"].casefold(), item["repository"], item["channel"])
                if key not in seen:
                    seen.add(key); evidence.append(item)
        skills = list(dict.fromkeys(item["skill"] for item in evidence))
        public_rows.append({
            "profile_id": f"gh_{login.casefold()}", "github_login": login,
            "github_profile_url": f"https://github.com/{login}", "display_name": public_alias,
            "bio": "", "location": "", "company": "", "public_repos": "", "followers": "",
            "skills": json.dumps(skills, ensure_ascii=False),
            "skill_evidence": json.dumps(evidence, ensure_ascii=False),
            "evidence_repository_count": len({item["repository"] for item in evidence}),
            "public_profile_status": "identity_from_public_repository_owner;profile_api_not_refetched",
            "random_supplemented_fields": 0, "authorization_status": "publicly_disclosed_by_account_owner",
            "anonymization_status": "pseudonymized_for_display;public_login_retained_for_evidence", "data_usage": "technology_skill_evidence_only",
            "retention_until": "2027-08-02", "statistics_scope": "excluded_from_labor_market_statistics",
            "accuracy_evaluation_scope": "excluded",
        })

    demo_names = aliases(len(synthetic_legacy))
    synthetic_rows = []
    for index, (old, alias) in enumerate(zip(synthetic_legacy, demo_names), start=1):
        row = dict(old)
        row.update({
            "resume_id": old.get("talent_id") or f"demo_{index:04d}", "display_name": alias,
            "is_pseudonym": "true", "dataset_type": "synthetic_demo", "is_synthetic": "true",
            "authorization_status": "not_applicable_synthetic", "anonymization_status": "synthetic_no_personal_data",
            "data_usage": "ui_and_workflow_demo_only", "retention_until": "project_lifecycle",
            "statistics_scope": "excluded", "accuracy_evaluation_scope": "excluded",
        })
        row.pop("talent_id", None); row.pop("username", None); row.pop("bio", None)
        synthetic_rows.append(row)

    public_fields = [
        "profile_id", "github_login", "github_profile_url", "display_name", "bio", "location", "company",
        "public_repos", "followers", "skills", "skill_evidence", "evidence_repository_count",
        "public_profile_status", "random_supplemented_fields", "authorization_status", "anonymization_status",
        "data_usage", "retention_until", "statistics_scope", "accuracy_evaluation_scope",
    ]
    synthetic_fields = [
        "resume_id", "display_name", "is_pseudonym", "dataset_type", "is_synthetic", "talent_type",
        "skill_raw", "skill_standard", "education", "major", "degree", "school", "projects", "certificates",
        "target_jobs", "location", "company", "public_repos", "followers", "source", "crawl_time",
        "authorization_status", "anonymization_status", "data_usage", "retention_until",
        "statistics_scope", "accuracy_evaluation_scope",
    ]
    write_csv(PUBLIC, public_fields, public_rows)
    write_csv(SYNTHETIC, synthetic_fields, synthetic_rows)
    EVALUATION.parent.mkdir(parents=True, exist_ok=True); EVALUATION.write_text("", encoding="utf-8")
    report = {
        "legacy_records": len(legacy), "github_public_profiles": len(public_rows),
        "synthetic_demo_resumes": len(synthetic_rows), "anonymized_evaluation_resumes": 0,
        "public_random_supplemented_fields": 0,
        "public_profiles_with_repository_skill_evidence": sum(bool(json.loads(row["skill_evidence"])) for row in public_rows),
        "evaluation_status": "awaiting_authorized_human_labeled_resumes",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
