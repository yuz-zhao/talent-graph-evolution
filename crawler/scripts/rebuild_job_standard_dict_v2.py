"""Rebuild job title mapping dictionary and enrich the formal JD dataset."""
from __future__ import annotations
import csv,json,sys
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from utils.job_standardize import standardize_job_title
JD=BASE/'data/silver/jobs/jd_clean.csv'; DICT=BASE/'data/gold/reference/job_standard_dict.csv'; REVIEW=BASE/'data/review/job_standard_mapping_review.csv'

def main():
    with JD.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f)); fields=list(rows[0])
    counts=Counter(r.get('job_title','').strip() for r in rows if r.get('job_title','').strip()); mappings={title:standardize_job_title(title) for title in counts}
    dict_fields=['raw_job_name','standard_job_name','job_family','job_level','job_direction','business_scene','occurrence_count','mapping_confidence','mapping_method','mapping_evidence','review_status']
    DICT.parent.mkdir(parents=True,exist_ok=True)
    with DICT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=dict_fields);w.writeheader()
        for title,m in sorted(mappings.items(),key=lambda x:(-counts[x[0]],x[0])):
            w.writerow({'raw_job_name':title,'standard_job_name':m.standard_job_name,'job_family':m.job_family,'job_level':m.job_level,'job_direction':m.job_direction,'business_scene':m.business_scene,'occurrence_count':counts[title],'mapping_confidence':f'{m.confidence:.2f}','mapping_method':m.mapping_method,'mapping_evidence':m.mapping_evidence,'review_status':'pending' if m.confidence<.75 else 'auto_accepted'})
    REVIEW.parent.mkdir(parents=True,exist_ok=True)
    with REVIEW.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=dict_fields);w.writeheader()
        for title,m in mappings.items():
            if m.confidence<.75:w.writerow({'raw_job_name':title,'standard_job_name':m.standard_job_name,'job_family':m.job_family,'job_level':m.job_level,'job_direction':m.job_direction,'business_scene':m.business_scene,'occurrence_count':counts[title],'mapping_confidence':f'{m.confidence:.2f}','mapping_method':m.mapping_method,'mapping_evidence':m.mapping_evidence,'review_status':'pending'})
    extra=['job_level','job_direction','business_scene','job_mapping_confidence','job_mapping_method','job_mapping_evidence']
    for field in extra:
        if field not in fields:fields.append(field)
    for row in rows:
        m=mappings.get(row.get('job_title','').strip())
        if not m:continue
        row['standard_job_name']=m.standard_job_name;row['job_family']=m.job_family;row['job_level']=m.job_level;row['job_direction']=m.job_direction;row['business_scene']=m.business_scene;row['job_mapping_confidence']=f'{m.confidence:.2f}';row['job_mapping_method']=m.mapping_method;row['job_mapping_evidence']=m.mapping_evidence
    with JD.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print(json.dumps({'jd_rows':len(rows),'unique_raw_titles':len(mappings),'auto_accepted_titles':sum(m.confidence>=.75 for m in mappings.values()),'review_titles':sum(m.confidence<.75 for m in mappings.values())},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
