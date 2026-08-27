# TALENT-GRAPH-EVOLUTION 数据资产报告

> 生成时间: 
> 项目: 多源异构数据驱动岗位和能力图谱构建与动态演化分析系统

---

## 一、数据规模

```
═══════════════════════════════════════════
  总数据文件:  21 个
  总数据量:    ~8,500 条记录
  字段总数:    ~150 个去重字段
  技能覆盖:    545 个标准技能
  数据来源:    10+ 平台
═══════════════════════════════════════════
```

---

## 二、数据类型

| 类型 | 数量 | 来源 | 用途 |
|------|------|------|------|
| JD 岗位数据 | 2,500 | 智联招聘(2244) + 猎聘(256) | 岗位需求分析 |
| 技术趋势(GitHub) | 389 | GitHub Search API | 技术趋势/技能演化 |
| 技术趋势(GitHub Detail) | 389 | GitHub Repo API + README | 技术栈深度抽取 |
| 技术趋势(arXiv) | 359 | arXiv API | 学术前沿追踪 |
| 技术趋势(Blog) | 857 | HuggingFace/Google Research/MIT | 产业技术动态 |
| 人才数据 | 180 | GitHub公开用户(120) + 合成简历(60) | 人才能力画像 |
| 课程数据 | 384 | 8平台(中国大学MOOC/Coursera/华为云等) | 技能学习路径 |
| 证书数据 | 101 | 华为/AWS/阿里云/CNCF/软考等 | 技能认证体系 |
| 评估数据 | 250 | Gold JD(50)+Resume(50)+Match(100)+Negative(50) | 人岗匹配评估 |
| 技能本体 | 519 | 多源抽取+标准化 | 技能体系标准化 |

---

## 三、技能体系

### 3.1 技能数量与分类

```
总计: 519 个标准技能

AI:             144 (27.7%)  — LLM, RAG, Agent, PyTorch, NLP, CV, Diffusion...
Backend:        216 (41.6%)  — Java, Spring Boot, Go, Rust, MySQL, Redis...
Data:            44 (8.5%)   — Spark, Hadoop, Flink, Kafka, ETL, 数据仓库...
Cloud:           28 (5.4%)   — Docker, Kubernetes, AWS, Terraform, CI/CD...
Frontend:        28 (5.4%)   — React, Vue, TypeScript, Next.js, Tailwind...
AI Agent:        21 (4.0%)   — LangChain, LangGraph, CrewAI, AutoGen, MCP...
Database:        12 (2.3%)   — PostgreSQL, MongoDB, ClickHouse, TiDB...
IoT:             10 (1.9%)   — Linux, Git, Android, iOS, 嵌入式, MQTT...
DevOps:           9 (1.7%)   — Jenkins, Prometheus, Grafana, Ansible...
Security:         7 (1.3%)   — 网络安全, OAuth2, JWT, SSO, Shiro...
```

### 3.2 技能生命周期分布

| 阶段 | 数量 | 占比 |
|------|------|------|
| mature (成熟) | 39 | 7.5% |
| growth (增长) | 52 | 10.0% |
| emerging (新兴) | 428 | 82.5% |

### 3.3 核心技能方向覆盖

```
LLM 生态:      GPT, LLaMA, Qwen, DeepSeek, ChatGLM, Mistral, Claude, Gemini
RAG 生态:      向量数据库, Milvus, FAISS, Pinecone, Chroma, Qdrant, Reranker
Agent 生态:    LangChain, LangGraph, CrewAI, AutoGen, Tool Calling, MCP
AI 工程:       vLLM, TensorRT, ONNX, CUDA, LoRA, QLoRA, RLHF, DPO, PEFT
Cloud 生态:    Docker, Kubernetes, AWS, Azure, GCP, 阿里云, 腾讯云, 华为云
Data 生态:     Spark, Flink, Kafka, Hadoop, Airflow, ClickHouse, Trino
Backend 生态:  Java, Spring Boot, Go, Rust, C/C++, Redis, PostgreSQL, MySQL
Frontend 生态: React, Vue, TypeScript, Next.js, Nuxt.js, Tailwind
```

---

## 四、数据文件清单

### 4.1 原始数据 (data/raw/)

| 文件 | 数量 | 字段 | 说明 |
|------|------|------|------|
| `jd_raw.csv` | 4,373 | 19 | 原始JD (智联2720+猎聘1653) |
| `github_trend.jsonl` | 389 | 7 | GitHub开源项目 |
| `github_detail.jsonl` | 389 | 14 | GitHub README详情+技术栈 |
| `arxiv_trend.jsonl` | 359 | 14 | arXiv论文 (cs.AI/cs.LG/cs.CL/cs.CV) |
| `blog_trend.jsonl` | 857 | 7 | 技术博客 (HuggingFace/Google/MIT) |
| `tech_trend.jsonl` | 973 | 7 | 旧版技术趋势合并 |
| `github_raw.jsonl` | 120 | 5 | 旧版GitHub数据 |
| `resume_raw.jsonl` | 180 | 13 | 人才原始数据 |

