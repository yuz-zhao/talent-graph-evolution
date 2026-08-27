"""官方技术博客 v2：RSS/Atom 原始字段、合规正文快照和证据化技能关系。"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from utils.skill_mapping import extract_skill_matches  # noqa: E402

OUTPUT = BASE / "data/bronze/blogs_trend.jsonl"
RAW_ROOT = BASE / "data/bronze/blogs/api"
URL_INVENTORY = BASE / "data/quarantine/blog_legacy_url_inventory.jsonl"
USER_AGENT = "TalentGraph-Evolution-Research/2.0"

SOURCES = [
    # 中国企业官方技术来源
    {"name": "Alibaba Cloud", "region": "domestic", "kind": "official_company", "feed": "https://www.alibabacloud.com/blog", "mode": "html_index", "link_pattern": "/blog/"},
    {"name": "PingCAP", "region": "domestic", "kind": "official_company", "feed": "https://www.pingcap.com/blog/", "mode": "html_index", "link_pattern": "/blog/"},
    {"name": "Zilliz China", "region": "domestic", "kind": "official_company", "feed": "https://zilliz.com.cn/blog", "mode": "html_index", "link_pattern": "/blog/"},
    {"name": "Qwen Team", "region": "domestic", "kind": "official_research", "feed": "https://qwenlm.github.io/blog/", "mode": "html_index", "link_pattern": "/blog/"},
    {"name": "ByteDance Seed", "region": "domestic", "kind": "official_research", "feed": "https://seed.bytedance.com/en/blog", "mode": "html_index", "link_pattern": "/en/blog/"},
    {"name": "Huawei", "region": "domestic", "kind": "official_company", "feed": "https://www.huawei.com/en/rss-feeds/huawei-updates/rss"},
    # 国际企业与研究机构官方来源
    {"name": "Hugging Face", "region": "international", "kind": "official_company", "feed": "https://huggingface.co/blog/feed.xml"},
    {"name": "Google Research", "region": "international", "kind": "official_research", "feed": "https://blog.research.google/feeds/posts/default?alt=rss"},
    {"name": "AWS Machine Learning", "region": "international", "kind": "official_company", "feed": "https://aws.amazon.com/blogs/machine-learning/feed/"},
    {"name": "Microsoft Research", "region": "international", "kind": "official_research", "feed": "https://www.microsoft.com/en-us/research/feed/"},
    {"name": "NVIDIA Developer", "region": "international", "kind": "official_company", "feed": "https://developer.nvidia.com/blog/feed/"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_html(value: str) -> str:
    text = re.sub(r"<(script|style).*?</\1>", " ", value or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if local_name(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def parse_feed(xml: bytes, source: dict, observed_at: str) -> list[dict]:
    root = ET.fromstring(xml)
    items = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    rows = []
    for node in items:
        title = child_text(node, {"title"})
        summary_raw = child_text(node, {"description", "summary", "content", "encoded"})
        link = child_text(node, {"link"})
        if not link:
            for child in list(node):
                if local_name(child.tag) == "link" and child.get("href"):
                    link = child.get("href", "")
                    if child.get("rel") in {None, "alternate"}:
                        break
        guid = child_text(node, {"guid", "id"})
        published_raw = child_text(node, {"pubdate", "published", "date"})
        updated_raw = child_text(node, {"updated", "modified"})
        authors = []
        for child in list(node):
            if local_name(child.tag) in {"author", "creator"}:
                value = clean_html("".join(child.itertext()))
                if value:
                    authors.append(value)
        categories = [clean_html("".join(child.itertext())) for child in list(node) if local_name(child.tag) == "category"]
        url = urljoin(source["feed"], link or guid)
        if not title or not url.startswith("http"):
            continue
        rss_raw = {
            "title": title, "link": link, "guid_or_id": guid,
            "published_raw": published_raw, "updated_raw": updated_raw,
            "authors_raw": authors, "categories_raw": categories,
            "summary_html": summary_raw,
        }
        rows.append({
            "article_id": hashlib.sha256(url.encode()).hexdigest()[:24], "title": clean_html(title),
            "article_url": url, "source_name": source["name"], "source_region": source["region"],
            "source_kind": source["kind"], "evidence_confidence": "high",
            "published_at": parse_date(published_raw), "updated_at": parse_date(updated_raw),
            "authors": list(dict.fromkeys(authors)), "rss_categories": list(dict.fromkeys(categories)),
            "rss_summary": clean_html(summary_raw), "summary_origin": "rss" if clean_html(summary_raw) else "",
            "summary_model": "", "summary_evidence": "", "rss_raw": rss_raw,
            "body_text": "", "body_status": "not_attempted", "body_fetched_at": "",
            "article_type": "", "inferred_skills": [], "relationship_skills": [], "skill_evidence": [],
            "hot_score": 0.0, "hot_score_method": "source_internal_recency_percentile",
            "observed_at": observed_at,
        })
    return rows


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta = {}; self.parts = []; self.capture = False; self.skip = 0
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag in {"script", "style", "nav", "footer"}: self.skip += 1
        if tag in {"article", "main", "p", "h1", "h2", "h3", "li"}: self.capture = True
        key = data.get("property") or data.get("name")
        if tag == "meta" and key and data.get("content"): self.meta[key.casefold()] = data["content"]
    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer"} and self.skip: self.skip -= 1
        if tag in {"article", "main", "p", "h1", "h2", "h3", "li"}: self.capture = False
    def handle_data(self, data):
        if self.capture and not self.skip and data.strip(): self.parts.append(data.strip())


class IndexParser(HTMLParser):
    def __init__(self, base_url: str, pattern: str):
        super().__init__(); self.base_url = base_url; self.pattern = pattern; self.current = ""; self.text = []; self.links = []
    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and self.pattern in href:
            self.current = urljoin(self.base_url, href.split("#")[0]); self.text = []
    def handle_data(self, data):
        if self.current and data.strip(): self.text.append(data.strip())
    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            title = clean_html(" ".join(self.text))
            if title and self.current.rstrip("/") != self.base_url.rstrip("/"):
                self.links.append((self.current, title))
            self.current = ""; self.text = []


def parse_html_index(content: bytes, source: dict, observed_at: str) -> list[dict]:
    parser = IndexParser(source["feed"], source["link_pattern"])
    parser.feed(content.decode("utf-8", errors="replace"))
    rows, seen = [], set()
    for url, title in parser.links:
        if url in seen: continue
        path = urlparse(url).path.rstrip("/")
        if path.endswith("/blog") or "/page/" in path:
            continue
        seen.add(url)
        rows.append({
            "article_id": hashlib.sha256(url.encode()).hexdigest()[:24], "title": title[:500],
            "article_url": url, "source_name": source["name"], "source_region": source["region"],
            "source_kind": source["kind"], "evidence_confidence": "high", "published_at": "", "updated_at": "",
            "authors": [], "rss_categories": [], "rss_summary": "", "summary_origin": "",
            "summary_model": "", "summary_evidence": "",
            "rss_raw": {"source_mode": "official_html_index", "index_url": source["feed"], "link_text": title},
            "body_text": "", "body_status": "not_attempted", "body_fetched_at": "", "article_type": "",
            "inferred_skills": [], "relationship_skills": [], "skill_evidence": [], "hot_score": 0.0,
            "hot_score_method": "source_internal_recency_percentile", "observed_at": observed_at,
        })
    return rows


def robots_allowed(session: requests.Session, url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = session.get(robots_url, timeout=20)
        if response.status_code >= 400:
            return True
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url); parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, url)
    except requests.RequestException:
        return False


def fetch_body(session: requests.Session, row: dict, raw_dir: Path) -> None:
    url = row["article_url"]
    if not robots_allowed(session, url):
        row["body_status"] = "robots_disallowed_or_unavailable"
        return
    try:
        response = session.get(url, timeout=35)
        if response.status_code != 200 or "html" not in response.headers.get("Content-Type", ""):
            row["body_status"] = f"http_{response.status_code}"
            return
        parser = ArticleParser(); parser.feed(response.text)
        body = re.sub(r"\s+", " ", "\n".join(parser.parts)).strip()
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{row['article_id']}.html").write_bytes(response.content)
        if len(body) >= 200:
            row["body_text"] = body[:20000]; row["body_status"] = "fetched"
        else:
            row["body_status"] = "insufficient_body"
        row["body_fetched_at"] = now_iso()
        if not row["published_at"]:
            row["published_at"] = parse_date(parser.meta.get("article:published_time") or parser.meta.get("date") or "")
        if not row["published_at"]:
            visible_date = re.search(r"\b(20\d{2})[年./-](0?[1-9]|1[0-2])[月./-](0?[1-9]|[12]\d|3[01])日?\b", body)
            if visible_date:
                row["published_at"] = parse_date(f"{visible_date.group(1)}-{int(visible_date.group(2)):02d}-{int(visible_date.group(3)):02d}")
        if not row["rss_summary"]:
            row["rss_summary"] = clean_html(parser.meta.get("description") or parser.meta.get("og:description") or "")
            if row["rss_summary"]:
                row["summary_origin"] = "publisher_meta"
    except requests.RequestException:
        row["body_status"] = "request_failed"


def classify_article(title: str, text: str) -> str:
    value = f"{title} {text}".casefold()
    rules = [
        ("产品发布", r"release|launch|introduc|announc|发布|上线|版本"),
        ("实践案例", r"case study|customer|production|实践|案例|落地"),
        ("技术教程", r"tutorial|how to|guide|step.by.step|教程|指南|入门"),
        ("研究解读", r"research|paper|study|benchmark|研究|论文|评测"),
    ]
    for label, pattern in rules:
        if re.search(pattern, value): return label
    return "行业观察"


def enrich_skills(row: dict) -> None:
    evidence_text = row["body_text"] or row["rss_summary"]
    field = "body" if row["body_text"] else "rss_summary"
    skills, evidence, seen = [], [], set()
    for match in extract_skill_matches(evidence_text):
        key = match.standard.casefold()
        if key in seen: continue
        seen.add(key); skills.append(match.standard)
        start, end = max(0, match.start - 100), min(len(evidence_text), match.start + len(match.raw) + 180)
        evidence.append({
            "skill": match.standard, "raw": match.raw, "source_field": field,
            "evidence_text": evidence_text[start:end].strip()[:400], "method": "skill_ontology_alias_rule_v3",
        })
    row["inferred_skills"] = skills
    row["relationship_skills"] = skills
    row["skill_evidence"] = evidence
    row["article_type"] = classify_article(row["title"], evidence_text)


def normalize_hotness(rows: list[dict]) -> None:
    groups = defaultdict(list)
    for row in rows: groups[row["source_name"]].append(row)
    for items in groups.values():
        ordered = sorted(items, key=lambda row: row.get("published_at") or "")
        denominator = max(1, len(ordered) - 1)
        for index, row in enumerate(ordered): row["hot_score"] = round(index / denominator, 6)


def build_legacy_inventory() -> None:
    legacy = BASE / "data/quarantine/blog_trend_contaminated_20260802.jsonl"
    text = legacy.read_text(encoding="utf-8", errors="replace") if legacy.exists() else ""
    urls = list(dict.fromkeys(re.findall(r'https://[^"\\\s]+', text)))
    URL_INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    with URL_INVENTORY.open("w", encoding="utf-8") as handle:
        for url in urls:
            handle.write(json.dumps({"article_url": url, "host": urlparse(url).netloc, "status": "legacy_url_only"}, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-per-source", type=int, default=8)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    observed_at = now_iso(); batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = RAW_ROOT / batch_id
    session = requests.Session(); session.headers["User-Agent"] = USER_AGENT
    build_legacy_inventory(); rows = []
    for source in SOURCES:
        try:
            response = session.get(source["feed"], timeout=40)
            if response.status_code != 200:
                print(f"{source['name']}: feed HTTP {response.status_code}"); continue
            source_dir = raw_dir / re.sub(r"[^A-Za-z0-9]+", "_", source["name"])
            source_dir.mkdir(parents=True, exist_ok=True)
            raw_name = "index.html" if source.get("mode") == "html_index" else "feed.xml"
            (source_dir / raw_name).write_bytes(response.content)
            items = parse_html_index(response.content, source, observed_at) if source.get("mode") == "html_index" else parse_feed(response.content, source, observed_at)
            for row in items[:max(0, args.body_per_source)]:
                fetch_body(session, row, source_dir / "articles"); time.sleep(max(0, args.delay))
            for row in items:
                enrich_skills(row)
            rows.extend(items)
            print(f"{source['name']}: {len(items)}，正文 {sum(r['body_status']=='fetched' for r in items)}")
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"{source['name']}: {type(exc).__name__}")
        time.sleep(max(0, args.delay))
    unique = {row["article_url"]: row for row in rows if row["rss_summary"] or row["body_text"]}
    rows = list(unique.values()); normalize_hotness(rows)
    rows.sort(key=lambda row: (row.get("published_at") or "", row["article_url"]), reverse=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for row in rows: handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest = {"batch_id": batch_id, "articles": len(rows), "sources": sorted({r['source_name'] for r in rows}), "observed_at": observed_at}
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
