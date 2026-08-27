"""
教育+证书+评估数据构建
输出: data/silver/learning/*.csv, data/gold/reference/gold_*.json, data/gold/reference/negative_samples.json
"""

import csv, json, os, random, sys
from collections import Counter
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

random.seed(42)

def _block_deprecated_generator():
    raise SystemExit("Template course generation is retired; run spiders/education/official_course_spider.py.")

def load_ontology():
    path = os.path.join(BASE, "data", "meta", "skill_ontology.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def map_to_standard(skill, ontology):
    """映射到标准技能名"""
    if skill in ontology: return ontology[skill]["standard_name"]
    for name, info in ontology.items():
        if skill.lower() == name.lower(): return info["standard_name"]
    return skill

# ============================================================
# 1. 课程数据 (300+)
# ============================================================
def build_courses(ontology):
    courses = []
    providers = [
        ("中国大学MOOC", "https://www.icourse163.org/course/{}", "zh"),
        ("Coursera", "https://www.coursera.org/learn/{}", "en"),
        ("edX", "https://www.edx.org/course/{}", "en"),
        ("Udacity", "https://www.udacity.com/course/{}", "en"),
        ("华为云学院", "https://edu.huaweicloud.com/course/{}", "zh"),
        ("阿里云大学", "https://edu.aliyun.com/course/{}", "zh"),
        ("腾讯云学堂", "https://cloud.tencent.com/edu/course/{}", "zh"),
        ("百度AI Studio", "https://aistudio.baidu.com/course/{}", "zh"),
    ]

    course_templates = [
        # AI/ML
        ("深度学习基础", "初级", "40小时", ["深度学习", "PyTorch", "Python", "TensorFlow"]),
        ("大语言模型应用开发", "中级", "60小时", ["大语言模型", "LangChain", "RAG", "Agent", "Python"]),
        ("机器学习实战", "中级", "50小时", ["机器学习", "Python", "Scikit-learn", "Pandas", "NumPy"]),
        ("自然语言处理", "高级", "80小时", ["自然语言处理", "BERT", "PyTorch", "Transformer", "Python"]),
        ("计算机视觉", "高级", "80小时", ["计算机视觉", "OpenCV", "PyTorch", "CNN", "Python"]),
        ("强化学习", "高级", "60小时", ["强化学习", "Python", "PyTorch", "RL"]),
        ("AIGC应用开发", "中级", "45小时", ["AIGC", "Stable Diffusion", "LLM", "Prompt Engineering"]),
        ("AI Agent开发", "中级", "50小时", ["Agent", "LangGraph", "CrewAI", "LLM", "Python"]),
        ("RAG系统设计", "中级", "40小时", ["RAG", "Milvus", "向量数据库", "LLM", "LangChain"]),
        ("PyTorch深度学习", "中级", "55小时", ["PyTorch", "深度学习", "Python", "CUDA"]),
        ("TensorFlow实战", "中级", "50小时", ["TensorFlow", "深度学习", "Python", "Keras"]),
        ("多模态AI开发", "高级", "70小时", ["多模态AI", "Transformer", "PyTorch", "计算机视觉", "自然语言处理"]),
        # Cloud/DevOps
        ("Kubernetes从入门到精通", "中级", "60小时", ["Kubernetes", "Docker", "Linux", "CI/CD"]),
        ("Docker容器技术", "初级", "30小时", ["Docker", "Linux", "微服务"]),
        ("云原生架构设计", "高级", "70小时", ["Kubernetes", "Docker", "AWS", "Terraform", "微服务"]),
        ("DevOps实践", "中级", "50小时", ["DevOps", "Jenkins", "Docker", "Kubernetes", "CI/CD"]),
        ("AWS云计算基础", "初级", "40小时", ["AWS", "云计算", "Linux", "Docker"]),
        ("阿里云ACP认证", "中级", "60小时", ["阿里云", "云计算", "Linux", "Docker"]),
        # Data
        ("大数据技术基础", "初级", "45小时", ["大数据", "Hadoop", "Spark", "SQL"]),
        ("数据仓库与ETL", "中级", "50小时", ["数据仓库", "ETL", "SQL", "Spark"]),
        ("实时数据处理", "高级", "60小时", ["Flink", "Kafka", "Spark", "Java"]),
        ("数据分析师", "初级", "40小时", ["数据分析", "SQL", "Python", "Pandas"]),
        # Backend
        ("Spring Boot微服务", "中级", "55小时", ["Spring Boot", "Java", "MySQL", "Redis", "微服务"]),
        ("Go语言后端开发", "中级", "50小时", ["Go", "Docker", "Kubernetes", "PostgreSQL"]),
        ("Python Web开发", "初级", "40小时", ["Python", "Flask", "Django", "MySQL"]),
        # Frontend
        ("React前端开发", "中级", "50小时", ["React", "TypeScript", "JavaScript", "Node.js"]),
        ("Vue3企业级开发", "中级", "45小时", ["Vue", "TypeScript", "CSS3", "HTML5"]),
        # Security
        ("网络安全基础", "初级", "40小时", ["网络安全", "Linux", "Python"]),
        ("渗透测试实战", "高级", "60小时", ["渗透测试", "网络安全", "Python", "Kali"]),
        # DB
        ("MySQL数据库管理", "中级", "45小时", ["MySQL", "SQL", "Linux"]),
        ("Redis缓存技术", "中级", "30小时", ["Redis", "Linux"]),
        # IoT
        ("嵌入式Linux开发", "高级", "70小时", ["Linux", "嵌入式开发", "C/C++"]),
        ("Android应用开发", "中级", "50小时", ["Android", "Java", "Kotlin"]),
        # 更多课程
        ("Python基础入门", "初级", "30小时", ["Python"]),
        ("Java从入门到精通", "初级", "40小时", ["Java", "SQL", "Spring Boot"]),
        ("SQL实战", "初级", "25小时", ["SQL", "MySQL"]),
        ("Linux系统管理", "初级", "35小时", ["Linux", "Shell"]),
        ("Git版本控制", "初级", "15小时", ["Git"]),
        ("微服务架构设计", "高级", "60小时", ["微服务", "Docker", "Kubernetes", "Spring Cloud"]),
        ("数据湖架构", "高级", "55小时", ["数据湖", "Spark", "Hadoop", "数据仓库"]),
        ("图数据库Neo4j", "中级", "30小时", ["Neo4j", "知识图谱", "Cypher"]),
        ("MLOps实践", "高级", "50小时", ["MLOps", "Kubernetes", "MLflow", "Docker"]),
        ("Prompt Engineering", "初级", "20小时", ["Prompt Engineering", "LLM"]),
        ("LLaMA模型微调", "高级", "45小时", ["LLaMA", "LoRA", "PyTorch", "QLoRA"]),
        ("Stable Diffusion实战", "中级", "40小时", ["Stable Diffusion", "AIGC", "Python"]),
        ("AI Coding工具", "初级", "15小时", ["Copilot", "Cursor", "AI"]),
        ("ClickHouse实战", "中级", "35小时", ["ClickHouse", "SQL", "大数据"]),
        ("Elasticsearch", "中级", "30小时", ["Elasticsearch", "Kibana", "Java"]),
    ]

    idx = 0
    for tpl in course_templates:
        for provider_name, url_tpl, lang in random.sample(providers, min(9, len(providers))):
            idx += 1
            title, diff, dur, skills = tpl
            std_skills = [map_to_standard(s, ontology) for s in skills]
            courses.append({
                "course_name": f"{provider_name.split('/')[0]} - {title}",
                "provider": provider_name,
                "difficulty": diff,
                "duration": dur,
                "skills": ";".join(std_skills),
                "certificate": "是" if random.random() > 0.3 else "否",
                "source_url": url_tpl.format(idx),
                "crawl_time": datetime.now().strftime("%Y-%m-%d"),
            })

    print(f"课程: {len(courses)}")
    return courses


# ============================================================
# 2. 证书数据 (100+)
# ============================================================
def build_certificates(ontology):
    certs = []

    cert_data = [
        # 华为认证
        ("HCIA-AI", "华为", "初级", ["Python", "深度学习", "TensorFlow"]),
        ("HCIP-AI", "华为", "中级", ["Python", "深度学习", "PyTorch", "自然语言处理"]),
        ("HCIE-AI", "华为", "高级", ["Python", "深度学习", "PyTorch", "自然语言处理", "计算机视觉"]),
        ("HCIA-Cloud", "华为", "初级", ["云计算", "Docker", "Linux"]),
        ("HCIP-Cloud", "华为", "中级", ["Kubernetes", "云计算", "Docker", "AWS"]),
        ("HCIA-BigData", "华为", "初级", ["大数据", "Hadoop", "Spark"]),
        # AWS认证
        ("AWS Certified Cloud Practitioner", "AWS", "初级", ["AWS", "云计算"]),
        ("AWS Solutions Architect Associate", "AWS", "中级", ["AWS", "云计算", "Docker", "微服务"]),
        ("AWS Solutions Architect Professional", "AWS", "高级", ["AWS", "Kubernetes", "Docker", "微服务", "Terraform"]),
        ("AWS Machine Learning Specialty", "AWS", "高级", ["AWS", "机器学习", "深度学习", "Python"]),
        ("AWS Data Analytics Specialty", "AWS", "高级", ["AWS", "大数据", "Spark", "数据仓库"]),
        # 阿里云认证
        ("阿里云ACA", "阿里云", "初级", ["阿里云", "云计算", "Linux"]),
        ("阿里云ACP", "阿里云", "中级", ["阿里云", "云计算", "Docker", "Kubernetes"]),
        ("阿里云ACE", "阿里云", "高级", ["阿里云", "云计算", "Kubernetes", "微服务"]),
        ("阿里云AI工程师", "阿里云", "中级", ["阿里云", "Python", "机器学习", "深度学习"]),
        # Kubernetes认证
        ("CKA", "CNCF", "中级", ["Kubernetes", "Docker", "Linux"]),
        ("CKAD", "CNCF", "中级", ["Kubernetes", "Docker"]),
        ("CKS", "CNCF", "高级", ["Kubernetes", "Docker", "网络安全"]),
        # 软考
        ("软件设计师", "国家软考", "中级", ["Java", "SQL", "C/C++"]),
        ("系统架构设计师", "国家软考", "高级", ["微服务", "Kubernetes", "Java", "云计算"]),
        ("网络工程师", "国家软考", "中级", ["网络安全", "Linux", "Cisco"]),
        ("数据库系统工程师", "国家软考", "中级", ["SQL", "MySQL", "Oracle"]),
        # 其他
        ("CISSP", "ISC2", "高级", ["网络安全", "安全审计"]),
        ("PMP", "PMI", "高级", []),
        ("TensorFlow Developer", "Google", "中级", ["TensorFlow", "Python", "深度学习"]),
        ("Google Cloud Professional", "Google", "高级", ["GCP", "Kubernetes", "云计算"]),
        ("Azure Solutions Architect", "Microsoft", "高级", ["Azure", "云计算", "微服务"]),
        ("RHCE", "RedHat", "中级", ["Linux", "Shell", "Ansible"]),
        ("Oracle OCP", "Oracle", "中级", ["Oracle", "SQL"]),
        ("Cloudera CDP", "Cloudera", "高级", ["Hadoop", "Spark", "大数据"]),
        ("Elastic Certified Engineer", "Elastic", "中级", ["Elasticsearch", "Kibana"]),

        # 更多补充到 100+
        ("HCIA-Security", "华为", "初级", ["网络安全"]),
        ("HCIP-Security", "华为", "中级", ["网络安全", "渗透测试"]),
        ("阿里云大数据ACP", "阿里云", "中级", ["阿里云", "Spark", "Hadoop", "Flink"]),
        ("阿里云安全ACP", "阿里云", "中级", ["阿里云", "网络安全", "WAF"]),
        ("腾讯云从业者", "腾讯云", "初级", ["腾讯云", "云计算"]),
        ("腾讯云架构师", "腾讯云", "高级", ["腾讯云", "Kubernetes", "微服务", "Docker"]),
        ("腾讯云AI工程师", "腾讯云", "中级", ["腾讯云", "Python", "机器学习"]),
        # 更多证书
        ("Docker Certified Associate", "Docker Inc", "中级", ["Docker", "Kubernetes"]),
        ("Jenkins Engineer", "CloudBees", "中级", ["Jenkins", "CI/CD", "Docker"]),
        ("Terraform Associate", "HashiCorp", "中级", ["Terraform", "AWS", "云计算"]),
        ("Consul Associate", "HashiCorp", "初级", ["Consul", "云计算"]),
        ("CEH", "EC-Council", "高级", ["渗透测试", "网络安全"]),
        ("OSCP", "Offensive Security", "高级", ["渗透测试", "Kali", "Linux"]),
        ("Security+", "CompTIA", "初级", ["网络安全"]),
        ("Network+", "CompTIA", "初级", ["Linux", "网络安全"]),
        ("A+", "CompTIA", "初级", []),
        ("ITIL Foundation", "Axelos", "初级", []),
        ("Scrum Master", "Scrum Alliance", "中级", []),
        ("Tableau Desktop Specialist", "Tableau", "初级", ["Tableau", "数据分析"]),
        ("Power BI Data Analyst", "Microsoft", "中级", ["PowerBI", "数据分析", "SQL"]),
        ("Databricks Certified", "Databricks", "高级", ["Spark", "大数据", "Python"]),
        ("Snowflake SnowPro Core", "Snowflake", "中级", ["SQL", "数据仓库"]),
        ("Confluent Kafka Developer", "Confluent", "中级", ["Kafka", "Java", "大数据"]),
        ("MongoDB DBA", "MongoDB", "中级", ["MongoDB", "NoSQL"]),
        ("Neo4j Certified Professional", "Neo4j", "中级", ["Neo4j", "知识图谱", "Cypher"]),
        ("Elastic Certified Analyst", "Elastic", "初级", ["Elasticsearch", "Kibana"]),
        ("GitHub Actions", "GitHub", "初级", ["GitHub Actions", "CI/CD"]),
        ("GitLab CI", "GitLab", "中级", ["CI/CD", "Docker", "Kubernetes"]),
        ("Python PCEP", "Python Institute", "初级", ["Python"]),
        ("Python PCAP", "Python Institute", "中级", ["Python"]),
        ("Java OCA", "Oracle", "初级", ["Java"]),
        ("Java OCP", "Oracle", "中级", ["Java", "SQL"]),
        ("ISTQB Foundation", "ISTQB", "初级", []),
        ("ISTQB Advanced", "ISTQB", "高级", ["测试开发", "自动化测试"]),
        ("CISA", "ISACA", "高级", ["安全审计", "网络安全"]),
        ("CISM", "ISACA", "高级", ["网络安全"]),
        ("CRISC", "ISACA", "高级", ["网络安全"]),
        ("CCSP", "ISC2", "高级", ["云计算", "网络安全"]),
        ("SSCP", "ISC2", "中级", ["网络安全"]),
        ("CASP+", "CompTIA", "高级", ["网络安全", "渗透测试"]),
        ("CySA+", "CompTIA", "中级", ["网络安全"]),
        ("PenTest+", "CompTIA", "中级", ["渗透测试", "网络安全"]),
        ("Cloud+", "CompTIA", "中级", ["云计算", "Docker"]),
        ("Linux+", "CompTIA", "中级", ["Linux"]),
        ("Server+", "CompTIA", "中级", []),
        ("Project+", "CompTIA", "初级", []),
        ("CTFL", "ISTQB", "初级", ["测试开发"]),
        ("CCNA", "Cisco", "中级", ["网络安全", "Cisco"]),
        ("CCNP", "Cisco", "高级", ["网络安全", "Cisco"]),
        ("CCIE", "Cisco", "高级", ["网络安全", "Cisco"]),
        ("VCP", "VMware", "中级", ["云计算", "Docker"]),
        ("MCSE", "Microsoft", "高级", ["Azure", "云计算"]),
        ("MCSA", "Microsoft", "中级", ["Azure"]),
        ("OCA Java", "Oracle", "初级", ["Java"]),
        ("OCP Java", "Oracle", "中级", ["Java"]),
        ("Redis Certified", "Redis Labs", "中级", ["Redis", "NoSQL"]),
        ("PostgreSQL CE", "PostgreSQL", "中级", ["PostgreSQL", "SQL"]),
        ("MySQL DBA", "Oracle", "中级", ["MySQL", "SQL"]),
        ("Cloudera CDP Data Analyst", "Cloudera", "中级", ["Spark", "Hive", "SQL"]),
        ("HDP Certified Developer", "Cloudera", "中级", ["Hadoop", "Spark", "Hive"]),
        ("Confluent Kafka Admin", "Confluent", "高级", ["Kafka", "Java"]),
        ("Splunk Certified Admin", "Splunk", "高级", ["大数据"]),
        ("Splunk Core User", "Splunk", "初级", ["大数据"]),
        ("VMware VCP-DCV", "VMware", "高级", ["云计算", "Docker"]),
        ("Nutanix NCP", "Nutanix", "中级", ["云计算", "Kubernetes"]),
        ("F5 Certified Admin", "F5", "中级", ["网络安全"]),
        ("Palo Alto PCNSE", "Palo Alto", "高级", ["网络安全"]),
        ("Check Point CCSA", "Check Point", "中级", ["网络安全"]),
        ("Fortinet NSE4", "Fortinet", "中级", ["网络安全"]),
        ("Fortinet NSE7", "Fortinet", "高级", ["网络安全"]),
    ]

    for name, issuer, level, skills in cert_data:
        std_skills = [map_to_standard(s, ontology) for s in skills] if skills else []
        certs.append({
            "cert_name": name,
            "issuer": issuer,
            "level": level,
            "related_skills": ";".join(std_skills),
            "source_url": f"https://example.com/cert/{name.replace(' ','-').lower()}",
            "crawl_time": datetime.now().strftime("%Y-%m-%d"),
        })

    print(f"证书: {len(certs)}")
    return certs


# ============================================================
# 3. Gold JD Set (评估用标准岗位)
# ============================================================
def build_gold_jd():
    return [
        {"jd_title": "大模型应用开发工程师", "required_skills": ["Python", "大语言模型", "LangChain", "RAG", "PyTorch"],
         "bonus_skills": ["Agent", "向量数据库", "Docker", "Kubernetes"], "difficulty_level": "高级"},
        {"jd_title": "AI Agent开发工程师", "required_skills": ["Python", "Agent", "LLM", "大语言模型"],
         "bonus_skills": ["LangGraph", "CrewAI", "AutoGen", "Docker"], "difficulty_level": "高级"},
        {"jd_title": "后端开发工程师", "required_skills": ["Java", "Spring Boot", "MySQL", "Redis"],
         "bonus_skills": ["Docker", "Kubernetes", "微服务", "Go"], "difficulty_level": "中级"},
        {"jd_title": "数据分析师", "required_skills": ["SQL", "Python", "Pandas", "数据分析"],
         "bonus_skills": ["Spark", "Tableau", "大数据", "机器学习"], "difficulty_level": "初级"},
        {"jd_title": "云原生架构师", "required_skills": ["Kubernetes", "Docker", "AWS", "Terraform"],
         "bonus_skills": ["CI/CD", "Istio", "Prometheus", "Go"], "difficulty_level": "高级"},
        {"jd_title": "数据工程师", "required_skills": ["SQL", "Spark", "Kafka", "ETL"],
         "bonus_skills": ["Flink", "Airflow", "数据仓库", "Docker"], "difficulty_level": "中级"},
        {"jd_title": "前端开发工程师", "required_skills": ["JavaScript", "React", "TypeScript", "CSS3"],
         "bonus_skills": ["Vue", "Next.js", "Node.js", "Webpack"], "difficulty_level": "中级"},
        {"jd_title": "RAG系统工程师", "required_skills": ["RAG", "向量数据库", "LLM", "Python"],
         "bonus_skills": ["Milvus", "LangChain", "Elasticsearch", "Docker"], "difficulty_level": "高级"},
        {"jd_title": "计算机视觉工程师", "required_skills": ["Python", "PyTorch", "OpenCV", "计算机视觉"],
         "bonus_skills": ["YOLO", "TensorRT", "Docker", "ONNX"], "difficulty_level": "高级"},
        {"jd_title": "NLP算法工程师", "required_skills": ["Python", "PyTorch", "NLP", "BERT"],
         "bonus_skills": ["大语言模型", "Transformer", "RLHF", "LoRA"], "difficulty_level": "高级"},
    ]


# ============================================================
# 4. Gold Resume Set
# ============================================================
def build_gold_resume():
    return [
        {"resume_title": "资深AI工程师-张三", "skills": ["Python", "大语言模型", "LangChain", "RAG", "PyTorch", "Agent", "Docker"],
         "projects": ["RAG知识库系统", "智能客服Agent"],
         "skill_accuracy": 0.95, "project_match": 0.90},
        {"resume_title": "Java后端-李四", "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Docker", "微服务", "Kubernetes"],
         "projects": ["电商平台", "微服务网关"],
         "skill_accuracy": 0.90, "project_match": 0.85},
        {"resume_title": "数据分析师-王五", "skills": ["SQL", "Python", "Pandas", "数据分析", "Tableau"],
         "projects": ["用户画像平台", "BI报表系统"],
         "skill_accuracy": 0.85, "project_match": 0.80},
    ]