### 4.2 清洗数据 (data/clean/)

| 文件 | 数量 | 字段 | 说明 |
|------|------|------|------|
| `jd_clean.csv` | 2,500 | 21 | 标准岗位数据 (100%技能覆盖) |
| `resume_clean.csv` | 180 | 19 | 人才简历 (100%技能覆盖) |
| `skill_candidates.csv` | 519 | 6 | 技能候选词库 |

### 4.3 元数据 (data/meta/)

| 文件 | 数量 | 说明 |
|------|------|------|
| `skill_ontology.json` | 519 | 技能本体 (standard_name/category/parent/lifecycle) |
| `job_standard_dict.csv` | 37 | 岗位名标准化字典 |
| `gold_jd_set.json` | 50 | 标准岗位 (required/bonus skills) |
| `gold_resume_set.json` | 50 | 标准简历 (项目+技能准确度) |
| `match_label_set.json` | 100 | 人岗匹配标注 (high:35/medium:35/low:30) |
| `negative_samples.json` | 50 | 负样本 (5种类型) |
| `talent_profile.json` | — | 人才数据画像统计 |
| `gold_jd_set_reviewed.json` | 100 | 标准岗位 (人工复核) |
| `gold_resume_set_reviewed.json` | 50 | 标准简历 (人工复核) |
| `match_label_set_reviewed.json` | 100 | 人岗匹配标注 (人工复核, high:31/medium:35/low:34) |
| `negative_samples_reviewed.json` | 50 | 负样本 (人工复核, 5种类型) |

### 4.4 教育数据 (data/education/)

| 文件 | 数量 | 字段 | 说明 |
|------|------|------|------|
| `course_data.csv` | 384 | 8 | 课程 (8平台×48模板) |
| `certificate_data.csv` | 101 | 6 | 证书 (30+颁发机构) |

---

## 五、数据质量检查

### 5.1 字段完整率

| 数据集 | job_title | company | skill_standard | source_url |
|--------|----------|---------|---------------|------------|
| jd_clean.csv | 100% | 100% | 100% | 100% |
| resume_clean.csv | — | — | 100% | — |
| github_trend.jsonl | 100% | — | — | 100% |
| arxiv_trend.jsonl | 100% | — | — | 100% |
| blog_trend.jsonl | 100% | — | — | 100% |

### 5.2 重复检查

| 数据集 | 检查维度 | 结果 |
|--------|---------|------|
| jd_clean.csv | source_url | 0 重复 |
| jd_clean.csv | company+title+location | <3% 近似重复 |
| github_trend.jsonl | source_url | 0 重复 |
| arxiv_trend.jsonl | source_url | 0 重复 |
| skill_candidates.csv | skill_name | 0 重复 |

### 5.3 技能映射覆盖率

| 数据集 | 覆盖率 |
|--------|--------|
| jd_clean.csv skill_standard | 100% (2500/2500) |
| resume_clean.csv skill_standard | 100% (180/180) |
| skill_candidates → ontology | 100% (519/519) |
| 课程数据 skills → ontology | 97.0% |
| 证书数据 related_skills → ontology | 97.5% |
| 评估数据 skills → ontology | 85.5% (初始) → 100% (人工复核后) |

### 5.4 来源分布

| 来源 | 数量 |
|------|------|
| 智联招聘 (zhaopin) | 2,244 |
| 猎聘 (liepin) | 256 |
| GitHub API | 389 |
| arXiv API | 359 |
| HuggingFace RSS | 822 |
| Google Research RSS | 25 |
| MIT Tech Review | 10 |
| GitHub 公开用户 | 120 |
| 合成简历 | 60 |
| 公开课程平台 | 384 |
| 认证机构 | 101 |

---

## 六、数据血缘图

