"""真实官方课程与学习资源采集器。"""
from __future__ import annotations
import argparse, csv, hashlib, html, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from utils.skill_mapping import extract_skill_matches  # noqa: E402

CATALOG = "https://learn.microsoft.com/api/catalog/?locale=en-us&type=modules,learningPaths,units"
OUT = BASE / "data/silver/learning/course_data.csv"
RAW = BASE / "data/bronze/learning/course_api"
USER_AGENT = "TalentGraph-Evolution-Research/2.0"

OFFICIAL_RESOURCES = [
    ("Python Software Foundation", "https://docs.python.org/3/tutorial/"),
    ("Oracle Java", "https://dev.java/learn/"), ("Go Team", "https://go.dev/tour/"),
    ("Rust Project", "https://doc.rust-lang.org/book/"), ("React", "https://react.dev/learn"),
    ("Vue", "https://vuejs.org/tutorial/"), ("Docker", "https://docs.docker.com/get-started/"),
    ("Kubernetes", "https://kubernetes.io/docs/tutorials/kubernetes-basics/"),
    ("PostgreSQL", "https://www.postgresql.org/docs/current/tutorial.html"),
    ("MySQL", "https://dev.mysql.com/doc/refman/8.4/en/tutorial.html"),
    ("TensorFlow", "https://www.tensorflow.org/tutorials"),
    ("PyTorch", "https://docs.pytorch.org/tutorials/"),
    ("Hugging Face", "https://huggingface.co/learn/llm-course/chapter1/1"),
    ("Git", "https://git-scm.com/book/en/v2"),
    ("MongoDB", "https://learn.mongodb.com/"),
    ("Redis", "https://university.redis.io/"),
    ("Node.js", "https://nodejs.org/en/learn/getting-started/introduction-to-nodejs"),
    ("TypeScript", "https://www.typescriptlang.org/docs/handbook/intro.html"),
    ("Apache Kafka", "https://kafka.apache.org/quickstart"),
    ("Apache Spark", "https://spark.apache.org/docs/latest/quick-start.html"),
    ("Apache Flink", "https://nightlies.apache.org/flink/flink-docs-stable/docs/learn-flink/overview/"),
    ("Prometheus", "https://prometheus.io/docs/tutorials/getting_started/"),
    ("Grafana", "https://grafana.com/tutorials/"),
    ("Terraform", "https://developer.hashicorp.com/terraform/tutorials"),
    ("Linux Foundation", "https://training.linuxfoundation.org/training/introduction-to-linux/"),
    ("Microsoft Learn", "https://learn.microsoft.com/en-us/training/paths/defender-iot-deploy-ot-monitoring/"),
    ("Microsoft Learn", "https://learn.microsoft.com/en-us/training/career-paths/information-protection-admin"),
    ("Microsoft Learn", "https://learn.microsoft.com/en-us/analysis-services/data-mining/data-mining-concepts?view=asallproducts-allversions"),
    ("Apache Hive", "https://hive.apache.org/docs/latest/user/tutorial/"),
    ("Hugging Face", "https://huggingface.co/learn/computer-vision-course/unit0/welcome/welcome"),
]

