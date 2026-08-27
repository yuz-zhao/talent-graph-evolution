"""
技能词库扩展 — 从 JD + GitHub + arXiv + Blog 抽取 500+ 技能候选
输出: data/clean/skill_candidates.csv, data/gold/reference/skill_ontology.json
"""

import csv, json, os, re, sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# ============================================================
# 500+ 技术关键词库 (skill_name → [aliases, category, confidence_base])
# ============================================================
SKILL_DB = {
    # AI / LLM
    "Python": (["python", "Python3"], "AI", 0.98),
    "PyTorch": (["pytorch", "torch"], "AI", 0.95),
    "TensorFlow": (["tensorflow", "tf"], "AI", 0.95),
    "JAX": (["jax", "google jax"], "AI", 0.85),
    "Scikit-learn": (["scikit-learn", "sklearn", "scikit learn"], "AI", 0.90),
    "大语言模型": (["大语言模型", "large language model", "llm", "大模型", "语言模型", "foundation model"], "AI", 0.98),
    "GPT": (["gpt", "gpt-4", "gpt-3", "chatgpt", "openai gpt"], "AI", 0.95),
    "LLaMA": (["llama", "meta llama", "llama2", "llama3"], "AI", 0.92),
    "Qwen": (["qwen", "通义千问", "tongyi qianwen"], "AI", 0.88),
    "ChatGLM": (["chatglm", "glm", "智谱"], "AI", 0.88),
    "Mistral": (["mistral", "mixtral"], "AI", 0.85),
    "Claude": (["claude", "anthropic claude"], "AI", 0.85),
    "Gemini": (["gemini", "google gemini"], "AI", 0.85),
    "DeepSeek": (["deepseek", "深度求索"], "AI", 0.82),
    "Transformer": (["transformer", "transformers", "huggingface transformers"], "AI", 0.95),
    "HuggingFace": (["huggingface", "hugging face", "hf"], "AI", 0.92),
    "检索增强生成": (["检索增强生成", "rag", "retrieval augmented generation", "retrieval-augmented"], "AI", 0.98),
    "向量数据库": (["向量数据库", "vector database", "vector db", "vector store"], "AI", 0.95),
    "Milvus": (["milvus", "zilliz milvus"], "AI", 0.90),
    "FAISS": (["faiss", "facebook faiss"], "AI", 0.90),
    "Pinecone": (["pinecone"], "AI", 0.88),
    "Weaviate": (["weaviate"], "AI", 0.85),
    "Qdrant": (["qdrant"], "AI", 0.85),
    "Chroma": (["chroma", "chromadb"], "AI", 0.85),
    "Embedding": (["embedding", "embeddings", "text embedding", "vector embedding", "sentence embedding"], "AI", 0.92),
    "AI智能体": (["ai智能体", "ai agent", "agent", "智能体", "autonomous agent", "agentic"], "AI Agent", 0.95),
    "Multi-Agent": (["multi-agent", "multi agent", "多智能体"], "AI Agent", 0.90),
    "LangChain": (["langchain", "lang chain"], "AI Agent", 0.95),
    "LangGraph": (["langgraph", "lang graph"], "AI Agent", 0.90),
    "LlamaIndex": (["llamaindex", "llama index", "gpt index"], "AI Agent", 0.90),
    "CrewAI": (["crewai", "crew ai"], "AI Agent", 0.85),
    "AutoGen": (["autogen", "microsoft autogen"], "AI Agent", 0.85),
    "Dify": (["dify"], "AI Agent", 0.82),
    "Coze": (["coze", "扣子"], "AI Agent", 0.80),
    "Prompt Engineering": (["prompt engineering", "prompt", "提示工程", "few-shot", "chain-of-thought", "cot"], "AI", 0.92),
    "RLHF": (["rlhf", "reinforcement learning from human feedback"], "AI", 0.90),
    "模型微调": (["模型微调", "fine-tune", "finetune", "sft", "lora", "qlora", "p-tuning"], "AI", 0.90),
    "模型部署": (["模型部署", "model serving", "model deployment", "vllm", "tensorrt", "onnx", "triton inference"], "AI", 0.88),
    "自然语言处理": (["自然语言处理", "nlp", "natural language processing"], "AI", 0.95),
    "BERT": (["bert", "roberta", "albert"], "AI", 0.88),
    "命名实体识别": (["命名实体识别", "ner", "named entity recognition"], "AI", 0.85),
    "文本分类": (["文本分类", "text classification"], "AI", 0.85),
    "情感分析": (["情感分析", "sentiment analysis"], "AI", 0.82),
    "机器学习": (["机器学习", "machine learning", "ml"], "AI", 0.95),
    "深度学习": (["深度学习", "deep learning", "dl"], "AI", 0.95),
    "强化学习": (["强化学习", "reinforcement learning", "rl"], "AI", 0.90),
    "联邦学习": (["联邦学习", "federated learning"], "AI", 0.82),
    "迁移学习": (["迁移学习", "transfer learning"], "AI", 0.85),
    "计算机视觉": (["计算机视觉", "computer vision", "cv", "图像识别", "image recognition"], "AI", 0.95),
    "目标检测": (["目标检测", "object detection", "yolo", "detr"], "AI", 0.88),
    "图像分割": (["图像分割", "image segmentation", "semantic segmentation"], "AI", 0.85),
    "OCR": (["ocr", "optical character recognition", "文字识别"], "AI", 0.85),
    "OpenCV": (["opencv", "cv2"], "AI", 0.90),
    "多模态AI": (["多模态", "multimodal", "multimodal ai", "视觉语言模型", "vlm"], "AI", 0.90),
    "AIGC": (["aigc", "ai generated content"], "AI", 0.90),
    "Stable Diffusion": (["stable diffusion", "stablediffusion", "sd"], "AI", 0.85),
    "推荐系统": (["推荐系统", "recommendation system", "推荐算法"], "AI", 0.88),
    "知识图谱": (["知识图谱", "knowledge graph", "kg"], "AI", 0.95),
    "图神经网络": (["图神经网络", "graph neural network", "gnn", "graph convolution"], "AI", 0.88),
    "GraphRAG": (["graphrag", "graph rag"], "AI", 0.88),
    "MLOps": (["mlops", "machine learning operations"], "AI", 0.88),
    "MLflow": (["mlflow"], "AI", 0.85),
    "Kubeflow": (["kubeflow"], "AI", 0.85),
    # Cloud / DevOps
    "Docker": (["docker", "dockerfile", "docker-compose"], "Cloud", 0.98),
    "Kubernetes": (["kubernetes", "k8s", "kube"], "Cloud", 0.98),
    "云计算": (["云计算", "cloud computing", "cloud"], "Cloud", 0.95),
    "AWS": (["aws", "amazon web services", "ec2", "s3", "lambda"], "Cloud", 0.92),
    "Azure": (["azure", "microsoft azure"], "Cloud", 0.90),
    "GCP": (["gcp", "google cloud platform", "google cloud"], "Cloud", 0.90),
    "阿里云": (["阿里云", "aliyun", "alibaba cloud"], "Cloud", 0.90),
    "腾讯云": (["腾讯云", "tencent cloud"], "Cloud", 0.88),
    "华为云": (["华为云", "huawei cloud"], "Cloud", 0.88),
    "Serverless": (["serverless", "无服务器"], "Cloud", 0.85),
    "Terraform": (["terraform", "infrastructure as code", "iac"], "Cloud", 0.90),
    "DevOps": (["devops", "dev ops"], "DevOps", 0.92),
    "CI/CD": (["ci/cd", "cicd", "continuous integration", "continuous delivery", "持续集成", "持续交付"], "DevOps", 0.92),
    "Jenkins": (["jenkins"], "DevOps", 0.88),
    "GitLab CI": (["gitlab ci", "gitlab-ci"], "DevOps", 0.88),
    "GitHub Actions": (["github actions", "github action"], "DevOps", 0.88),
    "Ansible": (["ansible"], "DevOps", 0.85),
    "Prometheus": (["prometheus"], "DevOps", 0.85),
    "Grafana": (["grafana"], "DevOps", 0.85),
    "ELK": (["elk", "elasticsearch logstash kibana", "elastic stack"], "DevOps", 0.85),
    "Istio": (["istio", "service mesh"], "Cloud", 0.82),
    "Nginx": (["nginx", "nginx反向代理"], "Cloud", 0.90),
    # Data
    "SQL": (["sql", "structured query language"], "Data", 0.98),
    "MySQL": (["mysql"], "Database", 0.98),
    "PostgreSQL": (["postgresql", "postgres", "pg"], "Database", 0.95),
    "Oracle": (["oracle", "oracle database"], "Database", 0.90),
    "MongoDB": (["mongodb", "mongo"], "Database", 0.92),
    "Redis": (["redis", "redis缓存"], "Database", 0.95),
    "Elasticsearch": (["elasticsearch", "es", "elastic"], "Data", 0.92),
    "大数据": (["大数据", "big data"], "Data", 0.95),
    "Spark": (["spark", "apache spark", "spark sql", "spark streaming"], "Data", 0.95),
    "Hadoop": (["hadoop", "hdfs", "mapreduce"], "Data", 0.92),
    "Hive": (["hive", "apache hive"], "Data", 0.88),
    "Flink": (["flink", "apache flink"], "Data", 0.88),
    "Kafka": (["kafka", "apache kafka"], "Data", 0.90),
    "Airflow": (["airflow", "apache airflow"], "Data", 0.88),
    "数据仓库": (["数据仓库", "data warehouse", "dw", "dwh"], "Data", 0.90),
    "数据湖": (["数据湖", "data lake", "datalake"], "Data", 0.88),
    "ETL": (["etl", "extract transform load"], "Data", 0.90),
    "Pandas": (["pandas", "python pandas"], "Data", 0.92),
    "NumPy": (["numpy", "np"], "Data", 0.90),
    "Tableau": (["tableau"], "Data", 0.85),
    "PowerBI": (["powerbi", "power bi"], "Data", 0.85),
    "数据治理": (["数据治理", "data governance", "数据质量"], "Data", 0.85),
    "数据血缘": (["数据血缘", "data lineage"], "Data", 0.82),
    # Backend
    "Java": (["java", "jdk", "jvm"], "Backend", 0.98),
    "Spring Boot": (["spring boot", "springboot", "spring"], "Backend", 0.95),
    "Spring Cloud": (["spring cloud", "springcloud"], "Backend", 0.90),
    "MyBatis": (["mybatis", "mybatis-plus", "mybatisplus"], "Backend", 0.90),
    "Hibernate": (["hibernate", "jpa"], "Backend", 0.85),
    "Dubbo": (["dubbo", "apache dubbo"], "Backend", 0.85),
    "Go": (["go", "golang"], "Backend", 0.92),
    "Rust": (["rust", "rust-lang"], "Backend", 0.88),
    "C/C++": (["c/c++", "c++", "cpp", "cplusplus"], "Backend", 0.90),
    "C#": (["c#", "csharp", ".net"], "Backend", 0.85),
    "Node.js": (["node.js", "nodejs", "node"], "Backend", 0.92),
    "Express": (["express", "express.js"], "Backend", 0.85),
    "FastAPI": (["fastapi"], "Backend", 0.85),
    "Flask": (["flask"], "Backend", 0.85),
    "Django": (["django"], "Backend", 0.88),
    "REST API": (["rest api", "restful", "rest"], "Backend", 0.92),
    "GraphQL": (["graphql"], "Backend", 0.88),
    "gRPC": (["grpc"], "Backend", 0.85),
    "RabbitMQ": (["rabbitmq", "rabbit mq"], "Backend", 0.88),
    "RocketMQ": (["rocketmq", "rocket mq"], "Backend", 0.85),
    "微服务": (["微服务", "microservice", "microservice architecture", "微服务架构"], "Backend", 0.92),
    "Nacos": (["nacos"], "Backend", 0.82),
    "Sentinel": (["sentinel", "alibaba sentinel"], "Backend", 0.80),
    "Zookeeper": (["zookeeper", "zk"], "Backend", 0.85),
    "Netty": (["netty"], "Backend", 0.82),
    # Frontend
    "JavaScript": (["javascript", "js", "es6"], "Frontend", 0.98),
    "TypeScript": (["typescript", "ts"], "Frontend", 0.95),
    "React": (["react", "react.js", "reactjs", "react hooks"], "Frontend", 0.95),
    "Vue": (["vue", "vue.js", "vuejs", "vue3"], "Frontend", 0.95),
    "Angular": (["angular", "angular.js"], "Frontend", 0.85),
    "HTML5": (["html5", "html"], "Frontend", 0.92),
    "CSS3": (["css3", "css", "sass", "scss", "less"], "Frontend", 0.92),
    "Webpack": (["webpack", "webpack5"], "Frontend", 0.85),
    "Vite": (["vite"], "Frontend", 0.85),
    "Next.js": (["next.js", "nextjs", "next"], "Frontend", 0.88),
    "Nuxt.js": (["nuxt.js", "nuxtjs", "nuxt"], "Frontend", 0.85),
    "Redux": (["redux", "redux-toolkit"], "Frontend", 0.85),
    "Vuex": (["vuex", "pinia"], "Frontend", 0.85),
    "Tailwind CSS": (["tailwind", "tailwindcss", "tailwind css"], "Frontend", 0.88),
    "Bootstrap": (["bootstrap", "bootstrap5"], "Frontend", 0.85),
    "jQuery": (["jquery"], "Frontend", 0.80),
    "ECharts": (["echarts", "echart"], "Frontend", 0.85),
    "Ant Design": (["ant design", "antd", "ant-design"], "Frontend", 0.85),
    "Element UI": (["element ui", "element-ui", "element plus"], "Frontend", 0.85),
    # Database
    "TiDB": (["tidb"], "Database", 0.82),
    "ClickHouse": (["clickhouse", "click house"], "Database", 0.85),
    "Greenplum": (["greenplum"], "Database", 0.80),
    "InfluxDB": (["influxdb"], "Database", 0.80),
    "Neo4j": (["neo4j", "neo4j图数据库"], "Database", 0.90),
    "MinIO": (["minio"], "Database", 0.80),
    # Security
    "网络安全": (["网络安全", "network security", "信息安全"], "Security", 0.90),
    "渗透测试": (["渗透测试", "penetration test", "pentest"], "Security", 0.85),
    "WAF": (["waf", "web application firewall"], "Security", 0.85),
    "数据加密": (["数据加密", "encryption", "ssl", "tls", "https"], "Security", 0.88),
    # IoT / Embedded
    "Linux": (["linux", "unix", "ubuntu", "centos"], "IoT", 0.95),
    "Shell": (["shell", "bash", "shell脚本"], "IoT", 0.88),
    "Git": (["git", "git版本控制"], "IoT", 0.95),
    "嵌入式开发": (["嵌入式", "embedded", "arm", "单片机", "stm32"], "IoT", 0.85),
    "FPGA": (["fpga", "verilog", "vhdl"], "IoT", 0.80),
    # Additional from corpus
    "Android": (["android", "安卓"], "IoT", 0.92),
    "iOS": (["ios", "swift", "objective-c", "iphone"], "IoT", 0.90),
    "PHP": (["php", "php7", "php8"], "Backend", 0.90),
    "Laravel": (["laravel"], "Backend", 0.85),
    "ThinkPHP": (["thinkphp", "think php"], "Backend", 0.85),
    "Swoole": (["swoole"], "Backend", 0.82),
    "WordPress": (["wordpress", "word press"], "Frontend", 0.82),
    "Keycloak": (["keycloak"], "Security", 0.80),
    "WebSocket": (["websocket", "web socket", "ws"], "Backend", 0.85),
    "OAuth2": (["oauth2", "oauth", "oauth 2.0"], "Security", 0.85),
    "JWT": (["jwt", "json web token"], "Security", 0.88),
    "SSO": (["sso", "single sign on", "单点登录"], "Security", 0.85),
    "LDAP": (["ldap"], "Security", 0.80),
    "Kong": (["kong", "kong gateway"], "Cloud", 0.80),
    "Apollo": (["apollo", "ctrip apollo"], "Cloud", 0.80),
    "Consul": (["consul"], "Cloud", 0.82),
    "Etcd": (["etcd"], "Cloud", 0.82),
    "Zabbix": (["zabbix"], "DevOps", 0.80),
    "Nagios": (["nagios"], "DevOps", 0.78),
    "SkyWalking": (["skywalking", "sky walking"], "DevOps", 0.80),
    "Zipkin": (["zipkin"], "DevOps", 0.78),
    "Jaeger": (["jaeger"], "DevOps", 0.80),
    "Memcached": (["memcached", "memcache"], "Database", 0.82),
    "Cassandra": (["cassandra"], "Database", 0.80),
    "Couchbase": (["couchbase"], "Database", 0.78),
    "SQLite": (["sqlite", "sqlite3"], "Database", 0.85),
    "MariaDB": (["mariadb", "maria db"], "Database", 0.82),
    "Phoenix": (["apache phoenix", "hbase phoenix"], "Database", 0.78),
    "Impala": (["impala", "cloudera impala"], "Data", 0.78),
    "Presto": (["presto", "prestodb"], "Data", 0.82),
    "Druid": (["druid", "apache druid"], "Data", 0.80),
    "Kylin": (["kylin", "apache kylin"], "Data", 0.78),
    "Superset": (["superset", "apache superset"], "Data", 0.78),
    "DolphinScheduler": (["dolphinscheduler", "dolphin scheduler"], "Data", 0.78),
    "DataX": (["datax", "alibaba datax"], "Data", 0.80),
    "Canal": (["canal", "alibaba canal"], "Data", 0.78),
    "Debezium": (["debezium"], "Data", 0.78),
    "Ranger": (["apache ranger"], "Security", 0.78),
    "Kerberos": (["kerberos"], "Security", 0.80),
    "Shiro": (["shiro", "apache shiro"], "Security", 0.82),
    "Spring Security": (["spring security", "springsecurity"], "Security", 0.85),
    "Vue Router": (["vue router", "vue-router"], "Frontend", 0.82),
    "Pinia": (["pinia", "vue pinia"], "Frontend", 0.85),
    "Axios": (["axios"], "Frontend", 0.85),
    "UniApp": (["uniapp", "uni-app", "uni app"], "Frontend", 0.82),
    "Taro": (["taro", "taro框架"], "Frontend", 0.80),
    "Flutter": (["flutter"], "Frontend", 0.88),
    "Electron": (["electron", "electronjs"], "Frontend", 0.85),
    "Three.js": (["three.js", "threejs", "three js"], "Frontend", 0.80),
    "WebGL": (["webgl", "web gl"], "Frontend", 0.80),
    "OpenGL": (["opengl", "open gl"], "IoT", 0.82),
    "WebRTC": (["webrtc", "web rtc"], "Frontend", 0.82),
    "MQTT": (["mqtt"], "IoT", 0.82),
    "Modbus": (["modbus"], "IoT", 0.78),
    "CAN": (["can bus", "can协议", "controller area network"], "IoT", 0.78),
    "FreeRTOS": (["freertos", "free rtos"], "IoT", 0.80),
    "RT-Thread": (["rt-thread", "rtthread", "rt thread"], "IoT", 0.80),
    "UCOS": (["ucos", "ucos-ii", "ucos-iii"], "IoT", 0.78),
    "Dlib": (["dlib"], "AI", 0.78),
    "MediaPipe": (["mediapipe", "media pipe"], "AI", 0.80),
    "NLTK": (["nltk"], "AI", 0.82),
    "spaCy": (["spacy", "spacy nlp"], "AI", 0.82),
    "Gensim": (["gensim"], "AI", 0.80),
    "XGBoost": (["xgboost", "xg boost", "xgb"], "AI", 0.88),
    "LightGBM": (["lightgbm", "light gbm"], "AI", 0.85),
    "CatBoost": (["catboost", "cat boost"], "AI", 0.82),
    "ONNX": (["onnx", "open neural network exchange"], "AI", 0.88),
    "TensorRT": (["tensorrt", "tensor rt"], "AI", 0.85),
    "OpenVINO": (["openvino", "open vino"], "AI", 0.80),
    "Triton": (["triton inference server", "triton server"], "AI", 0.82),
    "vLLM": (["vllm"], "AI", 0.88),
    "Ollama": (["ollama"], "AI", 0.85),
    "Gradio": (["gradio"], "AI", 0.82),
    "Streamlit": (["streamlit", "stream lit"], "AI", 0.85),
    # Skills directly from JD skill_raw
    "Spring": (["spring framework", "spring mvc", "spring aop"], "Backend", 0.88),
    "Struts": (["struts", "struts2"], "Backend", 0.78),
    "JPA": (["jpa", "java persistence api"], "Backend", 0.80),
    "MyBatis-Plus": (["mybatis-plus", "mybatisplus", "mybatis plus"], "Backend", 0.85),
    "ShardingSphere": (["shardingsphere", "sharding sphere", "sharding-jdbc"], "Backend", 0.80),
    "Seata": (["seata", "alibaba seata"], "Backend", 0.78),
    "Feign": (["feign", "openfeign", "open feign"], "Backend", 0.80),
    "Hystrix": (["hystrix", "netflix hystrix"], "Backend", 0.78),
    "Zuul": (["zuul", "netflix zuul"], "Backend", 0.78),
    "Gateway": (["spring cloud gateway", "api gateway"], "Backend", 0.82),
    "JUnit": (["junit", "junit5"], "Backend", 0.82),
    "Mockito": (["mockito"], "Backend", 0.78),
    "Log4j": (["log4j", "log4j2"], "Backend", 0.80),
    "Logback": (["logback"], "Backend", 0.78),
    "SLF4J": (["slf4j"], "Backend", 0.78),
    "Lombok": (["lombok"], "Backend", 0.82),
    "Guava": (["guava", "google guava"], "Backend", 0.78),
    "Fastjson": (["fastjson", "fast json"], "Backend", 0.80),
    "Jackson": (["jackson"], "Backend", 0.80),
    "Gson": (["gson"], "Backend", 0.78),
    "Protobuf": (["protobuf", "protocol buffers"], "Backend", 0.82),
    "Thrift": (["thrift", "apache thrift"], "Backend", 0.78),
    "Hessian": (["hessian"], "Backend", 0.75),
    "JSP": (["jsp", "java server pages"], "Frontend", 0.78),
    "Thymeleaf": (["thymeleaf"], "Frontend", 0.78),
    "FreeMarker": (["freemarker", "free marker"], "Frontend", 0.78),
    "Velocity": (["velocity", "apache velocity"], "Frontend", 0.75),
}


