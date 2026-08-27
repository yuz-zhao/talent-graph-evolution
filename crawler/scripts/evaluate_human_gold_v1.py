"""Evaluate reproducible TalentGraph baselines against frozen human gold v1.1."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HUMAN = BASE / "data" / "gold" / "human" / "v1.1"
REFERENCE = BASE / "data" / "gold" / "reference"
REPORT_JSON = BASE / "data" / "reports" / "human_gold_v1_1_baseline_evaluation.json"
REPORT_MD = BASE / "data" / "reports" / "human_gold_v1_1_baseline_evaluation.md"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def skill_set(values) -> set[str]:
    return {norm(v) for v in values or [] if norm(v)}


def set_counts(gold_rows, pred_by_id, id_key, gold_key, pred_key):
    tp = fp = fn = exact = 0
    for row in gold_rows:
        gold = skill_set(row.get(gold_key))
        pred = skill_set(pred_by_id.get(row[id_key], {}).get(pred_key))
        tp += len(gold & pred); fp += len(pred - gold); fn += len(gold - pred); exact += gold == pred
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "exact_match": exact / len(gold_rows), "tp": tp, "fp": fp, "fn": fn}


def overlap_score(required, bonus, resume_skills) -> float:
    required, bonus, skills = map(skill_set, (required, bonus, resume_skills))
    available = []
    if required: available.append((len(required & skills) / len(required), 0.8))
    if bonus: available.append((len(bonus & skills) / len(bonus), 0.2))
    return sum(v * w for v, w in available) / sum(w for _, w in available) if available else 0.0


def score_to_class(score: float) -> int:
    if score <= 0: return 0
    if score < 0.5: return 1
    if score < 0.999999: return 2
    return 3


FAMILIES = {
    "ai": ("机器学习", "人工智能", "算法", "大模型", "深度学习", "自然语言", "计算机视觉", "machine learning", "data scientist", " ai ", "nlp"),
    "backend": ("后端", "java", "golang", "服务端", "backend"),
    "frontend": ("前端", "web前端", "frontend"),
    "data": ("数据工程", "数据分析", "数据仓库", "大数据", "data engineer", "data analyst"),
    "devops": ("devops", "云原生", "运维", "sre", "云计算"),
    "embedded": ("嵌入式", "物联网", "iot"),
    "product": ("产品经理", "marketing manager", "市场经理", "销售", "解决方案经理"),
}


def families(value: str) -> set[str]:
    text = f" {norm(value)} "
    return {name for name, words in FAMILIES.items() if any(word in text for word in words)}


def direction_guard(score_class: int, target_job: str, job_title: str) -> int:
    left, right = families(target_job), families(job_title)
    return min(score_class, 1) if left and right and left.isdisjoint(right) else score_class


def classification_metrics(gold, pred):
    labels = [0, 1, 2, 3]
    confusion = [[sum(1 for y, p in zip(gold, pred) if y == a and p == b) for b in labels] for a in labels]
    per_class = {}
    f1s = []
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[r][label] for r in labels if r != label)
        fn = sum(confusion[label][c] for c in labels if c != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1); per_class[str(label)] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(confusion[label])}
    n = len(gold); accuracy = sum(y == p for y, p in zip(gold, pred)) / n
    gold_counts, pred_counts = Counter(gold), Counter(pred)
    expected = sum(gold_counts[x] * pred_counts[x] for x in labels) / (n * n)
    kappa = (accuracy - expected) / (1 - expected) if expected < 1 else 0.0
    return {"accuracy": accuracy, "macro_f1": sum(f1s) / len(f1s), "cohen_kappa": kappa, "mae": sum(abs(y-p) for y,p in zip(gold,pred))/n, "confusion_matrix": confusion, "per_class": per_class, "prediction_distribution": dict(sorted(Counter(pred).items()))}


def ranking_metrics(rows, score_key):
    grouped = defaultdict(list)
    for row in rows: grouped[row["resume_id"]].append(row)
    result = {}
    for k in (5, 10):
        ndcgs, recalls, reciprocal = [], [], []
        for candidates in grouped.values():
            ranked = sorted(candidates, key=lambda x: (x[score_key], x["pair_id"]), reverse=True)
            ideal = sorted(candidates, key=lambda x: x["relevance"], reverse=True)
            dcg = sum((2**x["relevance"]-1)/math.log2(i+2) for i,x in enumerate(ranked[:k]))
            idcg = sum((2**x["relevance"]-1)/math.log2(i+2) for i,x in enumerate(ideal[:k]))
            relevant = sum(x["relevance"] >= 2 for x in candidates)
            ndcgs.append(dcg/idcg if idcg else 0.0)
            recalls.append(sum(x["relevance"] >= 2 for x in ranked[:k])/relevant if relevant else 0.0)
            first = next((i for i,x in enumerate(ranked,1) if x["relevance"] >= 2), None)
            reciprocal.append(1/first if first else 0.0)
        result[f"ndcg@{k}"] = sum(ndcgs)/len(ndcgs)
        result[f"recall@{k}"] = sum(recalls)/len(recalls)
        if k == 10: result["mrr"] = sum(reciprocal)/len(reciprocal)
    result["query_count"] = len(grouped)
    return result


def rounded(value):
    if isinstance(value, float): return round(value, 4)
    if isinstance(value, dict): return {str(k): rounded(v) for k, v in value.items()}
    if isinstance(value, list): return [rounded(v) for v in value]
    return value


def main():
    gold_jd = load_jsonl(HUMAN / "gold_jd_v1.1.jsonl")
    gold_resume = load_jsonl(HUMAN / "gold_resume_v1.1.jsonl")
    gold_match = load_jsonl(HUMAN / "gold_match_v1.1.jsonl")
    ai_jd = json.loads((REFERENCE / "gold_jd_set_reviewed.json").read_text(encoding="utf-8"))
    ai_resume_payload = json.loads((REFERENCE / "gold_resume_set_user_provided.json").read_text(encoding="utf-8"))
    ai_jd_by_id = {row["sample_id"]: row for row in ai_jd}
    ai_resume_by_id = {row["resume_id"]: row.get("preannotation", {}) for row in ai_resume_payload.get("records", [])}
    gold_jd_by_id = {row["sample_id"]: row for row in gold_jd}
    gold_resume_by_id = {row["resume_id"]: row for row in gold_resume}

    jd_metrics = {
        "required": set_counts(gold_jd, ai_jd_by_id, "sample_id", "required_skills", "required_skills"),
        "bonus": set_counts(gold_jd, ai_jd_by_id, "sample_id", "bonus_skills", "bonus_skills"),
    }
    resume_metrics = {"skills": set_counts(gold_resume, ai_resume_by_id, "resume_id", "skills", "skills")}

    evaluated = []
    for row in gold_match:
        pred_jd = ai_jd_by_id.get(row["jd_sample_id"], {})
        pred_resume = ai_resume_by_id.get(row["resume_id"], {})
        gold_j = gold_jd_by_id[row["jd_sample_id"]]
        gold_r = gold_resume_by_id[row["resume_id"]]
        legacy_score = overlap_score(pred_jd.get("required_skills"), pred_jd.get("bonus_skills"), pred_resume.get("skills"))
        upper_score = overlap_score(gold_j["required_skills"], gold_j["bonus_skills"], gold_r["skills"])
        legacy_class = score_to_class(legacy_score)
        guarded_class = direction_guard(legacy_class, gold_r["target_job"], gold_j["job_title"])
        evaluated.append({**row, "legacy_score": legacy_score, "legacy_class": legacy_class, "guarded_class": guarded_class, "upper_score": upper_score, "upper_class": score_to_class(upper_score), "job_title": gold_j["job_title"], "target_job": gold_r["target_job"]})

    gold_labels = [row["relevance"] for row in evaluated]
    models = {}
    for name, class_key, score_key in (
        ("existing_ai_extraction_plus_overlap_v3", "legacy_class", "legacy_score"),
        ("direction_guarded_diagnostic", "guarded_class", "legacy_score"),
        ("gold_structured_overlap_upper_bound", "upper_class", "upper_score"),
    ):
        metrics = classification_metrics(gold_labels, [row[class_key] for row in evaluated])
        metrics["ranking"] = ranking_metrics(evaluated, score_key)
        metrics["largest_errors"] = [{"pair_id":r["pair_id"],"resume_id":r["resume_id"],"jd_sample_id":r["jd_sample_id"],"gold":r["relevance"],"predicted":r[class_key],"target_job":r["target_job"],"job_title":r["job_title"]} for r in sorted(evaluated,key=lambda x:(abs(x["relevance"]-x[class_key]),x["pair_id"]),reverse=True)[:20]]
        models[name] = metrics

    report = rounded({
        "schema_version":"1.1.0","gold_version":"gold_v1.1","formal_human_gold":True,
        "scope":{"jd":len(gold_jd),"resume":len(gold_resume),"match_pairs":len(gold_match),"match_queries":len(set(r['resume_id'] for r in gold_match))},
        "extraction":{"jd":jd_metrics,"resume":resume_metrics},"matching":models,
        "production_v8_note":"The online diversified_feedback_matching_v8 depends on PostgreSQL, Neo4j, behavior history, embeddings and optional GNN artifacts. It is not fully reproducible from the frozen offline workbook, so this report evaluates the existing reproducible AI-extraction + skill-overlap core and a direction-guard diagnostic.",
        "claim_limits":["The gold-structured overlap result is an upper-bound diagnostic because it consumes human structured skills as inputs.","Only existing_ai_extraction_plus_overlap_v3 is an end-to-end offline baseline.","Use validation data for future threshold tuning; do not tune on these 400 test labels."],
    })
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    base=models["existing_ai_extraction_plus_overlap_v3"]
    guard=models["direction_guarded_diagnostic"]
    upper=models["gold_structured_overlap_upper_bound"]
    lines=["# TalentGraph 人工金标 V1.0 基线评测","","> 本报告使用冻结人工金标；旧AI参考标签自一致性评测已移除。","","## 抽取基线","",f"- JD required F1：{report['extraction']['jd']['required']['f1']}",f"- JD bonus F1：{report['extraction']['jd']['bonus']['f1']}",f"- 简历技能 F1：{report['extraction']['resume']['skills']['f1']}","","## 匹配基线","",f"- 现有AI抽取+技能重叠：Accuracy {base['accuracy']}，Macro-F1 {base['macro_f1']}，Kappa {base['cohen_kappa']}，NDCG@10 {base['ranking']['ndcg@10']}",f"- 加岗位方向保护诊断：Accuracy {guard['accuracy']}，Macro-F1 {guard['macro_f1']}，Kappa {guard['cohen_kappa']}",f"- 人工结构化技能上限诊断：Accuracy {upper['accuracy']}，Macro-F1 {upper['macro_f1']}，Kappa {upper['cohen_kappa']}","","## 解释边界","",f"- {report['production_v8_note']}",*[f"- {x}" for x in report['claim_limits']]]
    REPORT_MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
