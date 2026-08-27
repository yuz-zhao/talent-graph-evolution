"""Evidence-constrained JD-level new-job discovery without synthetic scores.

Uses deterministic spherical k-means implemented with NumPy, evaluates multiple k
values, reports clustering quality, bootstraps stability, and integrates R03/R04.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
import sys

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
GOLD = BASE / "data/gold/records"
TEMPORAL = BASE / "data/gold/temporal/job_temporal_index.jsonl"
EVIDENCE = BASE / "data/gold/evidence/skill_validation_results.json"
ONTOLOGY = BASE / "data/gold/reference/skill_ontology.json"
RULES = BASE / "config/new_job_discovery_rules.json"
OUT = BASE / "data/gold/new_jobs/new_job_candidates.json"
REPORT = BASE / "data/reports/new_job_discovery_quality_report.json"


def repair(value) -> str:
    text = str(value or "").strip()
    if not text: return ""
    suspicious = sum(ch in text for ch in "¿Ê¤ÐÎÖÄÃÂºó·¢¹¤³Ì")
    if suspicious >= 2:
        try:
            fixed = text.encode("latin1").decode("gb18030")
            if fixed.count("�") == 0: return fixed
        except (UnicodeEncodeError, UnicodeDecodeError): pass
    return text


def arr(value):
    if isinstance(value, list): return value
    if not value: return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list): return parsed
    except (json.JSONDecodeError, TypeError): pass
    return [x.strip() for x in re.split(r"[;,，、]", str(value)) if x.strip()]


def load_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def stable_id(*parts):
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:20]


def norm_rows(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True); norms[norms == 0] = 1
    return matrix / norms


def spherical_kmeans(x, k, seed=42, iterations=60):
    rng = np.random.default_rng(seed); n = len(x)
    first = int(rng.integers(n)); centers = [x[first]]
    for _ in range(1, k):
        distance = 1 - np.max(x @ np.vstack(centers).T, axis=1)
        centers.append(x[int(np.argmax(distance))])
    centers = norm_rows(np.vstack(centers)); labels = np.zeros(n, dtype=int)
    for _ in range(iterations):
        new_labels = np.argmax(x @ centers.T, axis=1)
        if np.array_equal(new_labels, labels) and _ > 0: break
        labels = new_labels
        rebuilt = []
        for cluster in range(k):
            members = x[labels == cluster]
            rebuilt.append(members.mean(axis=0) if len(members) else x[int(rng.integers(n))])
        centers = norm_rows(np.vstack(rebuilt))
    return labels, centers


def silhouette_cosine(x, labels):
    unique = sorted(set(labels.tolist()))
    if len(unique) < 2 or len(x) < 3: return 0.0
    similarity = x @ x.T; distance = 1 - similarity; values = []
    for i, label in enumerate(labels):
        same = np.where(labels == label)[0]; same = same[same != i]
        a = float(distance[i, same].mean()) if len(same) else 0.0
        b = min(float(distance[i, labels == other].mean()) for other in unique if other != label and np.any(labels == other))
        values.append((b - a) / max(a, b, 1e-9))
    return float(np.mean(values))


def davies_bouldin(x, labels, centers):
    k = len(centers); scatter = []
    for i in range(k):
        members = x[labels == i]
        scatter.append(float(np.mean(1 - members @ centers[i])) if len(members) else 0)
    scores = []
    for i in range(k):
        scores.append(max((scatter[i] + scatter[j]) / max(1 - float(centers[i] @ centers[j]), 1e-9) for j in range(k) if j != i))
    return float(np.mean(scores))


def calinski_harabasz(x, labels, centers):
    n, k = len(x), len(centers)
    if k <= 1 or n <= k: return 0.0
    overall = norm_rows(x.mean(axis=0, keepdims=True))[0]
    between = sum(np.sum(labels == i) * (1 - float(centers[i] @ overall)) for i in range(k))
    within = sum(float(np.sum(1 - x[labels == i] @ centers[i])) for i in range(k))
    return float((between / (k - 1)) / max(within / (n - k), 1e-9))


def bootstrap_stability(x, labels, k, rounds):
    n = len(x); scores = defaultdict(list)
    for r in range(rounds):
        rng = np.random.default_rng(1000 + r); sample = np.sort(rng.choice(n, max(k * 2, int(n * .8)), replace=False))
        boot_labels, _ = spherical_kmeans(x[sample], k, seed=100 + r)
        for original in range(k):
            expected = set(sample[labels[sample] == original].tolist())
            if not expected: continue
            best = 0.0
            for candidate in range(k):
                actual = set(sample[boot_labels == candidate].tolist())
                best = max(best, len(expected & actual) / max(len(expected | actual), 1))
            scores[original].append(best)
    return {i: round(float(np.mean(scores[i])) if scores[i] else 0.0, 4) for i in range(k)}


def js_divergence(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    a = (a + 1e-9) / (a.sum() + 1e-9 * len(a)); b = (b + 1e-9) / (b.sum() + 1e-9 * len(b)); m = (a + b) / 2
    value = .5 * np.sum(a * np.log2(a / m)) + .5 * np.sum(b * np.log2(b / m))
    return float(min(max(value, 0), 1))


def diversity_score(values):
    counts = Counter(x for x in values if x); total = sum(counts.values())
    if total <= 1 or len(counts) <= 1: return 0.0
    entropy = -sum((n/total) * math.log(n/total) for n in counts.values())
    return min(1.0, entropy / math.log(min(len(counts), 5)))


def direction_label(skills):
    aliases = {"LLM":"大模型", "AI智能体":"AI智能体", "Agent":"AI智能体", "RAG":"RAG", "AIGC":"生成式AI", "Kubernetes":"云原生", "5G移动通信":"5G", "物联网":"物联网", "工业互联网":"工业互联网"}
    for priority in ("AI智能体","Agent","RAG","AIGC","LLM","大语言模型","多模态学习","生成式AI","5G移动通信","工业互联网","物联网","边缘计算","数字孪生"):
        if priority in skills: return aliases.get(priority, "大模型" if priority in {"大语言模型","多模态学习"} else priority)
    for skill in skills:
        if skill in aliases: return aliases[skill]
    return skills[0] if skills else "新能力"


def candidate_name(parent, distinctive):
    parent = repair(parent) or "信息技术工程师"; label = direction_label(distinctive)
    if label.casefold() in parent.casefold(): return f"{parent}新方向"
    core = re.sub(r"(?:高级|资深|初级|中级)", "", parent)
    return f"{label}{core}" if len(core) <= 16 else f"{label}方向{core}"


def main() -> int:
    rules = json.loads(RULES.read_text(encoding="utf-8")); ontology = json.loads(ONTOLOGY.read_text(encoding="utf-8"))
    aliases = {}
    for name, info in ontology.items():
        for alias in [name, *arr(info.get("aliases"))]: aliases[repair(alias).casefold()] = name
    temporal = {x["record_id"]: x for x in load_jsonl(TEMPORAL)}
    r03_data = json.loads(EVIDENCE.read_text(encoding="utf-8")); r03 = {x["skill_name"]: x for x in r03_data["skills"]}
    jobs = []; input_gold_jd_records = 0
    for path in GOLD.glob("*_job.jsonl"):
        for env in load_jsonl(path):
            payload = env.get("payload") or {}; synthetic = str(payload.get("is_synthetic", "")).lower() in {"1","true","yes"}
            if synthetic or env.get("lifecycle_status") == "expired": continue
            input_gold_jd_records += 1
            skills = []
            for raw in [*arr(payload.get("required_skills")), *arr(payload.get("skill_standard"))]:
                value = raw.get("skill") if isinstance(raw, dict) else raw; canonical = aliases.get(repair(value).casefold())
                if canonical and canonical not in skills: skills.append(canonical)
            if len(skills) < 2: continue
            rid = env.get("record_id"); t = temporal.get(rid, {})
            jobs.append({
                "record_id": rid, "canonical_job_id": payload.get("canonical_job_id") or rid,
                "raw_title": repair(payload.get("job_title")), "parent": repair(payload.get("standard_job_name")) or "未标准化岗位",
                "company": repair(payload.get("company")), "source": env.get("source_platform") or repair(payload.get("source_name")),
                "region": repair(payload.get("region_standard") or payload.get("location")), "skills": skills,
                "mapping_confidence": float(payload.get("job_mapping_confidence") or 0),
                "direction": repair(payload.get("job_direction")), "scene": repair(payload.get("business_scene")),
                "quarter": t.get("publication_quarter", "") if t.get("temporal_eligible") else "",
                "source_url": env.get("source_url") or payload.get("source_url") or "", "batch_id": env.get("crawl_batch_id") or "",
            })
    # Deduplicate by canonical job ID and preserve the most skill-complete record.
    skill_eligible_jd_records = len(jobs); unique = {}
    for job in jobs:
        key = job["canonical_job_id"]
        if key not in unique or len(job["skills"]) > len(unique[key]["skills"]): unique[key] = job
    jobs = list(unique.values()); all_skills = sorted({s for job in jobs for s in job["skills"]}); skill_index = {s:i for i,s in enumerate(all_skills)}
    document_frequency = Counter(s for job in jobs for s in set(job["skills"])); n_jobs = len(jobs)
    idf = np.array([math.log((n_jobs + 1) / (document_frequency[s] + 1)) + 1 for s in all_skills])
    matrix = np.zeros((n_jobs, len(all_skills)), dtype=np.float32)
    for row, job in enumerate(jobs):
        for skill in job["skills"]: matrix[row, skill_index[skill]] = idf[skill_index[skill]]
    matrix = norm_rows(matrix)
    by_parent = defaultdict(list)
    for i, job in enumerate(jobs): by_parent[job["parent"]].append(i)
    quarter_totals = Counter(job["quarter"] for job in jobs if job["quarter"]); quarters = sorted(quarter_totals)

    candidates = []; evaluations = []
    for parent, indices in sorted(by_parent.items(), key=lambda x: -len(x[1])):
        if len(indices) < int(rules["min_parent_samples"]): continue
        x = matrix[indices]; max_k = min(int(rules["max_clusters_per_parent"]), len(indices) // int(rules["min_cluster_size"]))
        if max_k < 2: continue
        trials = []
        for k in range(2, max_k + 1):
            labels, centers = spherical_kmeans(x, k, seed=42 + k); sizes = [int(np.sum(labels == c)) for c in range(k)]
            sil = silhouette_cosine(x, labels); db = davies_bouldin(x, labels, centers); ch = calinski_harabasz(x, labels, centers)
            valid_size = min(sizes) >= int(rules["min_cluster_size"])
            selection = sil - .03 * (k - 2) - (.2 if not valid_size else 0)
            trials.append({"k":k,"labels":labels,"centers":centers,"sizes":sizes,"silhouette":sil,"davies_bouldin":db,"calinski_harabasz":ch,"selection_score":selection,"valid_size":valid_size})
        best = max(trials, key=lambda t:t["selection_score"])
        evaluations.append({"parent_job":parent,"sample_count":len(indices),"selected_k":best["k"],"silhouette":round(best["silhouette"],4),"davies_bouldin":round(best["davies_bouldin"],4),"calinski_harabasz":round(best["calinski_harabasz"],4),"trials":[{k:(round(v,4) if isinstance(v,float) else v) for k,v in t.items() if k not in {"labels","centers"}} for t in trials]})
        if best["silhouette"] < float(rules["minimum_silhouette"]): continue
        stability = bootstrap_stability(x, best["labels"], best["k"], int(rules["bootstrap_rounds"]))
        for cluster in range(best["k"]):
            local = np.where(best["labels"] == cluster)[0]; outside = np.where(best["labels"] != cluster)[0]
            if len(local) < int(rules["min_cluster_size"]): continue
            member_indices = [indices[i] for i in local]; members = [jobs[i] for i in member_indices]
            cluster_presence = np.mean(matrix[member_indices] > 0, axis=0); outside_presence = np.mean(matrix[[indices[i] for i in outside]] > 0, axis=0) if len(outside) else np.zeros(len(all_skills))
            distinctive_idx = np.argsort(cluster_presence - outside_presence)[::-1]
            distinctive = [all_skills[i] for i in distinctive_idx if cluster_presence[i] >= .25 and cluster_presence[i] - outside_presence[i] >= .15][:8]
            if not distinctive: continue
            generic_for_naming = {"系统设计","软件工程","技术研究","标准研究","需求分析","解决方案设计","通信网络","后端开发","前端开发","数据分析","人工智能","Python","Java","C/C++","Linux"}
            meaningful = [s for s in distinctive if s not in generic_for_naming and s.casefold() not in parent.casefold()]
            emerging_markers = {"LLM","大语言模型","AI智能体","Agent","RAG","AIGC","多模态学习","生成式AI","5G移动通信","工业互联网","物联网","边缘计算","数字孪生"}
            emerging_signal = any(s in emerging_markers for s in meaningful)
            skill_novelty = js_divergence(cluster_presence, outside_presence)
            title_signal = sum(any(direction_label(distinctive[:3]).casefold() in text.casefold() for text in (m["raw_title"],m["direction"],m["scene"])) for m in members) / len(members)
            novelty = min(1.0, .75 * skill_novelty + .25 * title_signal)
            q_counts = Counter(m["quarter"] for m in members if m["quarter"]); growth_score = .0; growth_rate = None; windows = []
            usable = [q for q in quarters if quarter_totals[q] >= 10]
            if len(usable) >= 2:
                q1, q2 = usable[-2], usable[-1]; r1 = (q_counts[q1] + .5)/(quarter_totals[q1] + 1); r2 = (q_counts[q2] + .5)/(quarter_totals[q2] + 1)
                growth_rate = r2/r1 - 1; growth_score = .5 + .5 * math.tanh(math.log(max(r2/r1, 1e-9))); windows = [{"quarter":q1,"candidate_jobs":q_counts[q1],"eligible_jobs":quarter_totals[q1]},{"quarter":q2,"candidate_jobs":q_counts[q2],"eligible_jobs":quarter_totals[q2]}]
            evidence_items = [r03[s] for s in distinctive if s in r03]
            evidence_score = float(np.mean([x["confidence"] for x in evidence_items])) if evidence_items else 0.0
            external_groups = len({g for item in evidence_items for g,n in item["group_counts"].items() if g != "job" and n > 0})
            sources = [m["source"] for m in members]; companies = [m["company"] for m in members]; regions = [m["region"] for m in members]
            source_div = diversity_score(sources); company_div = diversity_score(companies); region_div = diversity_score(regions)
            company_counts = Counter(x for x in companies if x); max_company_share = max(company_counts.values(), default=0)/len(members)
            stab = stability.get(cluster, 0.0)
            components = {"novelty":novelty,"growth":growth_score,"evidence":evidence_score,"stability":stab,"source_diversity":source_div,"company_diversity":company_div,"regional_spread":region_div}
            score = min(1.0, max(0.0, sum(float(rules["score_weights"][key])*value for key,value in components.items())))
            th = rules["candidate_thresholds"]
            formal = bool(meaningful) and emerging_signal and len(members)>=th["formal_min_jds"] and len(set(companies))>=th["formal_min_companies"] and len(set(sources))>=th["formal_min_sources"] and stab>=th["formal_min_stability"] and novelty>=th["formal_min_novelty"] and evidence_score>=th["formal_min_evidence"] and growth_score>=th["formal_min_growth"] and max_company_share<=th["formal_max_company_share"]
            if formal: candidate_type = "formal_candidate"
            elif meaningful and emerging_signal and len(members)>=th["early_min_jds"] and novelty>=th["early_min_novelty"] and (growth_score>=.6 or external_groups>=2): candidate_type = "early_watch"
            elif meaningful and novelty>=.25 and stab>=.45: candidate_type = "capability_direction"
            else: candidate_type = "alias_or_noise"
            cid = "NJC_" + stable_id(parent, *sorted(m["record_id"] for m in members))
            candidates.append({
                "candidate_id":cid,"name":candidate_name(parent,meaningful or distinctive),"candidate_type":candidate_type,"parent_job":parent,
                "unique_jd_count":len(members),"job_count":len(members),"cluster_size":len(members),"company_count":len(set(companies)),"source_count":len(set(sources)),"region_count":len(set(regions)),
                "top_skills":distinctive,"member_record_ids":[m["record_id"] for m in members],"representative_jd_urls":[m["source_url"] for m in members if m["source_url"]][:10],
                "novelty":round(novelty,4),"growth":round(growth_score,4),"growth_rate":None if growth_rate is None else round(growth_rate,4),"evidence":round(evidence_score,4),"stability":round(stab,4),
                "source_diversity":round(source_div,4),"company_diversity":round(company_div,4),"regional_spread":round(region_div,4),"max_company_share":round(max_company_share,4),"score":round(score,4),
                "confidence":"high" if formal and score>=.7 else ("medium" if candidate_type in {"formal_candidate","early_watch","capability_direction"} else "low"),
                "independent_external_groups":external_groups,"observation_windows":windows,"representative_evidence":[ev for item in evidence_items for ev in item.get("representative_evidence",[])][:10],
                "cluster_metrics":{"parent_silhouette":round(best["silhouette"],4),"parent_davies_bouldin":round(best["davies_bouldin"],4),"parent_calinski_harabasz":round(best["calinski_harabasz"],4)},
                "algorithm_version":rules["version"],"data_batch_ids":sorted({m["batch_id"] for m in members if m["batch_id"]}),"review_status":"pending_review",
            })
    rank = {"formal_candidate":0,"early_watch":1,"capability_direction":2,"alias_or_noise":3}
    candidates.sort(key=lambda x:(rank[x["candidate_type"]],-x["score"],-x["unique_jd_count"]))
    formal_output = [x for x in candidates if x["candidate_type"] != "alias_or_noise"]
    payload = {"schema_version":"3.0.0","algorithm":rules["version"],"input_gold_jd_records":input_gold_jd_records,"skill_eligible_jd_records":skill_eligible_jd_records,"input_unique_jds":len(jobs),"candidate_counts":dict(Counter(x["candidate_type"] for x in candidates)),"candidates":formal_output,"rejected_alias_or_noise":len(candidates)-len(formal_output),"clustering_evaluations":evaluations}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    all_counts_valid = all(x["unique_jd_count"] == len(set(x["member_record_ids"])) <= len(jobs) for x in candidates)
    report = {"algorithm":rules["version"],"input_gold_jd_records":input_gold_jd_records,"skill_eligible_jd_records":skill_eligible_jd_records,"input_unique_jds":len(jobs),"parents_evaluated":len(evaluations),"candidates_before_noise_filter":len(candidates),"published_candidates":len(formal_output),"candidate_counts":payload["candidate_counts"],"all_scores_in_unit_interval":all(0<=x["score"]<=1 for x in candidates),"all_jd_counts_are_unique":all_counts_valid,"all_candidates_have_members":all(bool(x["member_record_ids"]) for x in candidates),"all_candidates_have_batch_ids":all(bool(x["data_batch_ids"]) for x in candidates),"growth_uses_r04_windows":True,"evidence_uses_r03_results":True,"passed":bool(evaluations) and all_counts_valid}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