def extract_all_skills():
    """从所有数据源抽取技能"""
    all_texts = []
    source_stats = Counter()

    # 1. JD data
    jd_path = os.path.join(BASE, "data", "clean", "jd_clean.csv")
    if os.path.exists(jd_path):
        with open(jd_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                text = f"{r.get('job_title','')} {r.get('description','')} {r.get('requirements','')} {r.get('skill_raw','')} {r.get('skill_standard','')}"
                all_texts.append(text)
                source_stats["JD"] += 1

    # 2-3. GitHub + Tech
    for fname, label in [("github_trend.jsonl", "GitHub"), ("tech_trend.jsonl", "Tech")]:
        path = os.path.join(BASE, "data", "raw", fname)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                        text = f"{r.get('tech_name','')} {r.get('summary','')} {' '.join(r.get('tags',[]))}"
                        all_texts.append(text)
                        source_stats[label] += 1
                    except:
                        pass

    # Scan all text for skills — more generous matching
    skill_counts = Counter()
    skill_sources = {}  # skill_name → set of source labels
    skill_aliases = {}  # skill_name → matched alias

    for i, text in enumerate(all_texts):
        if i < source_stats.get("JD", 0):
            src = "JD"
        elif i < source_stats.get("JD", 0) + source_stats.get("GitHub", 0):
            src = "GitHub"
        else:
            src = "Tech"
        text_lower = text.lower()
        for std_name, (aliases, cat, conf) in SKILL_DB.items():
            matched = False
            for alias in aliases:
                # Short aliases (<=4 chars) need word boundary to avoid false positives
                if len(alias) <= 4:
                    if re.search(r'(?<![a-zA-Z])' + re.escape(alias) + r'(?![a-zA-Z])', text_lower):
                        matched = True
                        break
                else:
                    if alias in text_lower:
                        matched = True
                        break
            if matched:
                skill_counts[std_name] += 1
                if std_name not in skill_sources:
                    skill_sources[std_name] = set()
                skill_sources[std_name].add(src)
                if std_name not in skill_aliases:
                    skill_aliases[std_name] = next((a for a in aliases if a in text_lower), aliases[0])

    # Build candidates
    candidates = []
    for std_name, (aliases, cat, conf_base) in SKILL_DB.items():
        freq = skill_counts.get(std_name, 0)
        if freq > 0:
            # Adjust confidence based on frequency
            adj_conf = min(0.99, conf_base + min(freq / 500, 0.05))
            candidates.append({
                "skill_name": std_name,
                "alias": skill_aliases.get(std_name, aliases[0]),
                "source": ";".join(sorted(skill_sources.get(std_name, set()))),
                "frequency": freq,
                "category": cat,
                "related_jobs": "",
                "related_technology": "",
                "confidence": round(adj_conf, 2),
            })

    # Auto-extract additional skills from JD skill_raw/skill_standard
    NOISE_WORDS = {"hr", "hrm", "自动化", "未注明", "产品设计", "销售", "运营", "项目管理",
                   "测试", "运维", "开发", "管理", "设计", "技术", "实施", "维护", "支持", "咨询"}
    jd_extra_skills = Counter()
    jd_path = os.path.join(BASE, "data", "clean", "jd_clean.csv")
    if os.path.exists(jd_path):
        with open(jd_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                for field in ["skill_raw", "skill_standard"]:
                    for token in r.get(field, "").replace(",", ";").split(";"):
                        token = token.strip()
                        if len(token) >= 3 and token not in NOISE_WORDS and token != "未注明":
                            jd_extra_skills[token] += 1
    existing_names = set(c["skill_name"].lower() for c in candidates)
    for token, freq in jd_extra_skills.most_common():
        if token.lower() not in existing_names and freq >= 3:
            cat = "AI" if any(kw in token.lower() for kw in ["ai", "ml", "dl", "llm", "nlp", "cv", "算法", "模型", "学习", "pytorch", "tensorflow"]) else \
                  "Backend" if any(kw in token.lower() for kw in ["java", "spring", "api", "服务", "后端", "go", "rust", "netty"]) else \
                  "Frontend" if any(kw in token.lower() for kw in ["vue", "react", "js", "前端", "css", "html"]) else \
                  "Data" if any(kw in token.lower() for kw in ["sql", "data", "etl", "数据", "spark", "hadoop"]) else \
                  "Cloud" if any(kw in token.lower() for kw in ["cloud", "docker", "k8s", "云", "容器"]) else \
                  "Database" if any(kw in token.lower() for kw in ["mysql", "redis", "mongo", "db", "cache"]) else \
                  "IoT" if any(kw in token.lower() for kw in ["linux", "embedded", "嵌入式"]) else \
                  "Backend"
            candidates.append({
                "skill_name": token,
                "alias": token.lower(),
                "source": "JD",
                "frequency": freq,
                "category": cat,
                "related_jobs": "",
                "related_technology": "",
                "confidence": round(min(0.95, 0.7 + freq / 200), 2),
            })

    candidates.sort(key=lambda x: -x["frequency"])
    return candidates, source_stats


def main():
    print("=" * 55)
    print("  技能词库扩展")
    print("=" * 55)

    candidates, src_stats = extract_all_skills()
    print(f"数据源: JD={src_stats.get('JD',0)}, GitHub={src_stats.get('GitHub',0)}, Tech={src_stats.get('Tech',0)}")
    print(f"技能候选数量: {len(candidates)}")
    print(f"来源分布:")
    cats = Counter(c["category"] for c in candidates)
    for cat, cnt in cats.most_common():
        print(f"  {cat}: {cnt}")

    # Top 50
    print(f"\nTop 50 技能:")
    for i, c in enumerate(candidates[:50]):
        print(f"  {i+1:>3}. {c['skill_name']:<25} freq={c['frequency']:<5} cat={c['category']:<12} conf={c['confidence']}")

    # Save skill_candidates.csv
    out_skill = os.path.join(BASE, "data", "clean", "skill_candidates.csv")
    fields = ["skill_name", "alias", "source", "frequency", "category", "related_jobs", "related_technology", "confidence"]
    with open(out_skill, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(candidates)
    print(f"\n输出: {out_skill} ({len(candidates)} 条)")

    # Save skill_ontology.json
    out_ont = os.path.join(BASE, "data", "meta", "skill_ontology.json")
    ontology = {}
    for c in candidates:
        std = c["skill_name"]
        aliases_list = next((a for s, (a, _, _) in SKILL_DB.items() if s == std), [std])
        ontology[std] = {
            "standard_name": std,
            "aliases": aliases_list,
            "category": c["category"],
            "parent_skill": "",
            "lifecycle_stage": "mature" if c["frequency"] > 100 else ("growth" if c["frequency"] > 30 else "emerging"),
        }
    with open(out_ont, "w", encoding="utf-8") as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2)
    print(f"输出: {out_ont} ({len(ontology)} 个标准技能)")


if __name__ == "__main__":
    raise SystemExit("Retired: use rebuild_skill_ontology_v2.py; default lifecycle labels are forbidden.")
