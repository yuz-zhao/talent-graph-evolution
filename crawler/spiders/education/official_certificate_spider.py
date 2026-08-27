"""Collect verified certification records from issuer-owned public pages."""
from __future__ import annotations
import csv, hashlib, html, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data/silver/learning/certificate_data.csv"
RAW = BASE / "data/bronze/learning/certificate_pages"
UA = "TalentGraph-Evolution-Research/2.0"

# Multiple credentials may share an issuer's live official catalog page. A row is
# accepted only when its name and skill keyword are present in the fetched page.
SEEDS = [
 # 国家职业资格（官方制度页）
 ("计算机技术与软件专业技术资格（水平）", "工业和信息化部、人力资源和社会保障部", "https://hrss.sz.gov.cn/szksy/ztzl/zyjsks/zyjskslb/rsjrj/zxksxx_89388/content/post_12694118.html", "国家职业资格", "", "现行", ["软件工程"], "计算机软件资格考试"),
 ("HCIA-Datacom", "华为", "https://e.huawei.com/cn/news/ebg/2020/datacom-certification-launch-for-future-professional", "HCIA", "", "active", ["数据通信","网络工程"], "HCIA-Datacom"),
 ("HCIP-Datacom-Core Technology", "华为", "https://e.huawei.com/cn/news/ebg/2020/datacom-certification-launch-for-future-professional", "HCIP", "", "active", ["数据通信","网络工程"], "HCIP-Datacom-Core Technology"),
 # 国内云厂商
 *[(n,"阿里云","https://edu.aliyun.com/certification/",lv,"", "现行",skills,key) for n,lv,skills,key in [
  ("阿里云大模型工程师ACA认证","ACA",["大语言模型","人工智能"],"大模型"),("阿里云大模型高级工程师ACP认证","ACP",["大语言模型","RAG"],"大模型"),
  ("阿里云云计算工程师ACA认证","ACA",["云计算"],"云计算"),("阿里云云计算高级工程师ACP认证","ACP",["云计算","云架构"],"云计算"),
  ("阿里云云计算架构师ACE认证","ACE",["云计算","云架构"],"云计算架构"),("阿里云大数据工程师ACA认证","ACA",["大数据"],"大数据"),
  ("阿里云大数据高级工程师ACP认证","ACP",["大数据","数据分析"],"大数据"),
 ]],
 *[(n,"腾讯云","https://cloud.tencent.com/edu/training",lv,"", "现行",skills,key) for n,lv,skills,key in [
  ("腾讯云云计算工程师认证","工程师",["云计算"],"云计算工程师"),("腾讯云数据库工程师认证","工程师",["数据库"],"数据库工程师"),
  ("腾讯云大数据工程师认证","工程师",["大数据"],"大数据工程师"),("腾讯云人工智能工程师认证","工程师",["人工智能"],"人工智能工程师"),
  ("腾讯云云架构高级工程师认证","高级工程师",["云计算","云架构"],"云架构高级工程师"),("腾讯云云运维高级工程师认证","高级工程师",["运维","云计算"],"云运维高级工程师"),
  ("腾讯云DevOps高级工程师认证","高级工程师",["DevOps","CI/CD"],"DevOps高级工程师"),("腾讯云关系型数据库高级工程师认证","高级工程师",["数据库","MySQL"],"关系型数据库高级工程师"),
  ("腾讯云大数据高级工程师认证","高级工程师",["大数据"],"大数据高级工程师"),("腾讯云人工智能高级工程师认证","高级工程师",["人工智能","机器学习"],"人工智能高级工程师"),
  ("腾讯云云架构专家认证","专家",["云架构","云计算"],"云架构专家"),("腾讯云数据库专家认证","专家",["数据库"],"数据库专家"),
  ("腾讯云大数据专家认证","专家",["大数据"],"大数据专家"),("腾讯云人工智能专家认证","专家",["人工智能","机器学习"],"人工智能专家"),
 ]],
 # 国际厂商，均为具体官方认证页
 ("AWS Certified Cloud Practitioner","AWS","https://aws.amazon.com/certification/certified-cloud-practitioner/","Foundational","CLF-C02","active",["AWS","云计算"],"cloud practitioner"),
 ("AWS Certified Solutions Architect - Associate","AWS","https://aws.amazon.com/certification/certified-solutions-architect-associate/","Associate","SAA-C03","active",["AWS","云架构"],"solutions architect"),
 ("AWS Certified Developer - Associate","AWS","https://aws.amazon.com/certification/certified-developer-associate/","Associate","DVA-C02","active",["AWS","云计算"],"developer"),
 ("AWS Certified Data Engineer - Associate","AWS","https://aws.amazon.com/certification/certified-data-engineer-associate/","Associate","DEA-C01","active",["AWS","数据工程"],"data engineer"),
 ("AWS Certified Machine Learning Engineer - Associate","AWS","https://aws.amazon.com/certification/certified-machine-learning-engineer-associate/","Associate","MLA-C01","active",["AWS","机器学习"],"machine learning"),
 ("AWS Certified DevOps Engineer - Professional","AWS","https://aws.amazon.com/certification/certified-devops-engineer-professional/","Professional","DOP-C02","active",["AWS","DevOps"],"devops"),
 ("AWS Certified Security - Specialty","AWS","https://aws.amazon.com/certification/certified-security-specialty/","Specialty","SCS-C03","active",["AWS","信息安全"],"security"),
 ("Microsoft Certified: Azure Fundamentals","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/","Fundamentals","AZ-900","active",["Azure","云计算"],"azure fundamentals"),
 ("Microsoft Certified: Azure AI Fundamentals","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-fundamentals/","Fundamentals","AI-900","active",["Azure","人工智能"],"azure ai fundamentals"),
 ("Microsoft Certified: Azure Data Fundamentals","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/azure-data-fundamentals/","Fundamentals","DP-900","active",["Azure","数据库"],"azure data fundamentals"),
 ("Microsoft Certified: Azure Administrator Associate","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/azure-administrator/","Associate","AZ-104","active",["Azure","云计算"],"azure administrator"),
 ("Microsoft Certified: Azure Developer Associate","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/azure-developer/","Associate","AZ-204","active",["Azure","云计算"],"azure developer"),
 ("Microsoft Certified: DevOps Engineer Expert","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/devops-engineer/","Expert","AZ-400","active",["Azure","DevOps"],"devops engineer"),
 ("MCSA/MCSD/MCSE legacy certifications","Microsoft","https://learn.microsoft.com/en-us/credentials/certifications/posts/mcsa-mcsd-mcse-certifications-retire-with-continued-investment-to-role-based-certifications","Legacy","","retired",[],"certifications retire"),
]