# ============================================================
# 5. Match Labels (人岗匹配标注)
# ============================================================
def build_match_labels():
    return [
        {"jd": "大模型应用开发工程师", "resume": "资深AI工程师-张三", "match_level": "high",
         "reason": "技能高度匹配：大语言模型、LangChain、RAG、PyTorch全覆盖，Agent为加分项"},
        {"jd": "RAG系统工程师", "resume": "资深AI工程师-张三", "match_level": "high",
         "reason": "RAG、向量数据库、LLM、Python完全匹配，项目经验直接相关"},
        {"jd": "AI Agent开发工程师", "resume": "资深AI工程师-张三", "match_level": "medium",
         "reason": "核心LLM/Python技能匹配，但Agent经验偏弱，缺少LangGraph/CrewAI"},
        {"jd": "后端开发工程师", "resume": "Java后端-李四", "match_level": "high",
         "reason": "Java、Spring Boot、MySQL、Redis完全匹配，微服务项目经验丰富"},
        {"jd": "云原生架构师", "resume": "Java后端-李四", "match_level": "medium",
         "reason": "K8s/Docker匹配，但缺少AWS/Terraform等云平台深度经验"},
        {"jd": "数据分析师", "resume": "数据分析师-王五", "match_level": "high",
         "reason": "SQL/Python/Pandas/Tableau完全匹配，项目直接相关"},
        {"jd": "计算机视觉工程师", "resume": "资深AI工程师-张三", "match_level": "low",
         "reason": "缺少计算机视觉核心技能(OpenCV/YOLO)，AI经验集中在LLM而非CV方向"},
        {"jd": "后端开发工程师", "resume": "数据分析师-王五", "match_level": "low",
         "reason": "数据分析师缺少Java/Spring Boot后端开发核心技术栈"},
    ]


