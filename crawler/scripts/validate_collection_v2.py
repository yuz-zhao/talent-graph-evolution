"""Offline acceptance test for lineage, idempotency, changes and rollback."""
from __future__ import annotations
import json,tempfile
from pathlib import Path
import sys
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from utils.collection_pipeline import CollectionStore
def main():
 with tempfile.TemporaryDirectory() as d:
  s=CollectionStore(d);one={'job_title':'5G工程师','company':'示例企业','source_url':'https://official.example/jobs/1','description':'负责5G网络优化','publish_time':'2026-08-01'}
  r1=s.ingest('offline-fixture','job',[one]);r2=s.ingest('offline-fixture','job',[dict(one)]);changed=dict(one,description='负责5G核心网与网络优化');r3=s.ingest('offline-fixture','job',[changed])
  gold=[json.loads(x) for x in (Path(d)/r3.gold_path).read_text(encoding='utf-8').splitlines() if x]
  checks={'all_gold_has_batch_id':all(x.get('crawl_batch_id') for x in gold),'gold_traces_to_bronze':all(x.get('bronze_record_id') and (Path(d)/x['lineage_uri'].split('#')[0]).exists() for x in gold),'idempotent_second_run':r2.unchanged==1 and r2.inserted==0,'field_changes_emitted':r3.updated==1 and any(c['field']=='description' for c in gold[0]['changed_fields']),'rollback_available':s.rollback(r3.batch_id),'quality_rules_by_type':r3.quality()['rules']['version']=='quality_rules_v2'}
 report={'checks':checks,'passed':all(checks.values()),'batches':[r1.batch_id,r2.batch_id,r3.batch_id]};out=BASE/'data/reports/collection_v2_quality_report.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