def now_iso(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def clean(value): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()
def stable_id(provider, uid): return "course_" + hashlib.sha256(f"{provider}:{uid}".encode()).hexdigest()[:20]

class PageParser(HTMLParser):
    def __init__(self): super().__init__(); self.in_title=False; self.title=[]; self.capture=False; self.parts=[]; self.headings=[]; self.meta={}
    def handle_starttag(self, tag, attrs):
        data=dict(attrs)
        if tag=='title': self.in_title=True
        if tag in {'main','article','p','h1','h2','h3','li'}: self.capture=True
        if tag in {'h1','h2','h3'}: self.headings.append([])
        key=data.get('name') or data.get('property')
        if tag=='meta' and key and data.get('content'): self.meta[key.casefold()]=data['content']
    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
        if tag in {'main','article','p','h1','h2','h3','li'}: self.capture=False
    def handle_data(self,data):
        if self.in_title: self.title.append(data)
        if self.capture and data.strip():
            self.parts.append(data.strip())
            if self.headings: self.headings[-1].append(data.strip())

def skill_evidence(description, syllabus):
    text = f"{description}\n" + "\n".join(syllabus)
    evidence=[]
    for match in extract_skill_matches(text):
        start=max(0,match.start-90); end=min(len(text),match.start+len(match.raw)+160)
        evidence.append({"skill":match.standard,"raw":match.raw,"evidence":text[start:end].strip()[:350],"source_field":"description_and_syllabus","method":"skill_ontology_alias_rule_v3"})
    unique={}
    # 领域短语只在课程简介/目录正文中命中；课程标题不参与技能猜测。
    for pattern, standard in [(r'(?i)\b(?:iot|internet of things)\b', '物联网'), (r'(?i)\bmultimodal\b', '多模态学习')]:
        found=re.search(pattern,text)
        if found:
            start=max(0,found.start()-90); end=min(len(text),found.end()+160)
            evidence.append({"skill":standard,"raw":found.group(0),"evidence":text[start:end].strip()[:350],"source_field":"description_and_syllabus","method":"strict_domain_phrase_rule_v1"})
    for item in evidence: unique.setdefault(item['skill'].casefold(),item)
    values=list(unique.values()); return [item['skill'] for item in values],values

def page_info(session, url):
    try:
        response=session.get(url,timeout=35,allow_redirects=True)
        content_type=response.headers.get('Content-Type','')
        parser=PageParser()
        if response.status_code==200 and 'html' in content_type: parser.feed(response.text)
        return {"status":response.status_code,"final_url":response.url,"title":clean(' '.join(parser.title)),"description":clean(parser.meta.get('description') or parser.meta.get('og:description') or ''),"headings":[clean(' '.join(x)) for x in parser.headings if clean(' '.join(x))],"body":clean(' '.join(parser.parts))[:12000],"content":response.content}
    except requests.RequestException:
        return {"status":0,"final_url":url,"title":"","description":"","headings":[],"body":"","content":b''}

def microsoft_rows(payload):
    modules={item.get('uid'):item for item in payload.get('modules',[])}
    units={item.get('uid'):item for item in payload.get('units',[])}
    rows=[]
    for item in list(modules.values()) + payload.get('learningPaths',[]):
        item_type=item.get('type') or ('learningPath' if item.get('modules') else 'module')
        if item_type=='module': syllabus=[clean(units[uid].get('title')) for uid in item.get('units',[]) if uid in units]
        else: syllabus=[clean(modules[uid].get('title')) for uid in item.get('modules',[]) if uid in modules]
        description=clean(item.get('summary'))
        skills,evidence=skill_evidence(description,syllabus)
        if not skills: continue
        prerequisites=[sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+',description) if re.search(r'prerequi|familiar|experience|before',sentence,re.I)]
        rows.append({
            "course_id":stable_id("Microsoft Learn",item.get('uid','')),"canonical_course_id":item.get('uid',''),"version_id":f"{item.get('uid','')}:{item.get('locale','en-us')}",
            "course_name":clean(item.get('title')),"provider":"Microsoft Learn","official_url":item.get('url',''),"language":item.get('locale','en-us'),
            "difficulty":";".join(item.get('levels') or []),"duration_value":item.get('duration_in_minutes',''),"duration_unit":"minute" if item.get('duration_in_minutes') is not None else "",
            "course_type":"learning_path" if item_type=='learningPath' else "self_paced_module","syllabus":json.dumps(syllabus,ensure_ascii=False),"prerequisites":json.dumps(prerequisites,ensure_ascii=False),
            "skills":json.dumps(skills,ensure_ascii=False),"skill_evidence":json.dumps(evidence,ensure_ascii=False),"certificate_available":"false","price_type":"free",
            "published_at":"","updated_at":item.get('last_modified',''),"observed_at":now_iso(),"url_status":"pending","page_title":"","title_match":"false","availability_status":"pending","source_type":"official_catalog_api",
        })
    return rows

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--limit',type=int,default=700); parser.add_argument('--workers',type=int,default=8); parser.add_argument('--supplement-only',action='store_true'); args=parser.parse_args()
    observed=now_iso(); batch=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); raw_dir=RAW/batch; raw_dir.mkdir(parents=True,exist_ok=True)
    session=requests.Session(); session.headers['User-Agent']=USER_AGENT; rows=[]
    if args.supplement_only and OUT.exists():
        with OUT.open('r',encoding='utf-8-sig',newline='') as handle: rows=list(csv.DictReader(handle))
    else:
        try:
            response=session.get(CATALOG,timeout=120); response.raise_for_status(); payload=response.json(); (raw_dir/'microsoft_catalog.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8'); rows=microsoft_rows(payload)[:args.limit]
            print(f"Microsoft Learn候选: {len(rows)}")
        except (requests.RequestException,ValueError) as exc: print(f"Microsoft Learn目录不可用: {type(exc).__name__}")
    curated=[]
    for provider,url in OFFICIAL_RESOURCES:
        info=page_info(session,url)
        if info['status']!=200 or not info['title']: continue
        description=info['description'] or info['body'][:1500]; syllabus=info['headings'][:30]
        skills,evidence=skill_evidence(description,syllabus)
        if not skills: continue
        uid=urlparse(info['final_url']).path.rstrip('/') or info['final_url']
        curated.append({"course_id":stable_id(provider,uid),"canonical_course_id":stable_id(provider,uid),"version_id":stable_id(provider,uid)+":default","course_name":info['title'].split(' | ')[0].strip(),"provider":provider,"official_url":info['final_url'],"language":"en","difficulty":"","duration_value":"","duration_unit":"","course_type":"official_tutorial","syllabus":json.dumps(syllabus,ensure_ascii=False),"prerequisites":"[]","skills":json.dumps(skills,ensure_ascii=False),"skill_evidence":json.dumps(evidence,ensure_ascii=False),"certificate_available":"false","price_type":"free","published_at":"","updated_at":"","observed_at":observed,"url_status":"verified_200","page_title":info['title'],"title_match":"true","availability_status":"active","source_type":"official_public_page"})
        time.sleep(.3)
    rows.extend(curated); rows=list({row['course_id']:row for row in rows}.values()); print(f"其他官方资源: {len(curated)}")

    pending=[row for row in rows if row['url_status']=='pending']
    def verify(row):
        info=page_info(requests.Session(),row['official_url']); title=info['title']; expected=re.sub(r'[^a-z0-9]+',' ',row['course_name'].casefold()).strip(); actual=re.sub(r'[^a-z0-9]+',' ',title.casefold()).strip()
        row['url_status']='verified_200' if info['status']==200 else f"http_{info['status']}"; row['availability_status']='active' if info['status']==200 else 'unavailable'; row['page_title']=title; row['title_match']='true' if expected and (expected in actual or actual in expected) else 'false'; return row,info['content']
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        futures={pool.submit(verify,row):row for row in pending}
        for index,future in enumerate(as_completed(futures),1):
            row,content=future.result()
            if content and index<=30: (raw_dir/f"page_{row['course_id']}.html").write_bytes(content)
    # 正式推荐集只接受URL有效且页面标题吻合的课程。
    rows=[row for row in rows if row['url_status']=='verified_200' and row['title_match']=='true']
    fields=["course_id","canonical_course_id","version_id","course_name","provider","official_url","language","difficulty","duration_value","duration_unit","course_type","syllabus","prerequisites","skills","skill_evidence","certificate_available","price_type","published_at","updated_at","observed_at","url_status","page_title","title_match","availability_status","source_type"]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',encoding='utf-8-sig',newline='') as handle: writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    report={"batch_id":batch,"formal_courses":len(rows),"providers":sorted({r['provider'] for r in rows}),"verified_urls":sum(r['url_status']=='verified_200' for r in rows),"title_matches":sum(r['title_match']=='true' for r in rows)}
    (raw_dir/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
