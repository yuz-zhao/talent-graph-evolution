"""Single registered entry point: fetch -> bronze -> normalize/validate -> gold."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from utils.collection_pipeline import CollectionStore,load_records,source_slug
REGISTRY_PATH=BASE/'config/source_registry.json';CHECKPOINT=BASE/'data/.ops/collection/checkpoints'

def registry():return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))['sources']
class SourceAdapter:
 def __init__(self,name,config,from_existing=False):self.name=name;self.config=config;self.from_existing=from_existing
 def fetch(self):
  if self.from_existing:return load_records(BASE/self.config['existing_file'])
  if self.name=='github':
   from spiders.tech.github_trend_spider import run;return run()
  if self.name=='gitee':
   from spiders.tech.gitee_trend_spider import run;return run()
  if self.name=='arxiv':
   from spiders.tech.arxiv_spider import run;return run()
  if self.name=='blog':
   from spiders.tech.blog_spider import run;return run()
  if self.name=='enterprise-greenhouse':
   from spiders.greenhouse_spider import GreenhouseSpider;return GreenhouseSpider().run()
  raise ValueError(f'{self.name}在线采集需由对应采集器接入；可先使用--from-existing')
 def parse(self,records):return [r for r in records if isinstance(r,dict)]
 def normalize(self,records):
  markers={'enterprise-greenhouse':'Greenhouse','arbeitnow':'Arbeitnow','remotive':'Remotive','ncss':'国家大学生就业','zhaopin':'智联','liepin':'猎聘','tencent-careers':'腾讯','china-telecom-careers':'中国电信','caict-careers':'信通院'}
  marker=markers.get(self.name)
  if marker:records=[r for r in records if marker in str(r.get('source_name',''))]
  return records
 def validate(self,records):return [r for r in records if (r.get('source_url') or r.get('html_url') or r.get('url') or r.get('official_url') or r.get('github_profile_url') or r.get('abs_url') or r.get('article_url')) and any(str(r.get(k,'')).strip() for k in ('job_title','title','name','full_name','display_name','course_name','certificate_name','description','abstract'))]
 def process(self,records):
  failures=[];parsed=[]
  for index,record in enumerate(records):
   if not isinstance(record,dict):
    failures.append({'stage':'parse','reason':'not_an_object','record_index':index,'value_type':type(record).__name__});continue
   parsed.append((index,record))
  normalized=[]
  for index,record in parsed:
   output=self.normalize([record])
   if not output:
    failures.append({'stage':'normalize','reason':'source_filter_mismatch','record_index':index,'source_url':record.get('source_url') or record.get('url') or ''});continue
   normalized.append((index,output[0]))
  valid=[]
  for index,record in normalized:
   url=record.get('source_url') or record.get('html_url') or record.get('url') or record.get('official_url') or record.get('github_profile_url') or record.get('abs_url') or record.get('article_url')
   content=any(str(record.get(k,'')).strip() for k in ('job_title','title','name','full_name','display_name','course_name','certificate_name','description','abstract'))
   if not url or not content:
    missing=[]
    if not url:missing.append('source_url')
    if not content:missing.append('content')
    failures.append({'stage':'validate','reason':'required_field_missing','record_index':index,'missing_fields':missing,'source_url':url or ''});continue
   valid.append(record)
  return valid,failures,{'parsed':len(parsed),'normalized':len(normalized),'validated':len(valid)}

def args():
 p=argparse.ArgumentParser();p.add_argument('--sources',default='github,arxiv,blog');p.add_argument('--from-existing',action='store_true');p.add_argument('--store',default=str(BASE/'data'));p.add_argument('--retries',type=int,default=3);p.add_argument('--rollback');p.add_argument('--list-sources',action='store_true');return p.parse_args()
def main():
 a=args();reg=registry();store=CollectionStore(a.store)
 if a.list_sources:print(json.dumps(reg,ensure_ascii=False,indent=2));return 0
 if a.rollback:print(json.dumps({'batch_id':a.rollback,'rolled_back':store.rollback(a.rollback)},ensure_ascii=False));return 0
 sources=[source_slug(x) for x in a.sources.split(',') if x.strip()];unknown=[x for x in sources if x not in reg]
 if unknown:raise SystemExit(f"未注册数据源: {','.join(unknown)}")
 CHECKPOINT.mkdir(parents=True,exist_ok=True);reports=[]
 for source in sources:
  adapter=SourceAdapter(source,reg[source],a.from_existing);error=None
  for attempt in range(1,a.retries+1):
   try:
    fetched=adapter.fetch();valid,failures,stage_counts=adapter.process(fetched);break
   except Exception as exc:
    error=exc
    if attempt>=a.retries:raise
    time.sleep(min(2**(attempt-1),8))
  report=store.ingest(source,reg[source]['data_type'],valid,reg[source]['source_type'],fetched_count=len(fetched),pipeline_failures=failures,stage_counts=stage_counts);reports.append(report.to_dict())
  (CHECKPOINT/f'{source}.json').write_text(json.dumps({'source':source,'last_successful_batch_id':report.batch_id,'record_count':report.valid,'updated_at':report.finished_at},ensure_ascii=False,indent=2),encoding='utf-8')
  time.sleep(float(reg[source].get('rate_limit_seconds',0)))
 print(json.dumps({'reports':reports},ensure_ascii=False,indent=2));return 0 if all(r.get('status')=='success' for r in reports) else 2
if __name__=='__main__':raise SystemExit(main())
