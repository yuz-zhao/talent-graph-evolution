"""中英文岗位技能识别与标准化。

本模块是爬虫、清洗任务和全量重算脚本共用的唯一技能识别入口。
标准技能采用稳定的规范名称；英文缩写、产品旧称和中文同义词仅作为别名。
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable


# 规范名称 -> 可出现在岗位标题、职责或要求中的别名。
# 别名按“可被独立证明的技术/专业能力”收录，不收录 manager、agent、model 等普通词。
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    # 编程语言与基础
    "Python": ("python", "python3"),
    "Java": ("java", "jdk", "jvm"),
    "JavaScript": ("javascript", "ecmascript", "es6"),
    "TypeScript": ("typescript",),
    "Golang": ("golang", "go language", "go语言"),
    "Rust": ("rust language", "rust语言"),
    "C/C++": ("c/c++", "c++", "cpp", "cplusplus"),
    "C#": ("c#", "csharp"),
    "Kotlin": ("kotlin",), "Swift": ("swift",), "PHP": ("php",),
    "Ruby": ("ruby",), "Scala": ("scala",), "Shell": ("shell scripting", "shell脚本", "bash"),
    "SQL": ("sql",), "R语言": ("r language", "r语言"), "MATLAB": ("matlab",),
    "数据结构与算法": ("数据结构与算法", "data structures and algorithms", "algorithm design"),

    # Web、客户端与后端
    "HTML/CSS": ("html/css", "html5", "css3", "html", "css"),
    "React": ("react.js", "reactjs", "react"), "Vue.js": ("vue.js", "vuejs", "vue 2", "vue 3"),
    "Angular": ("angularjs", "angular"), "Next.js": ("next.js", "nextjs"),
    "Nuxt.js": ("nuxt.js", "nuxtjs"), "Svelte": ("svelte",),
    "Redux": ("redux",), "Webpack": ("webpack",), "Vite": ("vite",),
    "Node.js": ("node.js", "nodejs"), "Spring Boot": ("spring boot", "springboot"),
    "Spring Cloud": ("spring cloud", "springcloud"), "Spring": ("spring framework", "spring框架"),
    "Django": ("django",), "Flask": ("flask",), "FastAPI": ("fastapi",),
    ".NET": (".net core", "asp.net", "dotnet", ".net"),
    "MyBatis": ("mybatis",), "Hibernate": ("hibernate",), "Laravel": ("laravel",),
    "REST API": ("restful api", "rest api", "restful接口"), "GraphQL": ("graphql",),
    "gRPC": ("grpc",), "WebSocket": ("websocket", "web socket"),
    "微服务": ("微服务", "microservices", "microservice architecture"),
    "前端开发": ("前端开发", "frontend development", "front-end development", "frontend engineer", "front-end engineer"),
    "后端开发": ("后端开发", "backend development", "back-end development", "backend engineer", "back-end engineer"),
    "分布式系统": ("分布式系统", "distributed systems", "distributed system"),
    "系统设计": ("系统设计", "system design", "architecture design", "架构设计"),
    "软件工程": ("软件工程", "软件工程师", "软件开发工程师", "software engineering", "software engineer"),
    "自动驾驶": ("自动驾驶", "autonomous driving", "self-driving", "autonomous vehicle"),
    "Android": ("android", "安卓开发", "android开发"), "iOS": ("ios development", "ios开发"),
    "Flutter": ("flutter",), "React Native": ("react native",), "Electron": ("electron.js", "electronjs"),

    # 数据库、消息与搜索
    "MySQL": ("mysql",), "PostgreSQL": ("postgresql", "postgres"), "MongoDB": ("mongodb",),
    "Redis": ("redis",), "Elasticsearch": ("elasticsearch", "elastic search"),
    "Oracle": ("oracle database", "oracle数据库"), "SQL Server": ("sql server", "mssql"),
    "SQLite": ("sqlite",), "ClickHouse": ("clickhouse",), "Doris": ("apache doris",),
    "Neo4j": ("neo4j",), "Kafka": ("apache kafka", "kafka"), "RabbitMQ": ("rabbitmq",),
    "RocketMQ": ("rocketmq",), "Pulsar": ("apache pulsar",), "Nacos": ("nacos",),
    "ZooKeeper": ("zookeeper",), "向量数据库": ("向量数据库", "vector database", "vector db"),
    "Milvus": ("milvus",), "FAISS": ("faiss",), "Pinecone": ("pinecone vector", "pinecone db"),

    # 数据工程与分析
    "数据分析": ("数据分析", "data analysis", "data analytics"),
    "统计分析": ("统计分析", "statistical analysis", "statistical analytics"),
    "实时计算": ("实时计算", "real-time computing", "real time processing", "stream processing"),
    "数据挖掘": ("数据挖掘", "data mining"), "数据建模": ("数据建模", "data modeling", "data modelling"),
    "数据治理": ("数据治理", "data governance"), "数据质量": ("数据质量", "data quality"),
    "数据架构": ("数据架构", "data architecture", "data architect"),
    "数据仓库": ("数据仓库", "data warehouse", "data warehousing"),
    "数据湖": ("数据湖", "data lake", "lakehouse"), "ETL": ("etl", "extract transform load"),
    "商业智能": ("商业智能", "business intelligence", "power bi", "tableau", "bi开发", "bi工程师", "bi分析"),
    "Hadoop": ("hadoop",), "Spark": ("apache spark", "pyspark", "spark"),
    "Flink": ("apache flink", "flink"), "Hive": ("apache hive", "hive sql"),
    "Airflow": ("apache airflow", "airflow"), "dbt": ("dbt core", "dbt cloud"),
    "Pandas": ("pandas",), "NumPy": ("numpy",), "Excel": ("advanced excel", "excel高级", "excel函数"),

    # 人工智能
    "人工智能": ("人工智能", "artificial intelligence"),
    "机器学习": ("机器学习", "machine learning"), "深度学习": ("深度学习", "deep learning"),
    "自然语言处理": ("自然语言处理", "natural language processing"),
    "计算机视觉": ("计算机视觉", "computer vision", "图像识别", "image recognition"),
    "大语言模型": ("大语言模型", "大模型", "large language model", "large language models", "llms", "foundation model", "generative ai"),
    "检索增强生成": ("检索增强生成", "retrieval augmented generation", "retrieval-augmented generation"),
    "AI智能体": ("ai智能体", "ai agent", "ai agents", "autonomous agent", "agentic ai", "multi-agent system"),
    "知识图谱": ("知识图谱", "knowledge graph"), "推荐系统": ("推荐系统", "recommendation system", "recommender system"),
    "强化学习": ("强化学习", "reinforcement learning"), "迁移学习": ("迁移学习", "transfer learning"),
    "联邦学习": ("联邦学习", "federated learning"), "多模态学习": ("多模态", "multimodal learning", "multi-modal"),
    "提示词工程": ("提示词工程", "提示工程", "prompt engineering", "prompt engineer", "prompt工程师"),
    "模型微调": ("模型微调", "fine-tuning", "finetuning", "lora", "qlora"),
    "模型部署": ("模型部署", "model deployment", "model serving", "inference serving"),
    "MLOps": ("mlops",), "RLHF": ("rlhf",), "OCR": ("optical character recognition", "ocr识别"),
    "目标检测": ("目标检测", "object detection"), "语音识别": ("语音识别", "speech recognition", "asr system"),
    "PyTorch": ("pytorch",), "TensorFlow": ("tensorflow",), "Keras": ("keras",),
    "Scikit-learn": ("scikit-learn", "sklearn"), "Transformers": ("hugging face transformers", "huggingface transformers"),
    "LangChain": ("langchain",), "LlamaIndex": ("llamaindex",), "OpenCV": ("opencv",),
    "YOLO": ("yolo model", "yolov5", "yolov8", "yolov10", "yolov11"),
    "生成式AI": ("aigc", "生成式ai", "生成式人工智能"),

    # 游戏与实时图形岗位中可被原文直接证明的技术栈
    "Unreal Engine": ("unreal engine", "ue4", "ue5", "ue4/5"),
    "Unity": ("unity3d", "unity引擎", "unity"),
    "OpenGL": ("opengl",), "DirectX": ("directx", "dx11", "dx12"),
    "Vulkan": ("vulkan",), "Metal": ("metal图形", "metal api"),
    "Shader开发": ("shader开发", "shader编程", "shader"),
    "CDN": ("cdn架构", "cdn分发", "内容分发网络"),
    "数字版权管理": ("drm", "数字版权管理"),

    # 云、运维与工程效率
    "云计算": ("云计算", "cloud computing", "cloud infrastructure"),
    "AWS": ("amazon web services", "aws cloud"), "Azure": ("microsoft azure", "azure cloud"),
    "GCP": ("google cloud platform", "google cloud"), "阿里云": ("阿里云", "alibaba cloud"),
    "腾讯云": ("腾讯云", "tencent cloud"), "华为云": ("华为云", "huawei cloud"),
    "Docker": ("docker", "containerization"), "Kubernetes": ("kubernetes", "k8s"),
    "Linux": ("linux", "ubuntu", "centos", "red hat enterprise linux"), "Git": ("git version control", "git版本控制"),
    "GitHub Actions": ("github actions",), "GitLab CI": ("gitlab ci",), "Jenkins": ("jenkins",),
    "CI/CD": ("ci/cd", "continuous integration and delivery", "continuous integration/continuous delivery"),
    "Terraform": ("terraform",), "Ansible": ("ansible",), "Nginx": ("nginx",),
    "Prometheus": ("prometheus monitoring", "prometheus"), "Grafana": ("grafana",),
    "Helm": ("helm charts", "helm chart"), "Argo CD": ("argo cd", "argocd"),
    "DevOps": ("devops",), "SRE": ("site reliability engineering", "sre engineer"),
    "Serverless": ("serverless architecture", "serverless computing"),
    "Microsoft 365": ("microsoft 365", "office 365", "m365"),

    # 安全、测试与项目协作
    "网络安全": ("网络安全", "cybersecurity", "cyber security"),
    "信息安全": ("信息安全", "information security", "infosec"),
    "渗透测试": ("渗透测试", "penetration testing", "pentest"),
    "漏洞评估": ("漏洞评估", "vulnerability assessment", "vulnerability management"),
    "安全审计": ("安全审计", "security audit"), "身份与访问管理": ("identity and access management", "身份与访问管理"),
    "零信任": ("零信任", "zero trust"), "SIEM": ("siem platform", "siem system"),
    "软件测试": ("软件测试", "软件测试工程师", "测试工程师", "software testing", "quality assurance testing", "software test engineer"),
    "自动化测试": ("自动化测试", "test automation", "automated testing"),
    "单元测试": ("单元测试", "unit testing", "unit tests"), "接口测试": ("接口测试", "api testing"),
    "性能测试": ("性能测试", "performance testing", "load testing"),
    "Selenium": ("selenium webdriver", "selenium"), "Playwright": ("playwright testing", "playwright"),
    "Pytest": ("pytest",), "JUnit": ("junit",),
    "敏捷开发": ("敏捷开发", "agile development", "agile methodology"), "Scrum": ("scrum",),
    "Jira": ("atlassian jira", "jira"), "项目管理": ("项目管理", "project management"),

    # 嵌入式、工业与硬件
    "嵌入式开发": ("嵌入式开发", "嵌入式系统", "embedded systems", "embedded development"),
    "物联网": ("物联网", "internet of things"), "PLC": ("plc编程", "plc programming", "可编程逻辑控制器"),
    "单片机": ("单片机", "microcontroller", "mcu development"), "STM32": ("stm32",),
    "ARM": ("arm architecture", "arm cortex", "arm架构"), "FPGA": ("fpga",),
    "PCB设计": ("pcb设计", "pcb design", "printed circuit board design"),
    "RTOS": ("real-time operating system", "rtos"), "ROS": ("robot operating system", "ros2"),
    "CAN总线": ("can总线", "can bus"), "Modbus": ("modbus",), "MQTT": ("mqtt",),
    "自动化控制": ("自动化控制", "industrial automation", "automation control", "自动控制"),
    "机器人技术": ("机器人技术", "robotics", "robotic systems"), "工业机器人": ("工业机器人", "industrial robot"),
    "CNC": ("cnc加工", "cnc machining", "数控加工", "数控编程"),
    "SMT": ("smt工艺", "smt process", "表面贴装技术"), "硬件开发": ("硬件开发", "硬件工程师", "hardware development", "hardware design", "hardware engineer"),
    "电路设计": ("电路设计", "circuit design", "schematic design"),
    "数据标注": ("数据标注", "data annotation", "data labeling", "data labelling"),
    "电气控制": ("电气控制", "电控系统", "electrical control", "electrical controls"),
    "设备验证": ("设备验证", "equipment validation", "commissioning and qualification"),
    "系统调试": ("系统调试", "系统联调", "system commissioning", "system debugging"),
    "工艺设计": ("工艺设计", "工艺工程师", "process design", "process engineer"),
    "试验验证": ("试验工程师", "试验验证", "test and validation engineer", "validation testing"),
    "模具设计": ("模具设计", "塑胶模设计", "mold design", "mould design"),
    "制冷技术": ("制冷系统", "制冷技术", "refrigeration system", "refrigeration engineering"),

    # 新一代信息技术赛题重点领域
    "5G移动通信": ("5g通信", "5g网络", "5g移动通信", "5g nr", "5g core", "第五代移动通信"),
    "6G通信": ("6g通信", "6g网络", "第六代移动通信"),
    "通信网络": ("通信网络", "通信系统", "telecommunication network", "telecommunications network"),
    "无线通信": ("无线通信", "无线网络", "wireless communication", "radio access network", "ran网络"),
    "光通信": ("光通信", "光网络", "光传输", "optical communication", "optical network"),
    "TCP/IP": ("tcp/ip", "tcp ip"), "IPv6": ("ipv6",), "BGP": ("bgp协议", "border gateway protocol"),
    "OSPF": ("ospf协议", "open shortest path first"), "VLAN": ("vlan",), "QoS": ("qos", "quality of service"),
    "云网融合": ("云网融合", "cloud-network convergence", "cloud network convergence"),
    "算力网络": ("算力网络", "computing power network"), "数据中心": ("数据中心", "data center", "datacenter"),
    "边缘计算": ("边缘计算", "edge computing"), "工业互联网": ("工业互联网", "industrial internet"),
    "数字孪生": ("数字孪生", "digital twin"), "智能制造": ("智能制造", "smart manufacturing"),
    "隐私计算": ("隐私计算", "privacy-preserving computation", "privacy computing"),
    "数据空间": ("数据空间", "data space", "dataspace"),

    # 岗位能力而非具体框架，用于产品、架构、研究和技术服务类岗位
    "产品管理": ("产品管理", "产品经理", "product management", "product manager"),
    "需求分析": ("需求分析", "requirements analysis", "business requirement analysis"),
    "解决方案设计": ("解决方案设计", "方案设计", "solution design", "solutions architecture"),
    "技术咨询": ("技术咨询", "technical consulting", "technology consulting"),
    "技术支持": ("技术支持", "technical support", "support engineer"),
    "技术研究": ("技术研究", "产业研究", "前沿研究", "technology research", "research scientist"),
    "标准研究": ("标准研究", "标准制定", "标准编制", "standards research", "standardization"),
    "科研项目管理": ("科研项目管理", "课题管理", "research project management"),
    "系统运维": ("系统运维", "运维管理", "system operations", "it operations"),
}


# 短缩写只有在技术上下文中才识别，防止匹配普通英文单词。
CONTEXT_ALIASES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Golang": (("go",), ("developer", "engineer", "backend", "microservice", "programming", "开发", "工程师")),
    "Rust": (("rust",), ("developer", "engineer", "programming", "backend", "systems", "开发", "工程师")),
    "R语言": (("r",), ("statistics", "statistical", "analytics", "data science", "programming", "统计", "数据分析")),
    "人工智能": (("ai",), ("engineer", "工程师", "application", "应用", "algorithm", "machine learning", "model", "人工智能", "算法", "大模型")),
    "AI智能体": (("agent",), ("ai", "llm", "engineer", "工程师", "智能体", "agentic", "multi-agent")),
    "商业智能": (("bi",), ("developer", "engineer", "analyst", "analytics", "开发", "工程师", "分析", "报表")),
    "自然语言处理": (("nlp",), ("engineer", "model", "machine learning", "自然语言", "算法")),
    "计算机视觉": (("cv",), ("engineer", "computer vision", "image", "vision", "算法", "图像", "视觉")),
    "大语言模型": (("llm",), ("engineer", "model", "language", "大模型", "算法", "应用")),
    "检索增强生成": (("rag",), ("llm", "retrieval", "vector", "大模型", "检索", "知识库")),
    "OCR": (("ocr",), ("image", "document", "vision", "识别", "图像", "算法")),
    "AWS": (("aws",), ("cloud", "engineer", "devops", "infrastructure", "云", "运维", "架构")),
    "Azure": (("azure",), ("cloud", "engineer", "devops", "microsoft", "云", "运维")),
    "Git": (("git",), ("version control", "github", "gitlab", "代码", "版本控制")),
    "PLC": (("plc",), ("automation", "control", "electrical", "自动化", "控制", "电气", "生产操作")),
    "iOS": (("ios",), ("developer", "engineer", "mobile", "swift", "开发", "工程师")),
}

# Repair legacy GBK-as-Latin-1 strings at load time. The persisted ontology is
# rebuilt as clean UTF-8, while this compatibility layer keeps old callers safe.
def _repair_legacy_text(value: str) -> str:
    try:
        candidate=value.encode("latin1").decode("gbk")
        if sum('\u4e00'<=c<='\u9fff' for c in candidate)>sum('\u4e00'<=c<='\u9fff' for c in value): return candidate
    except (UnicodeEncodeError,UnicodeDecodeError): pass
    return value

SKILL_ALIASES={_repair_legacy_text(k):tuple(_repair_legacy_text(x) for x in v) for k,v in SKILL_ALIASES.items()}
CONTEXT_ALIASES={_repair_legacy_text(k):(tuple(_repair_legacy_text(x) for x in aliases),tuple(_repair_legacy_text(x) for x in contexts)) for k,(aliases,contexts) in CONTEXT_ALIASES.items()}


@dataclass(frozen=True)
class SkillMatch:
    raw: str
    standard: str
    start: int


def _boundary_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-/]*")
    left = r"(?<![A-Za-z0-9_])" if alias[:1].isascii() and alias[:1].isalnum() else ""
    right = r"(?![A-Za-z0-9_])" if alias[-1:].isascii() and alias[-1:].isalnum() else ""
    return re.compile(left + escaped + right, re.IGNORECASE)


@lru_cache(maxsize=1)
def _compiled_aliases() -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    rows: list[tuple[str, str, re.Pattern[str]]] = []
    for standard, aliases in SKILL_ALIASES.items():
        for alias in set((standard, *aliases)):
            if len(alias.strip()) >= 2:
                rows.append((standard, alias, _boundary_pattern(alias.strip())))
    ontology_path=Path(__file__).resolve().parents[1]/"data/gold/reference/skill_ontology.json"
    if ontology_path.exists():
        try:
            ontology=json.loads(ontology_path.read_text(encoding="utf-8"))
            for standard,info in ontology.items():
                if info.get("deprecated"):
                    continue
                for alias in (standard,*(info.get("aliases") or [])):
                    rule=(info.get("alias_rules") or {}).get(alias,{})
                    if len(alias.strip())>=2 and not rule.get("context_required"):
                        rows.append((standard,alias,_boundary_pattern(alias.strip())))
        except (OSError,json.JSONDecodeError):
            pass
    # 长词优先，避免 JavaScript 同时命中 Java。
    unique={(standard,alias.casefold()):(standard,alias,pattern) for standard,alias,pattern in rows}
    return tuple(sorted(unique.values(), key=lambda row: len(row[1]), reverse=True))


def extract_skill_matches(text: str) -> list[SkillMatch]:
    """抽取带原始证据、标准名称和位置的技能，结果按首次出现排序。"""
    source = str(text or "")
    if not source.strip():
        return []
    candidates: list[SkillMatch] = []
    for standard, _alias, pattern in _compiled_aliases():
        match = pattern.search(source)
        if match:
            candidates.append(SkillMatch(match.group(0), standard, match.start()))

    lowered = source.lower()
    for standard, (aliases, contexts) in CONTEXT_ALIASES.items():
        if any(context.lower() in lowered for context in contexts):
            for alias in aliases:
                match = _boundary_pattern(alias).search(source)
                if match:
                    candidates.append(SkillMatch(match.group(0), standard, match.start()))
                    break

    # 同一标准技能只保留最早证据；被长技能完全覆盖的父串不重复输出。
    best: dict[str, SkillMatch] = {}
    for item in sorted(candidates, key=lambda x: (x.start, -len(x.raw))):
        current = best.get(item.standard)
        if current is None or item.start < current.start:
            best[item.standard] = item
    return sorted(best.values(), key=lambda x: (x.start, x.standard.casefold()))


def extract_skills(text: str) -> list[str]:
    """兼容旧接口：返回实际命中的中英文原词，按出现顺序去重。"""
    return [item.raw for item in extract_skill_matches(text)]


def standardize_skills(skills: Iterable[str]) -> list[str]:
    """将任意技能别名转换为规范名称；未知词保留，保证兼容历史调用。"""
    result: list[str] = []
    seen: set[str] = set()
    alias_map = {
        alias.casefold(): standard
        for standard, aliases in SKILL_ALIASES.items()
        for alias in (standard, *aliases)
    }
    for skill in skills or []:
        value = str(skill).strip()
        if not value:
            continue
        standard = alias_map.get(value.casefold(), value)
        key = standard.casefold()
        if key not in seen:
            seen.add(key)
            result.append(standard)
    return result


def identify_skills(text: str) -> tuple[list[str], list[str]]:
    """一次完成原词抽取和标准化，供全量清洗任务使用。"""
    matches = extract_skill_matches(text)
    return [m.raw for m in matches], [m.standard for m in matches]