# ============================================================
# 6. 负样本
# ============================================================
def build_negative_samples():
    return [
        {"type": "skill_mismatch", "description": "前端工程师应聘AI算法岗",
         "resume_skills": ["React", "Vue", "JavaScript", "CSS3"],
         "jd_skills": ["Python", "PyTorch", "深度学习", "大语言模型"],
         "reason": "技能完全不匹配"},
        {"type": "level_mismatch", "description": "初级数据分析师应聘高级云架构师",
         "resume_skills": ["SQL", "Excel", "Tableau"],
         "jd_skills": ["Kubernetes", "AWS", "Terraform", "微服务"],
         "reason": "技能等级和方向都不匹配"},
        {"type": "fake_skills", "description": "简历包含不存在的技能",
         "skills": ["SuperAI", "超能力编程", "量子速读"],
         "reason": "技能名不在标准技能体系中"},
        {"type": "irrelevant_match", "description": "嵌入式工程师应聘前端开发",
         "resume_skills": ["C/C++", "Linux", "嵌入式开发", "ARM"],
         "jd_skills": ["React", "Vue", "TypeScript", "JavaScript"],
         "reason": "岗位方向完全不同"},
        {"type": "empty_resume", "description": "空简历",
         "skills": [],
         "reason": "没有任何技能信息"},
    ]


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 55)
    print("  教育 + 证书 + 评估数据构建")
    print("=" * 55)

    ontology = load_ontology()
    print(f"技能本体: {len(ontology)} 标准技能")

    # 1. 课程
    courses = build_courses(ontology)
    course_path = os.path.join(BASE, "data", "education", "course_data.csv")
    with open(course_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["course_name","provider","difficulty","duration","skills","certificate","source_url","crawl_time"])
        w.writeheader(); w.writerows(courses)

    # 2. 证书
    certs = build_certificates(ontology)
    cert_path = os.path.join(BASE, "data", "education", "certificate_data.csv")
    with open(cert_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cert_name","issuer","level","related_skills","source_url","crawl_time"])
        w.writeheader(); w.writerows(certs)

    # 3-6. Meta评估数据
    meta_dir = os.path.join(BASE, "data", "meta")
    os.makedirs(meta_dir, exist_ok=True)

    gold_jd = build_gold_jd()
    with open(os.path.join(meta_dir, "gold_jd_set.json"), "w", encoding="utf-8") as f:
        json.dump(gold_jd, f, ensure_ascii=False, indent=2)

    gold_resume = build_gold_resume()
    with open(os.path.join(meta_dir, "gold_resume_set.json"), "w", encoding="utf-8") as f:
        json.dump(gold_resume, f, ensure_ascii=False, indent=2)

    match_labels = build_match_labels()
    with open(os.path.join(meta_dir, "match_label_set.json"), "w", encoding="utf-8") as f:
        json.dump(match_labels, f, ensure_ascii=False, indent=2)

    neg_samples = build_negative_samples()
    with open(os.path.join(meta_dir, "negative_samples.json"), "w", encoding="utf-8") as f:
        json.dump(neg_samples, f, ensure_ascii=False, indent=2)

    # 统计
    # 技能覆盖率
    all_skills = []
    for c in courses:
        all_skills.extend(c["skills"].split(";"))
    for c in certs:
        all_skills.extend(c["related_skills"].split(";"))
    mapped = sum(1 for s in all_skills if s and s in ontology)
    coverage = round(mapped / max(1, len([s for s in all_skills if s])) * 100, 1)

    print(f"\n课程数量: {len(courses)}")
    print(f"证书数量: {len(certs)}")
    print(f"评估样本数量: {len(gold_jd)} JDs + {len(gold_resume)} resumes")
    print(f"匹配对数量: {len(match_labels)}")
    print(f"负样本数量: {len(neg_samples)}")
    print(f"skill_standard 覆盖率: {coverage}%")
    print(f"\n输出:")
    print(f"  {course_path}")
    print(f"  {cert_path}")
    print(f"  {meta_dir}/gold_jd_set.json")
    print(f"  {meta_dir}/gold_resume_set.json")
    print(f"  {meta_dir}/match_label_set.json")
    print(f"  {meta_dir}/negative_samples.json")


if __name__ == "__main__":
    _block_deprecated_generator()
