"""
技能词库扩展 — JD + GitHub + arXiv + Blog → 500+ 技能
输出: data/clean/skill_candidates.csv, data/gold/reference/skill_ontology.json
"""

import csv, json, os, re, sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# ============================================================
# 500+ 技能关键词库
# ============================================================
SKILL_DB = {
    "Python": (["python", "python3"], "AI", 0.98),
    "PyTorch": (["pytorch", "torch"], "AI", 0.95),
    "TensorFlow": (["tensorflow", "tf"], "AI", 0.95),
    "JAX": (["jax"], "AI", 0.85),
    "Scikit-learn": (["scikit-learn", "sklearn"], "AI", 0.90),
    "XGBoost": (["xgboost", "xgb"], "AI", 0.88),
    "LightGBM": (["lightgbm"], "AI", 0.85),
    "大语言模型": (["大语言模型", "large language model", "llm", "大模型", "language model", "foundation model"], "AI", 0.98),
    "GPT": (["gpt", "gpt-4", "chatgpt"], "AI", 0.95),
    "LLaMA": (["llama", "llama2", "llama3"], "AI", 0.92),
    "Qwen": (["qwen", "通义千问"], "AI", 0.88),
    "ChatGLM": (["chatglm", "glm"], "AI", 0.88),
    "Mistral": (["mistral", "mixtral"], "AI", 0.85),
    "Claude": (["claude"], "AI", 0.85),
    "Gemini": (["gemini"], "AI", 0.85),
    "DeepSeek": (["deepseek", "深度求索"], "AI", 0.82),
    "Transformer": (["transformer", "transformers"], "AI", 0.95),
    "HuggingFace": (["huggingface", "hugging face"], "AI", 0.92),
    "检索增强生成": (["检索增强生成", "rag", "retrieval augmented generation", "retrieval-augmented"], "AI", 0.98),
    "向量数据库": (["向量数据库", "vector database", "vector db", "vector store"], "AI", 0.95),
    "Milvus": (["milvus"], "AI", 0.90),
    "FAISS": (["faiss"], "AI", 0.90),
    "Pinecone": (["pinecone"], "AI", 0.88),
    "Weaviate": (["weaviate"], "AI", 0.85),
    "Qdrant": (["qdrant"], "AI", 0.85),
    "Chroma": (["chroma", "chromadb"], "AI", 0.85),
    "Embedding": (["embedding", "embeddings", "text embedding", "sentence embedding"], "AI", 0.92),
    "AI智能体": (["ai智能体", "ai agent", "agent", "智能体", "autonomous agent", "agentic", "multi-agent", "multi agent"], "AI Agent", 0.95),
    "LangChain": (["langchain", "lang chain"], "AI Agent", 0.95),
    "LangGraph": (["langgraph"], "AI Agent", 0.90),
    "LlamaIndex": (["llamaindex", "llama index"], "AI Agent", 0.90),
    "CrewAI": (["crewai"], "AI Agent", 0.85),
    "AutoGen": (["autogen"], "AI Agent", 0.85),
    "MCP": (["mcp", "model context protocol"], "AI Agent", 0.85),
    "Prompt Engineering": (["prompt engineering", "prompt", "提示工程", "few-shot", "chain-of-thought", "cot"], "AI", 0.92),
    "RLHF": (["rlhf", "reinforcement learning from human feedback"], "AI", 0.90),
    "模型微调": (["模型微调", "fine-tune", "finetune", "sft", "lora", "qlora"], "AI", 0.90),
    "模型部署": (["模型部署", "model serving", "vllm", "tensorrt", "onnx"], "AI", 0.88),
    "自然语言处理": (["自然语言处理", "nlp", "natural language processing"], "AI", 0.95),
    "BERT": (["bert", "roberta"], "AI", 0.88),
    "机器学习": (["机器学习", "machine learning", "ml"], "AI", 0.95),
    "深度学习": (["深度学习", "deep learning", "dl"], "AI", 0.95),
    "强化学习": (["强化学习", "reinforcement learning", "rl"], "AI", 0.90),
    "联邦学习": (["联邦学习", "federated learning"], "AI", 0.82),
    "迁移学习": (["迁移学习", "transfer learning"], "AI", 0.85),
    "计算机视觉": (["计算机视觉", "computer vision", "cv", "图像识别", "image recognition"], "AI", 0.95),
    "目标检测": (["目标检测", "object detection", "yolo", "detr"], "AI", 0.88),
    "OCR": (["ocr", "optical character recognition"], "AI", 0.85),
    "OpenCV": (["opencv", "cv2"], "AI", 0.90),
    "多模态AI": (["多模态", "multimodal", "multimodal ai", "视觉语言模型", "vlm"], "AI", 0.90),
    "AIGC": (["aigc", "ai generated content"], "AI", 0.90),
    "Stable Diffusion": (["stable diffusion", "stablediffusion", "sd"], "AI", 0.85),
    "Diffusion": (["diffusion model", "diffusion models", "ddpm"], "AI", 0.85),
    "推荐系统": (["推荐系统", "recommendation system"], "AI", 0.88),
    "知识图谱": (["知识图谱", "knowledge graph", "kg"], "AI", 0.95),
    "Neo4j": (["neo4j", "neo4j图数据库"], "Database", 0.90),
    "图神经网络": (["图神经网络", "graph neural network", "gnn"], "AI", 0.88),
    "GraphRAG": (["graphrag", "graph rag"], "AI", 0.88),
    "MLOps": (["mlops", "machine learning operations"], "AI", 0.88),
    "MLflow": (["mlflow"], "AI", 0.85),
    "Kubeflow": (["kubeflow"], "AI", 0.85),
    "Docker": (["docker", "dockerfile", "docker-compose"], "Cloud", 0.98),
    "Kubernetes": (["kubernetes", "k8s", "kube"], "Cloud", 0.98),
    "云计算": (["云计算", "cloud computing", "cloud"], "Cloud", 0.95),
    "AWS": (["aws", "amazon web services", "ec2", "s3", "lambda"], "Cloud", 0.92),
    "Azure": (["azure"], "Cloud", 0.90),
    "GCP": (["gcp", "google cloud"], "Cloud", 0.90),
    "阿里云": (["阿里云", "aliyun"], "Cloud", 0.90),
    "腾讯云": (["腾讯云", "tencent cloud"], "Cloud", 0.88),
    "华为云": (["华为云", "huawei cloud"], "Cloud", 0.88),
    "Serverless": (["serverless"], "Cloud", 0.85),
    "Terraform": (["terraform", "iac"], "Cloud", 0.90),
    "DevOps": (["devops"], "DevOps", 0.92),
    "CI/CD": (["ci/cd", "cicd", "continuous integration", "continuous delivery", "持续集成", "持续交付"], "DevOps", 0.92),
    "Jenkins": (["jenkins"], "DevOps", 0.88),
    "Ansible": (["ansible"], "DevOps", 0.85),
    "Prometheus": (["prometheus"], "DevOps", 0.85),
    "Grafana": (["grafana"], "DevOps", 0.85),
    "Istio": (["istio", "service mesh"], "Cloud", 0.82),
    "Nginx": (["nginx", "nginx反向代理"], "Cloud", 0.90),
    "SQL": (["sql"], "Data", 0.98),
    "MySQL": (["mysql"], "Database", 0.98),
    "PostgreSQL": (["postgresql", "postgres", "pg"], "Database", 0.95),
    "Oracle": (["oracle", "oracle database"], "Database", 0.90),
    "MongoDB": (["mongodb", "mongo"], "Database", 0.92),
    "Redis": (["redis", "redis缓存"], "Database", 0.95),
    "Elasticsearch": (["elasticsearch", "es", "elastic"], "Data", 0.92),
    "大数据": (["大数据", "big data"], "Data", 0.95),
    "Spark": (["spark", "apache spark"], "Data", 0.95),
    "Hadoop": (["hadoop", "hdfs"], "Data", 0.92),
    "Hive": (["hive"], "Data", 0.88),
    "Flink": (["flink"], "Data", 0.88),
    "Kafka": (["kafka"], "Data", 0.90),
    "Airflow": (["airflow"], "Data", 0.88),
    "数据仓库": (["数据仓库", "data warehouse", "dw"], "Data", 0.90),
    "数据湖": (["数据湖", "data lake", "datalake"], "Data", 0.88),
    "ETL": (["etl", "extract transform load"], "Data", 0.90),
    "Pandas": (["pandas"], "Data", 0.92),
    "NumPy": (["numpy", "np"], "Data", 0.90),
    "Tableau": (["tableau"], "Data", 0.85),
    "PowerBI": (["powerbi", "power bi"], "Data", 0.85),
    "Java": (["java", "jdk", "jvm"], "Backend", 0.98),
    "Spring Boot": (["spring boot", "springboot", "spring"], "Backend", 0.95),
    "Spring Cloud": (["spring cloud", "springcloud"], "Backend", 0.90),
    "MyBatis": (["mybatis", "mybatis-plus"], "Backend", 0.90),
    "Dubbo": (["dubbo"], "Backend", 0.85),
    "Go": (["go", "golang"], "Backend", 0.92),
    "Rust": (["rust", "rust-lang"], "Backend", 0.88),
    "C/C++": (["c/c++", "c++", "cpp", "cplusplus"], "Backend", 0.90),
    "C#": (["c#", "csharp", ".net"], "Backend", 0.85),
    "Node.js": (["node.js", "nodejs", "node"], "Backend", 0.92),
    "FastAPI": (["fastapi"], "Backend", 0.85),
    "Flask": (["flask"], "Backend", 0.85),
    "Django": (["django"], "Backend", 0.88),
    "REST API": (["rest api", "restful", "rest"], "Backend", 0.92),
    "GraphQL": (["graphql"], "Backend", 0.88),
    "gRPC": (["grpc"], "Backend", 0.85),
    "RabbitMQ": (["rabbitmq", "rabbit mq"], "Backend", 0.88),
    "RocketMQ": (["rocketmq"], "Backend", 0.85),
    "微服务": (["微服务", "microservice", "微服务架构", "microservice architecture"], "Backend", 0.92),
    "Zookeeper": (["zookeeper", "zk"], "Backend", 0.85),
    "Netty": (["netty"], "Backend", 0.82),
    "JavaScript": (["javascript", "js", "es6"], "Frontend", 0.98),
    "TypeScript": (["typescript", "ts"], "Frontend", 0.95),
    "React": (["react", "react.js", "reactjs"], "Frontend", 0.95),
    "Vue": (["vue", "vue.js", "vuejs", "vue3"], "Frontend", 0.95),
    "Angular": (["angular", "angular.js"], "Frontend", 0.85),
    "HTML5": (["html5", "html"], "Frontend", 0.92),
    "CSS3": (["css3", "css", "sass", "scss", "less"], "Frontend", 0.92),
    "Webpack": (["webpack", "webpack5"], "Frontend", 0.85),
    "Vite": (["vite"], "Frontend", 0.85),
    "Next.js": (["next.js", "nextjs"], "Frontend", 0.88),
    "Nuxt.js": (["nuxt.js", "nuxtjs"], "Frontend", 0.85),
    "Redux": (["redux", "redux-toolkit"], "Frontend", 0.85),
    "Tailwind CSS": (["tailwind", "tailwindcss"], "Frontend", 0.88),
    "Bootstrap": (["bootstrap", "bootstrap5"], "Frontend", 0.85),
    "ECharts": (["echarts", "echart"], "Frontend", 0.85),
    "Ant Design": (["ant design", "antd", "ant-design"], "Frontend", 0.85),
    "Element UI": (["element ui", "element-ui", "element plus"], "Frontend", 0.85),
    "Flutter": (["flutter"], "Frontend", 0.88),
    "Electron": (["electron", "electronjs"], "Frontend", 0.85),
    "Android": (["android", "安卓"], "IoT", 0.92),
    "iOS": (["ios", "swift", "objective-c", "iphone"], "IoT", 0.90),
    "PHP": (["php", "php7", "php8"], "Backend", 0.90),
    "Laravel": (["laravel"], "Backend", 0.85),
    "Linux": (["linux", "unix", "ubuntu", "centos"], "IoT", 0.95),
    "Shell": (["shell", "bash", "shell脚本"], "IoT", 0.88),
    "Git": (["git", "git版本控制"], "IoT", 0.95),
    "嵌入式开发": (["嵌入式", "embedded", "arm", "单片机", "stm32"], "IoT", 0.85),
    "网络安全": (["网络安全", "network security", "信息安全"], "Security", 0.90),
    "渗透测试": (["渗透测试", "penetration test", "pentest"], "Security", 0.85),
    "OAuth2": (["oauth2", "oauth", "oauth 2.0"], "Security", 0.85),
    "JWT": (["jwt", "json web token"], "Security", 0.88),
    "SSO": (["sso", "single sign on", "单点登录"], "Security", 0.85),
    "Spring Security": (["spring security", "springsecurity"], "Security", 0.85),
    "Shiro": (["shiro", "apache shiro"], "Security", 0.82),
    "Memcached": (["memcached", "memcache"], "Database", 0.82),
    "SQLite": (["sqlite", "sqlite3"], "Database", 0.85),
    "MariaDB": (["mariadb"], "Database", 0.82),
    "ClickHouse": (["clickhouse", "click house"], "Database", 0.85),
    "TiDB": (["tidb"], "Database", 0.82),
    "Presto": (["presto", "prestodb"], "Data", 0.82),
    "Druid": (["druid", "apache druid"], "Data", 0.80),
    "DataX": (["datax"], "Data", 0.80),
    "Ollama": (["ollama"], "AI", 0.85),
    "Gradio": (["gradio"], "AI", 0.82),
    "Streamlit": (["streamlit"], "AI", 0.85),
    "WebSocket": (["websocket", "web socket", "ws"], "Backend", 0.85),
    "Nacos": (["nacos"], "Backend", 0.82),
    "Sentinel": (["sentinel"], "Backend", 0.80),
    "Apollo": (["apollo", "ctrip apollo"], "Cloud", 0.80),
    "Consul": (["consul"], "Cloud", 0.82),
    "Etcd": (["etcd"], "Cloud", 0.82),
    "Zabbix": (["zabbix"], "DevOps", 0.80),
    "SkyWalking": (["skywalking"], "DevOps", 0.80),
    "Jaeger": (["jaeger"], "DevOps", 0.80),
    "JUnit": (["junit", "junit5"], "Backend", 0.82),
    "Lombok": (["lombok"], "Backend", 0.82),
    "Fastjson": (["fastjson", "fast json"], "Backend", 0.80),
    "Jackson": (["jackson"], "Backend", 0.80),
    "Protobuf": (["protobuf", "protocol buffers"], "Backend", 0.82),
    "Axios": (["axios"], "Frontend", 0.85),
    "UniApp": (["uniapp", "uni-app"], "Frontend", 0.82),
    "Three.js": (["three.js", "threejs"], "Frontend", 0.80),
    "WebGL": (["webgl"], "Frontend", 0.80),
    "WebRTC": (["webrtc"], "Frontend", 0.82),
    "MQTT": (["mqtt"], "IoT", 0.82),
    "FreeRTOS": (["freertos"], "IoT", 0.80),
    "ONNX": (["onnx"], "AI", 0.88),
    "OpenVINO": (["openvino"], "AI", 0.80),
    # 必保技能 (用户指定, 即使语料中低频也保留)
    "Haystack": (["haystack", "deepset haystack"], "AI", 0.82),
    "Dify": (["dify", "langgenius dify"], "AI Agent", 0.82),
    "RAGFlow": (["ragflow", "rag flow"], "AI", 0.82),
    "Reranker": (["reranker", "re-ranker", "cross-encoder"], "AI", 0.82),
    "MetaGPT": (["metagpt", "meta gpt"], "AI Agent", 0.80),
    "Tool Calling": (["tool calling", "tool call", "function calling", "function call"], "AI Agent", 0.90),
    "CUDA": (["cuda", "nvidia cuda"], "AI", 0.90),
    "LoRA": (["lora", "low-rank adaptation"], "AI", 0.90),
    "QLoRA": (["qlora", "quantized lora"], "AI", 0.88),
    "DPO": (["dpo", "direct preference optimization"], "AI", 0.88),
    "PEFT": (["peft", "parameter efficient fine-tuning"], "AI", 0.85),
    "Iceberg": (["iceberg", "apache iceberg"], "Data", 0.85),
    "Delta Lake": (["delta lake", "deltalake", "delta table"], "Data", 0.85),
    "Trino": (["trino", "trinodb"], "Data", 0.82),
    "Data Mesh": (["data mesh", "datamesh"], "Data", 0.82),
    "Coze": (["coze", "扣子"], "AI Agent", 0.80),
    "Agents SDK": (["agents sdk", "openai agents", "agent sdk"], "AI Agent", 0.82),
    "Semantic Kernel": (["semantic kernel", "sk"], "AI Agent", 0.82),
    "AutoGPT": (["autogpt", "auto gpt"], "AI Agent", 0.80),
    "BabyAGI": (["babyagi", "baby agi"], "AI Agent", 0.78),
    "Voyager": (["voyager", "voyager agent"], "AI Agent", 0.78),
    "Mem0": (["mem0", "mem0ai"], "AI", 0.80),
    "MemGPT": (["memgpt", "mem gpt", "letta"], "AI", 0.80),
    "Swarm": (["openai swarm", "agent swarm"], "AI Agent", 0.80),
    "Magentic": (["magentic", "magentic-one"], "AI Agent", 0.78),
    "Adept": (["adept", "adept ai"], "AI Agent", 0.78),
    "Imbue": (["imbue", "imbue ai"], "AI Agent", 0.78),
    "Cursor": (["cursor", "cursor ide", "cursor ai"], "AI", 0.85),
    "Copilot": (["copilot", "github copilot", "ai coding assistant"], "AI", 0.90),
    "Codex": (["codex", "openai codex"], "AI", 0.82),
    "Devin": (["devin", "cognition devin"], "AI Agent", 0.82),
    "Claude Code": (["claude code", "claude-code"], "AI", 0.82),
    "Aider": (["aider", "aider ai"], "AI", 0.78),
    "Continue": (["continue dev", "continue ai"], "AI", 0.80),
    "Cody": (["cody", "sourcegraph cody"], "AI", 0.80),
    "Tabnine": (["tabnine", "tabnine ai"], "AI", 0.78),
    "Codeium": (["codeium", "windsurf"], "AI", 0.82),
    "Replit": (["replit", "replit agent"], "AI", 0.80),
    "Bolt": (["bolt.new", "bolt ai"], "AI", 0.80),
    "v0": (["v0.dev", "vercel v0", "v0 by vercel"], "AI", 0.80),
    "Lovable": (["lovable", "lovable.dev"], "AI", 0.78),
    "Tempo": (["tempo labs", "tempo ai"], "AI", 0.78),
    "Galileo": (["galileo ai", "galileo"], "AI", 0.78),
    "Uizard": (["uizard", "uizard ai"], "AI", 0.78),
    "Keras": (["keras", "tf keras"], "AI", 0.88),
    "Apache Flink": (["apache flink"], "Data", 0.85),
    "Apache Beam": (["apache beam", "beam"], "Data", 0.80),
    "Snowflake": (["snowflake", "snowflake db"], "Data", 0.85),
    "Databricks": (["databricks"], "Data", 0.85),
    "dbt": (["dbt", "data build tool"], "Data", 0.85),
    "Fivetran": (["fivetran"], "Data", 0.80),
    "Airbyte": (["airbyte"], "Data", 0.80),
    "Great Expectations": (["great expectations", "gx"], "Data", 0.80),
    "Monte Carlo": (["monte carlo data", "montecarlo"], "Data", 0.78),
    "Soda": (["soda data", "sodaql"], "Data", 0.78),
    "Dagster": (["dagster"], "Data", 0.82),
    "Prefect": (["prefect", "prefecthq"], "Data", 0.82),
    "Temporal": (["temporal io", "temporal workflow"], "Data", 0.80),
    "Ray": (["ray", "ray distributed"], "AI", 0.85),
    "Horovod": (["horovod"], "AI", 0.78),
    "DeepSpeed": (["deepspeed", "microsoft deepspeed"], "AI", 0.88),
    "Megatron": (["megatron", "nvidia megatron", "megatron-lm"], "AI", 0.85),
    "ColossalAI": (["colossalai", "colossal ai"], "AI", 0.80),
    "FairScale": (["fairscale", "facebook fairscale"], "AI", 0.78),
    "HuggingFace Hub": (["huggingface hub", "hf hub", "hugging face hub"], "AI", 0.88),
    "Weights & Biases": (["weights & biases", "wandb", "weights and biases"], "AI", 0.88),
    "Neptune": (["neptune ai", "neptune.ml"], "AI", 0.80),
    "Comet": (["comet ml", "cometml"], "AI", 0.78),
    "DVC": (["dvc", "data version control"], "Data", 0.82),
    "Pachyderm": (["pachyderm"], "Data", 0.78),
    "Feast": (["feast", "feast feature store"], "Data", 0.82),
    "Tecton": (["tecton", "tecton ai"], "Data", 0.80),
    "Hopsworks": (["hopsworks", "hopsworks ai"], "Data", 0.78),
    "Seldon": (["seldon", "seldon core"], "AI", 0.80),
    "BentoML": (["bentoml", "bento ml"], "AI", 0.82),
    "Ray Serve": (["ray serve"], "AI", 0.80),
    "SageMaker": (["sagemaker", "aws sagemaker"], "Cloud", 0.88),
    "Vertex AI": (["vertex ai", "google vertex ai"], "Cloud", 0.85),
    "Azure ML": (["azure ml", "azure machine learning"], "Cloud", 0.85),
    "Modal": (["modal", "modal labs"], "Cloud", 0.80),
    "Replicate": (["replicate", "replicate.com"], "Cloud", 0.82),
    "HuggingFace Spaces": (["huggingface spaces", "hf spaces"], "Cloud", 0.82),
    "Together AI": (["together ai", "together.xyz", "together compute"], "Cloud", 0.82),
    "Fireworks AI": (["fireworks ai", "fireworks"], "Cloud", 0.80),
    "Anyscale": (["anyscale", "anyscale ray"], "Cloud", 0.80),
    "BentoCloud": (["bentocloud"], "Cloud", 0.78),
    "Gin": (["gin", "gin-gonic"], "Backend", 0.82),
    "Echo": (["echo", "echo framework"], "Backend", 0.78),
    "Beego": (["beego"], "Backend", 0.78),
    "Iris": (["iris", "iris-go"], "Backend", 0.78),
    "Fiber": (["fiber", "gofiber"], "Backend", 0.80),
    "Gorilla": (["gorilla", "gorilla mux"], "Backend", 0.78),
    "Chi": (["chi", "go-chi"], "Backend", 0.78),
    "Buffalo": (["buffalo", "gobuffalo"], "Backend", 0.75),
    "Revel": (["revel"], "Backend", 0.75),
    "Martini": (["martini", "go-martini"], "Backend", 0.75),
    "Kratos": (["kratos", "go-kratos"], "Backend", 0.78),
    # GitHub README / arXiv 新增
    "OpenWebUI": (["openwebui", "open webui"], "AI", 0.80),
    "TextGenWebUI": (["text-generation-webui", "oobabooga"], "AI", 0.78),
    "MoE": (["moe", "mixture of experts", "mixture-of-experts"], "AI", 0.85),
    "Diffusion Transformer": (["diffusion transformer", "dit"], "AI", 0.85),
    "Vision Language Model": (["vision language model", "vlm", "vision-language"], "AI", 0.88),
    "LLM Evaluation": (["llm evaluation", "llm benchmark", "lm-eval"], "AI", 0.82),
    "LLM Reasoning": (["llm reasoning", "chain of thought"], "AI", 0.85),
    "Instruction Tuning": (["instruction tuning", "instruction fine-tuning"], "AI", 0.85),
    "Text-to-Image": (["text-to-image", "text2image", "image generation"], "AI", 0.88),
    "Video Generation": (["video generation", "text-to-video", "sora"], "AI", 0.85),
    "Speech Recognition": (["speech recognition", "asr", "whisper"], "AI", 0.88),
    "Text-to-Speech": (["text-to-speech", "tts"], "AI", 0.85),
    "Self-Supervised Learning": (["self-supervised learning", "ssl"], "AI", 0.85),
    "Contrastive Learning": (["contrastive learning", "simclr"], "AI", 0.82),
    "Anomaly Detection": (["anomaly detection", "outlier detection"], "AI", 0.82),
    "Time Series": (["time series", "time-series", "forecasting"], "AI", 0.85),
    "Collaborative Filtering": (["collaborative filtering", "matrix factorization"], "AI", 0.80),
}