```
                    ┌──────────────────┐
                    │   skill_ontology │  ← 519 标准技能
                    │   (data/meta/)   │
                    └────────┬─────────┘
                             │ 技能标准化
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼─────┐      ┌──────▼──────┐      ┌─────▼──────┐
   │ JD 岗位  │      │  技术趋势    │      │  人才简历   │
   │  2,500   │      │  1,605      │      │   180      │
   └──────────┘      └─────────────┘      └────────────┘
        │                    │                    │
   ┌────▼─────┐      ┌──────▼──────┐      ┌─────▼──────┐
   │ 智联招聘 │      │ GitHub 389  │      │ GitHub 120 │
   │ 猎聘     │      │ arXiv 359   │      │ 合成 60    │
   │          │      │ Blog 857    │      │            │
   └──────────┘      └─────────────┘      └─────────────┘

   ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
   │  教育数据     │    │   评估数据      │    │  证书数据     │
   │  课程 384    │    │  Gold JD 50    │    │  101         │
   │  证书 101    │    │  Resume 50     │    │              │
   │              │    │  Match 100     │    │              │
   │              │    │  Negative 50   │    │              │
   └──────────────┘    └────────────────┘    └──────────────┘
```

---

## 七、人工审核评估数据

### 7.1 审核概况

本项目初始评估样本由规则生成，用于构建待人工审核的候选样本集。
为提高评估数据可信度，项目组对候选样本进行了人工复核，形成 reviewed 版本。

| 指标 | 数值 |
|------|------|
| 总审核样本数 | 300 条 |
| Gold JD 标准岗位 | 100 条 |
| Gold Resume 标准简历 | 50 条 |
| Match Label 匹配标注 | 100 条（high=31, medium=35, low=34） |
| Negative Samples 负样本 | 50 条（5种类型） |
| 技能映射覆盖率 | 100%（人工复核后） |
| 审核人数量 | 5 人（余昭、徐赠贺、郭炫宇、邓佑杰、胡苗苗） |
| 审核时间跨度 | 2026-07-07 至 2026-07-10 |

### 7.2 审核字段

每条 reviewed 记录包含以下人工审核字段：

- `review_status`：审核状态
- `reviewer`：审核人姓名
- `review_time`：审核时间
- `manual_reason`：人工审核理由
- `final_*` 字段：人工修正后的最终标注（如 final_required_skills、final_match_level、final_reason 等）

### 7.3 数据用途

该 300 条 reviewed 数据可用于系统原型阶段的：

1. 岗位技能抽取评估 — 以 gold_jd_set_reviewed.json 作为标准答案
2. 简历技能画像评估 — 以 gold_resume_set_reviewed.json 作为参考基准
3. 人岗匹配等级评估 — 以 match_label_set_reviewed.json 的高/中/低标注计算匹配准确率
4. 负样本识别测试 — 以 negative_samples_reviewed.json 验证系统的错误拒绝能力

### 7.4 规模说明

该评估集规模为**原型验证级别**（300 条），适用于算法开发和初步指标计算。
不应夸大为大规模工业标注数据集。原始规则生成文件与人工复核版本同时保留，
保证数据来源可追溯。

---

## 八、后续知识图谱需要的数据

### 8.1 节点类型

| 节点 | 数据源 | 数量 |
|------|--------|------|
| **岗位节点 (Job)** | jd_clean.csv | 2,500 |
| **技能节点 (Skill)** | skill_ontology.json | 519 |
| **人才节点 (Talent)** | resume_clean.csv | 180 |
| **技术节点 (TechProject)** | github_trend.jsonl | 389 |
| **论文节点 (Paper)** | arxiv_trend.jsonl | 359 |
| **博客节点 (Blog)** | blog_trend.jsonl | 857 |
| **课程节点 (Course)** | course_data.csv | 384 |
| **证书节点 (Certificate)** | certificate_data.csv | 101 |
| **企业节点 (Company)** | jd_clean.csv | ~2,000 唯一企业 |

### 8.2 建议关系类型

| 关系 | 来源→目标 | 示例 |
|------|----------|------|
| REQUIRES_SKILL | Job→Skill | Java后端工程师 REQUIRES_SKILL Spring Boot |
| HAS_SKILL | Talent→Skill | 张三 HAS_SKILL Python |
| USES_TECH | TechProject→Skill | LangChain USES_TECH LLM |
| TEACHES_SKILL | Course→Skill | 深度学习课程 TEACHES_SKILL PyTorch |
| CERTIFIES_SKILL | Certificate→Skill | AWS SAA CERTIFIES_SKILL AWS |
| BELONGS_TO | Skill→SkillCategory | LLM BELONGS_TO AI |
| CHILD_OF | Skill→Skill | RAG CHILD_OF 大语言模型 |
| MATCHES | Talent→Job | 张三 MATCHES 大模型工程师 (high) |
| PUBLISHED_BY | Job→Company | Java岗 PUBLISHED_BY 字节跳动 |

### 8.3 知识图谱规模预估

```
节点总数:  ~5,500
关系总数:  ~15,000+ (基于技能共现)
```

---

> 本报告由 `data_summary_report.md` 自动生成。所有数据文件位于 `crawler/data/` 目录下。
