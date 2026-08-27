"""统一采集批次、增量去重和质量报告。

该模块不负责访问具体网站。各数据源采集器只需返回 ``list[dict]``，
这里负责补充审计字段、保存不可变批次、维护最新状态并生成报告。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from .time_utils import normalize_source_time


UTC = timezone.utc
COLLECTION_FIELDS = (
    "record_id", "data_type", "source_platform", "source_type",
    "source_url", "source_published_at", "crawled_at", "first_seen_at",
    "last_seen_at", "crawl_batch_id", "content_hash", "content",
    "payload", "collection_status", "changed_fields", "previous_content_hash",
    "lifecycle_status", "consecutive_misses", "evidence_snippets",
    "bronze_batch_id", "bronze_record_id", "lineage_uri",
    "publish_time_raw", "time_precision", "time_source", "time_parse_confidence",
)

AUDIT_FIELDS = (
    "job_title", "title", "standard_job_name", "company", "location", "salary",
    "education", "experience", "description", "requirements", "skill_standard",
    "publish_time", "summary", "content",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def new_batch_id(source: str, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    safe_source = source_slug(source)
    return f"{moment:%Y%m%dT%H%M%SZ}_{safe_source}_{uuid.uuid4().hex[:8]}"

def source_slug(source: str) -> str:
    aliases={"国家大学生就业服务平台":"ncss","智联招聘":"zhaopin","猎聘":"liepin","腾讯招聘官网":"tencent-careers","中国电信招聘":"china-telecom-careers","中国信通院招聘":"caict-careers"}
    value=aliases.get(str(source or '').strip(),str(source or '').strip())
    slug=re.sub(r"[^a-zA-Z0-9_-]+","-",value).strip("-").lower()
    if not slug: raise ValueError(f"非法或空白数据源名称: {source!r}")
    return slug


def canonical_url(value: str) -> str:
    url = (value or "").strip()
    return url[:-1] if url.endswith("/") else url


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text_content(record: dict) -> str:
    preferred = (
        "raw_description", "description", "requirements", "summary", "abstract", "content",
        "readme", "body_text", "job_title", "title", "tech_name", "course_name", "certificate_name", "display_name", "syllabus", "skills", "skill_evidence",
    )
    parts = []
    for key in preferred:
        value = record.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            parts.append(str(value).strip())
    return "\n".join(parts)


def content_hash(record: dict) -> str:
    ignored = {
        "crawl_time", "crawled_at", "first_seen_at", "last_seen_at",
        "crawl_batch_id", "content_hash", "collection_status", "observed_at",
    }
    stable = {k: v for k, v in record.items() if k not in ignored}
    return hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()


def record_identity(record: dict, source: str, data_type: str) -> str:
    repository_id = str(record.get("repo_id") or "").strip()
    url = canonical_url(record.get("source_url") or record.get("html_url") or record.get("official_url") or record.get("github_profile_url") or record.get("abs_url") or record.get("article_url") or record.get("url") or "")
    if data_type == "technology_project" and repository_id:
        raw = f"{source}|{data_type}|repo_id|{repository_id}"
    elif url:
        raw = f"{source}|{data_type}|url|{url}"
    else:
        natural = "|".join(str(record.get(k, "")).strip() for k in (
            "company", "job_title", "location", "title", "tech_name", "full_name", "id",
        ))
        raw = f"{source}|{data_type}|natural|{natural}|{content_hash(record)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_publish_time(record: dict) -> str:
    for key in ("source_published_at", "publish_time", "published_at", "created_at"):
        value = record.get(key)
        if value:
            return str(value).strip()
    return ""


@dataclass
class BatchReport:
    batch_id: str
    source: str
    data_type: str
    started_at: str
    finished_at: str = ""
    status: str = "running"
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    suspected_missing: int = 0
    expired: int = 0
    reopened: int = 0
    changed_records: int = 0
    missing_url: int = 0
    missing_published_at: int = 0
    missing_content: int = 0
    duplicate_in_batch: int = 0
    parsed: int = 0
    normalized: int = 0
    validated: int = 0
    failure_reasons: dict | None = None
    error: str = ""
    bronze_path: str = ""
    gold_path: str = ""
    failure_path: str = ""
    quality_rule_version: str = "quality_rules_v2"

    @property
    def valid(self) -> int:
        return self.inserted + self.updated + self.unchanged

    def quality(self) -> dict:
        denominator = max(self.fetched, 1)
        base = {
            "source_url_coverage": round(max(0, self.fetched - self.missing_url) / denominator, 4),
            "published_at_coverage": round(max(0, self.fetched - self.missing_published_at) / denominator, 4),
            "content_coverage": round(max(0, self.fetched - self.missing_content) / denominator, 4),
            "rejection_rate": round(self.rejected / max(self.fetched, 1), 4),
            "validity_rate": round(self.valid / denominator, 4),
            "uniqueness_rate": round(max(0, self.fetched - self.duplicate_in_batch) / denominator, 4),
        }
        thresholds={
            "job":{"url":.95,"content":.95,"published":.95,"validity":.90,"uniqueness":.95},
            "paper":{"url":.98,"content":.98,"published":.98,"validity":.95,"uniqueness":.98},
            "technology_project":{"url":.98,"content":.90,"validity":.90,"uniqueness":.98},
            "technology_article":{"url":.95,"content":.95,"published":.98,"validity":.90,"uniqueness":.95},
            "course":{"url":.95,"content":.90,"validity":.90,"uniqueness":.95},
            "certificate":{"url":.95,"content":.90,"validity":.90,"uniqueness":.95},
        }
        rule=thresholds.get(self.data_type,{"url":.90,"content":.90,"validity":.85,"uniqueness":.90})
        base["rules"]={"version":"quality_rules_v2",**rule}
        checks = [
            base["source_url_coverage"] >= rule["url"],
            base["content_coverage"] >= rule["content"],
            base["validity_rate"] >= rule["validity"],
            base["uniqueness_rate"] >= rule["uniqueness"],
        ]
        if "published" in rule:
            checks.append(base["published_at_coverage"] >= rule["published"])
        base["passed"] = all(checks)
        return base

    def to_dict(self) -> dict:
        result = asdict(self)
        result["valid"] = self.valid
        result["quality"] = self.quality()
        return result


class CollectionStore:
    """文件型采集存储，适合比赛和单机部署，后续可平移到数据库。"""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        operations = self.root / ".ops" / "collection"
        self.batch_dir = operations / "batches"
        self.bronze_dir = self.root / "bronze" / "collection"
        self.gold_dir = self.root / "gold" / "records"
        self.rollback_dir = operations / "rollback"
        self.state_dir = operations / "state"
        self.report_dir = self.root / "reports" / "collection"
        self.failure_dir = self.root / "quarantine" / "collection_failures"
        for directory in (self.batch_dir, self.bronze_dir, self.gold_dir, self.rollback_dir, self.state_dir, self.report_dir, self.failure_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def _state_path(self, source: str, data_type: str) -> Path:
        safe = f"{source_slug(source)}_{source_slug(data_type)}"
        return self.state_dir / f"{safe}.jsonl"

    def _load_state(self, source: str, data_type: str) -> dict[str, dict]:
        path = self._state_path(source, data_type)
        state = {}
        if not path.exists():
            return state
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    state[item["record_id"]] = item
                except (json.JSONDecodeError, KeyError):
                    continue
        return state

    @staticmethod
    def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _field_changes(previous_payload: dict, current_payload: dict) -> list[dict]:
        changes = []
        for field in AUDIT_FIELDS:
            before = str(previous_payload.get(field, "") or "").strip()
            after = str(current_payload.get(field, "") or "").strip()
            if before != after:
                changes.append({"field": field, "before": before[:1000], "after": after[:1000]})
        return changes

    @staticmethod
    def _evidence_snippets(payload: dict) -> list[dict]:
        snippets = []
        for field in ("job_title", "raw_description", "description", "requirements", "skill_standard"):
            value = str(payload.get(field, "") or "").strip()
            if value:
                snippets.append({"field": field, "text": value[:500]})
        return snippets

    def ingest(self, source: str, data_type: str, records: Iterable[dict],
               source_type: str = "public_api", batch_id: str | None = None,
               complete_snapshot: bool = False, expire_after_misses: int = 2,
               fetched_count: int | None = None,
               pipeline_failures: Iterable[dict] | None = None,
               stage_counts: dict | None = None) -> BatchReport:
        started = utc_now()
        source=source_slug(source); data_type=source_slug(data_type)
        batch_id = batch_id or new_batch_id(source)
        report = BatchReport(batch_id, source, data_type, started)
        failures = list(pipeline_failures or [])
        stages = stage_counts or {}
        report.parsed = int(stages.get("parsed", 0))
        report.normalized = int(stages.get("normalized", 0))
        report.validated = int(stages.get("validated", 0))
        report.failure_reasons = {}
        state = self._load_state(source, data_type)
        batch_records = []
        seen_ids: set[str] = set()

        raw_records=list(records)
        report.fetched = int(fetched_count if fetched_count is not None else len(raw_records))
        report.rejected = len(failures)
        for failure in failures:
            reason = str(failure.get("reason") or "unknown")
            report.failure_reasons[reason] = report.failure_reasons.get(reason, 0) + 1
            missing = set(failure.get("missing_fields") or [])
            report.missing_url += int("source_url" in missing)
            report.missing_published_at += int("published_at" in missing)
            report.missing_content += int("content" in missing)
        bronze_path=self.bronze_dir/f"{batch_id}.jsonl"
        bronze=[]
        for index,raw in enumerate(raw_records):
            bronze_id=hashlib.sha256(f"{batch_id}:{index}:{canonical_json(raw)}".encode()).hexdigest()
            bronze.append({"bronze_record_id":bronze_id,"crawl_batch_id":batch_id,"source_platform":source,"data_type":data_type,"fetched_at":started,"raw_payload":raw})
        self._write_jsonl(bronze_path,bronze);report.bronze_path=str(bronze_path.relative_to(self.root)).replace('\\','/')
        state_path=self._state_path(source,data_type)
        if state_path.exists():
            backup=self.rollback_dir/f"{batch_id}__{state_path.name}.bak";backup.write_bytes(state_path.read_bytes())
        try:
            for index,raw in enumerate(raw_records):
                if not isinstance(raw, dict):
                    report.rejected += 1
                    failures.append({"stage":"parse","reason":"not_an_object","record_index":index})
                    continue
                url = canonical_url(raw.get("source_url") or raw.get("html_url") or raw.get("official_url") or raw.get("github_profile_url") or raw.get("abs_url") or raw.get("article_url") or raw.get("url") or "")
                body = text_content(raw)
                publish_info = normalize_source_time(source_publish_time(raw), started)
                published = publish_info["source_published_at"]
                if not url:
                    report.missing_url += 1
                if not published:
                    report.missing_published_at += 1
                if not body:
                    report.missing_content += 1
                if not url and not body:
                    report.rejected += 1
                    failures.append({"stage":"validate","reason":"missing_url_and_content","record_index":index,"missing_fields":["source_url","content"],"bronze_record_id":bronze[index]["bronze_record_id"]})
                    continue

                rid = record_identity(raw, source, data_type)
                if rid in seen_ids:
                    report.rejected += 1
                    report.duplicate_in_batch += 1
                    report.failure_reasons["duplicate_in_batch"] = report.failure_reasons.get("duplicate_in_batch", 0) + 1
                    failures.append({"stage":"deduplicate","reason":"duplicate_in_batch","record_index":index,"record_id":rid,"source_url":url,"bronze_record_id":bronze[index]["bronze_record_id"]})
                    continue
                digest = content_hash(raw)
                previous = state.get(rid)
                seen_ids.add(rid)
                status = "inserted"
                first_seen = started
                changes: list[dict] = []
                previous_hash = ""
                reopened = False
                if previous:
                    first_seen = previous.get("first_seen_at") or started
                    status = "unchanged" if previous.get("content_hash") == digest else "updated"
                    previous_hash = previous.get("content_hash", "")
                    if status == "updated":
                        changes = self._field_changes(previous.get("payload") or {}, raw)
                        report.changed_records += 1
                    reopened = previous.get("lifecycle_status") in {"suspected_missing", "expired"}
                    if reopened:
                        report.reopened += 1

                if status == "inserted":
                    report.inserted += 1
                elif status == "updated":
                    report.updated += 1
                else:
                    report.unchanged += 1

                normalized = {
                    "record_id": rid,
                    "data_type": data_type,
                    "source_platform": source,
                    "source_type": source_type,
                    "source_url": url,
                    "source_published_at": published,
                    "publish_time_raw": publish_info["publish_time_raw"],
                    "time_precision": publish_info["time_precision"],
                    "time_source": publish_info["time_source"],
                    "time_parse_confidence": publish_info["time_parse_confidence"],
                    "crawled_at": started,
                    "first_seen_at": first_seen,
                    "last_seen_at": started,
                    "crawl_batch_id": batch_id,
                    "content_hash": digest,
                    "content": body,
                    "payload": raw,
                    "collection_status": status,
                    "changed_fields": changes,
                    "previous_content_hash": previous_hash,
                    "lifecycle_status": "reopened" if reopened else "active",
                    "consecutive_misses": 0,
                    "evidence_snippets": self._evidence_snippets(raw),
                    "bronze_batch_id": batch_id,
                    "bronze_record_id": bronze[index]["bronze_record_id"],
                    "lineage_uri": f"bronze/collection/{batch_id}.jsonl#{bronze[index]['bronze_record_id']}",
                }
                state[rid] = normalized
                batch_records.append(normalized)

            # 只有采集器明确声明“本次是完整快照”时，才允许据此推断岗位下线。
            if complete_snapshot:
                for rid, previous in list(state.items()):
                    if rid in seen_ids or previous.get("source_platform") != source:
                        continue
                    misses = int(previous.get("consecutive_misses") or 0) + 1
                    lifecycle = "expired" if misses >= max(expire_after_misses, 1) else "suspected_missing"
                    previous["consecutive_misses"] = misses
                    previous["lifecycle_status"] = lifecycle
                    previous["last_checked_at"] = started
                    if lifecycle == "expired":
                        report.expired += 1
                    else:
                        report.suspected_missing += 1

            batch_path = self.batch_dir / f"{batch_id}.jsonl"
            self._write_jsonl(batch_path, batch_records)
            self._write_jsonl(state_path, state.values())
            gold_path=self.gold_dir/f"{source}_{data_type}.jsonl";self._write_jsonl(gold_path,state.values());report.gold_path=str(gold_path.relative_to(self.root)).replace('\\','/')
            report.status = "success" if report.quality().get("passed") else "quality_failed"
        except Exception as exc:
            report.status = "failed"
            report.error = str(exc)
            failures.append({"stage":"batch","reason":"unhandled_exception","error_type":type(exc).__name__,"message":str(exc)})
            raise
        finally:
            report.finished_at = utc_now()
            for failure in failures:
                failure.setdefault("batch_id", batch_id)
                failure.setdefault("source", source)
                failure.setdefault("data_type", data_type)
                failure.setdefault("recorded_at", report.finished_at)
            failure_path = self.failure_dir / f"{batch_id}.jsonl"
            self._write_jsonl(failure_path, failures)
            report.failure_path = str(failure_path.relative_to(self.root)).replace('\\','/')
            report_path = self.report_dir / f"{batch_id}.json"
            report_path.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return report

    def rollback(self,batch_id:str)->bool:
        backups=list(self.rollback_dir.glob(f"{batch_id}__*.bak"))
        report_path=self.report_dir/f"{batch_id}.json"
        if not backups:return False
        for backup in backups:
            target=self.state_dir/backup.name.split('__',1)[1].removesuffix('.bak')
            target.write_bytes(backup.read_bytes())
            gold=self.gold_dir/target.name
            gold.write_bytes(backup.read_bytes())
        if report_path.exists():
            report=json.loads(report_path.read_text(encoding='utf-8'));report['status']='rolled_back';report['rolled_back_at']=utc_now();report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return True


def load_records(path: str | Path) -> list[dict]:
    """读取 CSV、JSON 或 JSONL，用于人工导入和离线复测。"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return [row.get("payload", row) if isinstance(row, dict) else row for row in rows]
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            return value
        for key in ("items", "records", "data", "jobs"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    raise ValueError(f"不支持的文件格式: {path.suffix}")