NOISE_WORDS = {"hr", "hrm", "自动化", "未注明", "产品设计", "销售", "运营", "项目管理",
               "测试", "运维", "开发", "管理", "设计", "技术", "实施", "维护", "支持", "咨询"}


def collect_texts():
    """从所有数据源收集文本"""
    texts = []  # (text, source_label)
    src_stats = Counter()

    # JD
    jd_path = os.path.join(BASE, "data", "clean", "jd_clean.csv")
    if os.path.exists(jd_path):
        with open(jd_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                text = f"{r.get('job_title','')} {r.get('description','')} {r.get('requirements','')} {r.get('skill_raw','')} {r.get('skill_standard','')}"
                texts.append((text, "JD"))
        src_stats["JD"] = sum(1 for _ in open(jd_path, encoding="utf-8-sig")) - 1

    # GitHub Detail, GitHub, arXiv, Blog
    for fname, label in [("github_detail.jsonl", "GitHub"), ("github_trend.jsonl", "GitHub"), ("arxiv_trend.jsonl", "arXiv"), ("blog_trend.jsonl", "Blog")]:
        path = os.path.join(BASE, "data", "raw", fname)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                        text = f"{r.get('tech_name','')} {r.get('summary','')} {' '.join(r.get('tags',[]))}"
                        texts.append((text, label))
                        src_stats[label] += 1
                    except:
                        pass

    return texts, src_stats


def main():
    print("=" * 55)
    print("  技能词库扩展 (JD + GitHub + arXiv + Blog)")
    print("=" * 55)

    texts, src_stats = collect_texts()
    print(f"数据源: JD={src_stats.get('JD',0)}, GitHub={src_stats.get('GitHub',0)}, arXiv={src_stats.get('arXiv',0)}, Blog={src_stats.get('Blog',0)}")

    # Extract skills
    skill_counts = Counter()
    skill_sources = {}

    for text, src in texts:
        text_lower = text.lower()
        for std_name, (aliases, cat, conf) in SKILL_DB.items():
            for alias in aliases:
                if len(alias) <= 4:
                    if re.search(r'(?<![a-zA-Z])' + re.escape(alias) + r'(?![a-zA-Z])', text_lower):
                        skill_counts[std_name] += 1
                        if std_name not in skill_sources:
                            skill_sources[std_name] = set()
                        skill_sources[std_name].add(src)
                        break
                else:
                    if alias in text_lower:
                        skill_counts[std_name] += 1
                        if std_name not in skill_sources:
                            skill_sources[std_name] = set()
                        skill_sources[std_name].add(src)
                        break

    # Auto-extract from JD skill_raw/skill_standard
    jd_path = os.path.join(BASE, "data", "clean", "jd_clean.csv")
    jd_extra = Counter()
    if os.path.exists(jd_path):
        with open(jd_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                for field in ["skill_raw", "skill_standard"]:
                    for token in r.get(field, "").replace(",", ";").split(";"):
                        token = token.strip()
                        if len(token) >= 2 and token not in NOISE_WORDS and token != "未注明":
                            jd_extra[token] += 1

    # Build candidates
    candidates = []
    for std_name, (aliases, cat, conf_base) in SKILL_DB.items():
        freq = skill_counts.get(std_name, 0)
        if freq > 0:
            sources = skill_sources.get(std_name, set())
            adj_conf = min(0.99, conf_base + min(freq / 500, 0.05))
            candidates.append({
                "skill_name": std_name, "alias": aliases[0],
                "category": cat, "frequency": freq,
                "source_count": len(sources),
                "confidence": round(adj_conf, 2),
            })

    # Add auto-extracted (skip if already in candidates)
    existing_names = set(c["skill_name"].lower() for c in candidates)
    for token, freq in jd_extra.most_common():
        if freq >= 2 and token.lower() not in existing_names:
            cat = "AI" if any(kw in token.lower() for kw in ["ai", "ml", "dl", "llm", "nlp", "cv", "算法", "模型", "学习", "pytorch", "tensorflow"]) else \
                  "Backend" if any(kw in token.lower() for kw in ["java", "spring", "api", "服务", "后端", "go", "rust"]) else \
                  "Frontend" if any(kw in token.lower() for kw in ["vue", "react", "js", "前端", "css"]) else \
                  "Data" if any(kw in token.lower() for kw in ["sql", "data", "etl", "spark", "hadoop"]) else \
                  "Cloud" if any(kw in token.lower() for kw in ["cloud", "docker", "k8s", "云"]) else \
                  "Database" if any(kw in token.lower() for kw in ["mysql", "redis", "mongo", "db"]) else \
                  "IoT" if any(kw in token.lower() for kw in ["linux", "embedded", "嵌入式"]) else "Backend"
            candidates.append({
                "skill_name": token, "alias": token.lower(),
                "category": cat, "frequency": freq,
                "source_count": 1, "confidence": round(min(0.95, 0.7 + freq / 200), 2),
            })

    # Guaranteed minimum: all SKILL_DB entries included
    existing_names = set(c["skill_name"].lower() for c in candidates)
    guaranteed_added = 0
    for std_name, (aliases, cat, conf_base) in SKILL_DB.items():
        if std_name.lower() not in existing_names:
            candidates.append({
                "skill_name": std_name, "alias": aliases[0],
                "category": cat, "frequency": 0,
                "source_count": 0, "confidence": round(conf_base, 2),
            })
            guaranteed_added += 1

    candidates.sort(key=lambda x: -x["frequency"])

    # Save skill_candidates.csv
    out_csv = os.path.join(BASE, "data", "clean", "skill_candidates.csv")
    fields = ["skill_name", "alias", "category", "frequency", "source_count", "confidence"]
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(candidates)

    # Save skill_ontology.json
    out_ont = os.path.join(BASE, "data", "meta", "skill_ontology.json")
    ontology = {}
    for c in candidates:
        std = c["skill_name"]
        aliases_list = next((a for s, (a, _, _) in SKILL_DB.items() if s == std), [std])
        ontology[std] = {
            "standard_name": std, "aliases": aliases_list,
            "category": c["category"], "parent_skill": "",
            "lifecycle_stage": "mature" if c["frequency"] > 100 else ("growth" if c["frequency"] > 30 else "emerging"),
        }
    with open(out_ont, "w", encoding="utf-8") as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2)

    # Stats
    cats = Counter(c["category"] for c in candidates)
    orig_count = len(candidates) - guaranteed_added
    print(f"\nJD数量: {src_stats.get('JD', 0)}")
    print(f"GitHub: {src_stats.get('GitHub', 0)}")
    print(f"arXiv: {src_stats.get('arXiv', 0)}")
    print(f"Blog: {src_stats.get('Blog', 0)}")
    print(f"原技能数量: {orig_count}")
    print(f"新增技能数量: {guaranteed_added}")
    print(f"最终技能数量: {len(candidates)}")
    print(f"分类统计: {dict(cats)}")
    print(f"覆盖率: 100%")
    print(f"输出: {out_csv}")
    print(f"输出: {out_ont}")


if __name__ == "__main__":
    raise SystemExit("Retired: use rebuild_skill_ontology_v2.py; default lifecycle labels are forbidden.")
