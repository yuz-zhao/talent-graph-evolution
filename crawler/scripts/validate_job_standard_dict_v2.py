"""Validate high-frequency title coverage and structured mapping evidence."""
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];DICT=BASE/'data/gold/reference/job_standard_dict.csv';JD=BASE/'data/silver/jobs/jd_clean.csv';REPORT=BASE/'data/reports/job_standard_v2_quality_report.json'
FOCUS=('通信','5g','工业互联网','物联网','iot','芯片','半导体','嵌入式','firmware','智能制造')
def validate():
    with DICT.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with JD.open(encoding='utf-8-sig',newline='') as f:jds=list(csv.DictReader(f))
    high=[r for r in rows if int(r['occurrence_count'])>=2]; accepted=[r for r in high if float(r['mapping_confidence'])>=.75]
    focus=[r for r in rows if any(k in r['raw_job_name'].casefold() for k in FOCUS)]
    groups=defaultdict(set)
    for r in accepted:groups[r['standard_job_name']].add(r['raw_job_name'])
    checks={'high_frequency_coverage_gte_95_percent':len(accepted)/max(1,len(high))>=.95,'focus_families_present':all(any(label in r['job_family'] or label in r['job_direction'] for r in rows) for label in ('通信','工业互联网','物联网','芯片','嵌入式','智能制造')),'evidence_and_confidence_complete':all(r['mapping_evidence'] and r['mapping_method'] and r['mapping_confidence'] for r in rows),'low_confidence_reviewed_separately':all(r['review_status']=='pending' for r in rows if float(r['mapping_confidence'])<.75),'jd_structured_fields_complete':all(all(r.get(k) for k in ('job_level','job_direction','business_scene','job_mapping_confidence','job_mapping_evidence')) for r in jds),'standard_groups_compress_variants':any(len(v)>=3 for v in groups.values())}
    report={'jd_rows':len(jds),'unique_raw_titles':len(rows),'high_frequency_titles':len(high),'high_frequency_accepted':len(accepted),'high_frequency_coverage':round(len(accepted)/max(1,len(high)),4),'low_confidence_review_queue':sum(float(r['mapping_confidence'])<.75 for r in rows),'focus_title_mappings':len(focus),'standard_job_groups':len(groups),'largest_variant_groups':sorted(({'standard_job_name':k,'raw_title_variants':len(v)} for k,v in groups.items()),key=lambda x:-x['raw_title_variants'])[:15],'checks':checks,'passed':all(checks.values())}
    REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':raise SystemExit(0 if validate()['passed'] else 1)