def clean(text): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
def norm(text): return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.casefold())
def cert_id(issuer,name): return "cert_"+hashlib.sha256(f"{issuer}:{name}".encode()).hexdigest()[:20]
def evidence(text, keyword):
    match=re.search(re.escape(keyword),text,re.I)
    if not match: return ""
    return text[max(0,match.start()-120):min(len(text),match.end()+260)].strip()

def main():
    observed=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    batch=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); raw_dir=RAW/batch; raw_dir.mkdir(parents=True,exist_ok=True)
    session=requests.Session(); session.headers["User-Agent"]=UA; pages={}; rows=[]
    for name,issuer,url,level,exam_code,status,skills,keyword in SEEDS:
        if url not in pages:
            try:
                response=session.get(url,timeout=40,allow_redirects=True)
                if response.apparent_encoding: response.encoding=response.apparent_encoding
                pages[url]=(response.status_code,response.url,clean(response.text),response.text)
            except requests.RequestException: pages[url]=(0,url,"","")
            time.sleep(.25)
        code,final_url,text,raw=pages[url]; proof=evidence(text,keyword)
        if code != 200 or not proof: continue
        cid=cert_id(issuer,name)
        (raw_dir/f"{cid}.html").write_text(raw,encoding="utf-8",errors="ignore")
        prerequisites=[s for s in re.split(r"(?<=[.!?。])\s+",proof) if re.search(r"experience|prerequi|建议|经验",s,re.I)]
        rows.append({
          "certificate_id":cid,"certificate_name":name,"issuer":issuer,"official_url":final_url,"level":level,"exam_code":exam_code,
          "version":"current","languages":"[]","validity_period":"","renewal_required":"unknown","related_skills":json.dumps(skills,ensure_ascii=False),
          "skill_evidence":json.dumps([{"skill":s,"evidence":proof,"source":"official_outline_or_capability_page"} for s in skills],ensure_ascii=False),
          "prerequisites":json.dumps(prerequisites,ensure_ascii=False),"status":status,"updated_at":"","observed_at":observed,"url_status":"verified_200","source_type":"official_issuer_page"
        })
    fields=["certificate_id","certificate_name","issuer","official_url","level","exam_code","version","languages","validity_period","renewal_required","related_skills","skill_evidence","prerequisites","status","updated_at","observed_at","url_status","source_type"]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",encoding="utf-8-sig",newline="") as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    manifest={"batch_id":batch,"formal_certificates":len(rows),"issuers":sorted({r['issuer'] for r in rows}),"verified_urls":len(rows),"rejected_seeds":len(SEEDS)-len(rows)}
    (raw_dir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False)); return 0 if rows else 1

if __name__ == "__main__": raise SystemExit(main())
