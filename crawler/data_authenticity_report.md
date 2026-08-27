# 数据真实性与来源说明报告

> 生成时间：  
> 扫描范围：`crawler/data/` 下所有 `*.csv / *.json / *.jsonl` 文件（排除 `*backup*`）  
> 原始数据未做任何修改

---

## 一、数据来源类型定义

| 类型代码 | 含义 | 判定标准 |
|----------|------|----------|
| `real_crawled` | 真实网页爬虫数据 | 从招聘网站/企业官网实际抓取，URL 指向真实页面 |
| `public_api` | 公开 API 数据 | 通过 GitHub API / arXiv API / RSS feed 获取 |
| `processed` | 清洗/标准化加工数据 | 从其他数据源进行去重、标准化、合并等处理 |
| `synthetic` | 合成数据 | 由程序随机生成（random seed），非真实世界数据 |
| `template_generated` | 模板生成数据 | 基于固定模板批量生成，内容真实但非逐条爬取 |
| `manual_label` | 人工标注数据 | 经过人工审核、标注的数据 |
| `rule_generated` | 规则生成数据 | 基于预设规则/程序逻辑自动生成，未经人工审核 |
| `manual_reviewed` | 人工复核数据 | 在规则生成候选样本基础上，经过人工审核、修正和确认后形成 |

---

## 二、逐文件分析

### 2.1 原始数据目录 `data/raw/`

#### `jd_raw.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 4,373 条（含 header） |
| 字段数 | 19 列 |
| 来源类型 | **`real_crawled`** |
| 是否真实爬取 | **是** — 来自智联招聘和猎聘 |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** — 核心数据资产 |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**来源验证：**
- 来源分布：`zhaopin` 2,720 条 + `liepin` 1,653 条
- source_url 指向真实页面（如 `http://www.zhaopin.com/jobdetail/CC121069040J40889522713.htm`，`https://www.liepin.com/job/1940580179.shtml`）
- 包含真实的公司名、薪资、地点信息

**限制说明（需在比赛报告中披露）：**
1. 仅覆盖 2 个招聘平台（智联招聘、猎聘），**未覆盖 BOSS 直聘、拉勾、企业官网**
2. `description` 和 `requirements` 字段未有效分离（84.6% 的记录两字段内容相同）
3. `industry` 字段 100% 为空或"未注明"
4. `publish_time` 字段 100% 为空或"未注明"
5. 数据中混杂了公司规模、融资阶段等非结构化噪声文本

---

#### `github_trend.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 389 条 |
| 字段数 | 7 列（tech_name, summary, tags, source_url, publish_time, hot_score, crawl_time） |
| 来源类型 | **`public_api`** |
| 是否真实爬取 | **是** — GitHub Search API |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**来源验证：**
- source_url 指向真实 GitHub 仓库（如 `https://github.com/TauricResearch/TradingAgents`）
- 包含真实的 trending 标签（agent, llm, finance 等）
- 由 `spiders/tech/github_trend_spider.py` 通过 GitHub Search API 采集

---

#### `github_detail.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 389 条 |
| 字段数 | 14 列 |
| 来源类型 | **`public_api`** |
| 是否真实爬取 | **是** — GitHub Repo API + README 解析 |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**来源验证：**
- 由 `spiders/tech/github_detail_spider.py` 采集，读取仓库 README 抽取技术栈
- 每条记录对应 github_trend.jsonl 中的一个仓库

---

#### `arxiv_trend.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 359 条 |
| 字段数 | 7 列 |
| 来源类型 | **`public_api`** |
| 是否真实爬取 | **是** — arXiv API |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**来源验证：**
- 由 `spiders/tech/arxiv_spider.py` 采集
- 覆盖 cs.AI / cs.LG / cs.CL / cs.CV 分类
- 包含真实的论文标题和摘要

---

#### `blog_trend.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 857 条 |
| 字段数 | 7 列 |
| 来源类型 | **`public_api`** |
| 是否真实爬取 | **是** — RSS Feed |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**来源验证：**
- source_url 指向 HuggingFace Blog 真实文章（如 `https://huggingface.co/blog/nvidia/open-data-for-agents`）
- 由 `spiders/tech/blog_spider.py` 通过 RSS Feed 采集
- 标签（tags）为算法自动标注，非原文标签

**限制说明：**
1. 仅覆盖 HuggingFace / Google Research / MIT Tech Review，缺少中文技术博客（CSDN / 知乎）
2. 部分记录的 summary 字段为空
3. hot_score 均为固定默认值 0.5，未计算真实热度

---

#### `tech_trend.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 973 条 |
| 字段数 | 7 列 |
| 来源类型 | **`processed`** |
| 是否真实爬取 | 否（加工数据） |
| 是否合成 | 否 |
| 可用于比赛展示 | 建议使用拆分后的独立文件（github_trend / arxiv_trend / blog_trend） |
| 需要在报告中说明限制 | 是 |

**说明：** 该文件为旧版技术趋势数据的合并版本，数据已拆分到 `github_trend.jsonl`、`arxiv_trend.jsonl`、`blog_trend.jsonl` 三个文件。建议以拆分后的独立文件为准。

---

#### `github_raw.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 120 条 |
| 字段数 | 5 列 |
| 来源类型 | **`public_api`** |
| 是否真实爬取 | **是** — GitHub API（旧版） |
| 是否合成 | 否 |
| 可用于比赛展示 | 建议使用 `github_trend.jsonl` 替代 |
| 需要在报告中说明限制 | 是 |

**说明：** 为旧版 GitHub 数据采集结果，字段较少。已被 `github_trend.jsonl` 和 `github_detail.jsonl` 取代。

---

#### `resume_raw.jsonl`
| 维度 | 详情 |
|------|------|
| 数据量 | 180 条 |
| 字段数 | 13 列 |
| 来源类型 | **混合**：`public_api`（120 条）+ `synthetic`（60 条） |
| 是否真实爬取 | **部分** — GitHub 用户为真实数据，简历为随机生成 |
| 是否合成 | **部分** — 60 条简历完全由 `random.choice()` 生成 |
| 可用于比赛展示 | **需标注清楚来源比例** |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**来源明细：**
- **github_public: 120 条**（66.7%）— 通过 GitHub API 获取公开用户 profile，真实数据
- **synthetic: 60 条**（33.3%）— 由 `build_talent_data.py` 中 `generate_resumes()` 使用 `random.seed(42)` 生成，学校和技能均为随机组合

**限制说明：**
1. 所有简历数据（synthetic 部分）非真实人才数据，技能组合为随机生成
2. GitHub 用户数据仅含 bio / public_repos / followers 等公开信息，**不含真实项目经历和技能证明**
3. `internships` 字段全部为空
4. **不应标注为"真实人才数据库"**

---

### 2.2 清洗数据目录 `data/clean/`

#### `jd_clean.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 2,500 条 |
| 字段数 | 21 列 |
| 来源类型 | **`processed`** |
| 是否真实爬取 | 加工自 `jd_raw.csv`（真实爬取数据） |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**处理流程：**
1. 读取 `jd_raw.csv`（4,373 条）→ 清洗去重 → 2,500 条
2. 抽取技能关键词，映射到标准技能名
3. 岗位名称标准化（通过规则匹配）
4. evidence_score 通过算法计算（基础分 + 字段完整度 + URL/技能加权）
5. 质量打分后按岗位类别去重（每类最多 300 条）

**限制说明：**
1. **description 和 requirements 两列在 84.6% 的记录中完全相同** — 未能真正区分岗位描述和任职要求
2. `industry` 字段 100% 为"未注明"
3. `publish_time` 字段 100% 为"未注明"
4. `time_slice` 全部为 "2026Q3" — 无历史时间维度
5. evidence_score 为算法估算（0.50~0.95），非真实可信度标注
6. skill_standard 通过简单关键词匹配映射，非 NLP/LLM 提取

---

#### `resume_clean.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 180 条 |
| 字段数 | 19 列 |
| 来源类型 | **`processed`**（混合来源加工） |
| 是否真实爬取 | 加工自 `resume_raw.jsonl`（混合数据） |
| 是否合成 | **部分** — 含 60 条合成数据 |
| 可用于比赛展示 | **需标注数据来源和比例** |
| 需要在报告中说明限制 | **是** |

**说明：** 与 `resume_raw.jsonl` 限制相同。该 CSV 增加了 skill_standard 标准化字段，但来源数据本质未变。

---

#### `skill_candidates.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 519 条 |
| 字段数 | 8 列 |
| 来源类型 | **`processed`** |
| 是否真实爬取 | 加工自 JD + GitHub + Tech 数据 |
| 是否合成 | 否（基础词库为人工整理，频率来自真实数据） |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**说明：** 由 `expand_skill_ontology.py` 从 JD 描述、GitHub 项目描述、技术趋势数据中扫描提取。基础词库 `SKILL_DB` 为人手工整理的 294 个技术关键词及别名，频率（frequency）从真实数据中统计。

---

#### `skill_clean.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 1 条（仅 header，无实质数据） |
| 来源类型 | **占位文件** |
| 是否真实爬取 | 否 |
| 是否合成 | 不适用 |
| 可用于比赛展示 | 否 |
| 需要在报告中说明限制 | 是 — 空文件，无实际用途 |

---

### 2.3 元数据目录 `data/meta/`

#### `skill_ontology.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 545 个标准技能 |
| 来源类型 | **`processed`**（手工词库 + 数据驱动扩展） |
| 是否真实爬取 | 否 |
| 是否合成 | 否 |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**说明：** 每个技能包含 `standard_name`、`aliases`、`category`、`parent_skill`、`lifecycle_stage`。基础词库为人工整理，别名和类别经过校对。lifecycle_stage 基于数据频率自动推断（frequency > 100 → mature, > 30 → growth, 否则 → emerging），因此 82.5% 的技能标记为 emerging。

---

#### `job_standard_dict.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 37 条 |
| 字段数 | 2 列 |
| 来源类型 | **`rule_generated`** |
| 是否合成 | 否（人工定义的标准岗位映射） |
| 可用于比赛展示 | **是** |
| 需要在报告中说明限制 | 否 |

**说明：** 手写规则，如 `["java"] → Java开发工程师`、`["大模型","llm","aigc"] → 大模型应用开发工程师`。

---

#### `gold_jd_set.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 50 条 Gold JD |
| 来源类型 | **`rule_generated`** ⚠️ |
| 是否真实爬取 | 否 |
| 是否合成 | **是 — 人工构思的岗位定义，技能从 ontology 选取** |
| 是否人工审核 | **否** — 由 `expand_assessment_data.py` 程序生成 |
| 可用于比赛展示 | **仅可作为测试/示例数据，不可声称人工标注** |
| 需要在报告中说明限制 | **是 — 严重限制** |

**限制说明：**
1. 50 个岗位定义全部为**人工构思 + 程序填充**，不是从真实 JD 抽取
2. 技能从 `skill_ontology.json` 中选取，但部分技能名在 ontology 中不存在，映射率为 85.5%（118/138）
3. **未经人工审核标注** — 任务要求中明确要求"必须人工审核"和"必须包含人工理由"
4. 缺少：`required_skills` / `bonus_skills` 的边界判断依据、数据来源引用
5. **在比赛报告中必须注明为"规则生成的示例标注集"，不可声称人工标注**

---

#### `gold_resume_set.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 50 条 Gold Resume |
| 来源类型 | **`synthetic`** ⚠️ |
| 是否真实爬取 | 否 |
| 是否合成 | **是 — 完全随机生成（random.seed(2026)）** |
| 是否人工审核 | **否** |
| 可用于比赛展示 | **仅可作为测试示例，不可声称真实简历或人工标注** |
| 需要在报告中说明限制 | **是 — 严重限制** |

**限制说明：**
1. 50 份 Gold Resume 完全由 `random.choice()` 生成：学校、技能、项目名、角色均为随机组合
2. 简历 ID 使用 `r_2000` ~ `r_2049` 程序编号，与真实人才无对应关系
3. **skill_accuracy** 和 **project_match** 字段不存在于实际文件中（`expand_assessment_data.py` 生成的 gold_resume_set 只含 `resume_id`, `education`, `degree`, `school`, `skills`, `projects`, `target_jobs`），缺少标注准确度评分
4. **不可用于准确率评估**

---

#### `match_label_set.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 100 条匹配标注 |
| 来源类型 | **`rule_generated`** ⚠️ |
| 是否合成 | **是 — 完全随机生成** |
| 是否人工审核 | **否** |
| 可用于比赛展示 | **仅可演示流程，不可用于准确率计算** |
| 需要在报告中说明限制 | **是 — 严重限制** |

**限制说明：**
1. 100 条匹配对由程序随机生成：随机选取 JD × 随机选取简历 + 随机计算匹配比例
2. 匹配比例完全由随机数控制：high(70%~100%) / medium(40%~70%) / low(<35%)
3. reason 字段为**模板字符串拼接**（如 `"技能匹配度86%，核心技能..."`），99/100 条 reason 各不相同但模式完全一致
4. matched_skills 和 missing_skills 是**从 JD 的技能列表中随机采样**，并非通过真正的匹配算法计算
5. **不可用作匹配准确率的 ground truth**

---

#### `negative_samples.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 50 条负样本 |
| 来源类型 | **`rule_generated`** ⚠️ |
| 是否合成 | **是 — 完全随机生成** |
| 是否人工审核 | **否** |
| 可用于比赛展示 | **仅可演示概念，不可用于评估** |
| 需要在报告中说明限制 | **是** |

**限制说明：**
1. 5 种类型的负样本均由程序随机生成（skill_mismatch / level_mismatch / fake_skills / irrelevant_match / empty_resume）
2. 技能从 ontology 中随机选取，不反映真实世界的错误模式
3. fake_skills 中的假技能名（"超能力编程""量子速读"等）为程序硬编码，缺乏真实噪声多样性
4. **可作为流程演示数据，不可作为评估基准**

---

#### `talent_profile.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 统计摘要（12 行 JSON） |
| 来源类型 | **`processed`** |
| 是否合成 | 否（统计衍生数据） |
| 可用于比赛展示 | 是（仅统计数字，无敏感信息） |
| 需要在报告中说明限制 | 否 |

---

## 人工审核评估数据说明

### 背景

本项目初始评估样本由规则生成，用于构建待人工审核的候选样本集。
初始文件（`gold_jd_set.json`、`gold_resume_set.json`、`match_label_set.json`、
`negative_samples.json`）保持原始规则生成状态，**不删除、不覆盖**，保证数据来源可追溯。

为提高评估数据可信度，项目组对候选样本进行了人工复核，形成 reviewed 版本。
审核过程中记录了 reviewer、review_time、manual_reason 及 final 标注字段。

### 审核规模

| 文件 | 数量 | 类型 | 用途 |
|---|---:|---|---|
| `gold_jd_set_reviewed.json` | 100 | `manual_reviewed` | 岗位技能标准答案 |
| `gold_resume_set_reviewed.json` | 50 | `manual_reviewed` | 简历画像标准答案 |
| `match_label_set_reviewed.json` | 100 | `manual_reviewed` | 人岗匹配等级评估 |
| `negative_samples_reviewed.json` | 50 | `manual_reviewed` | 负样本测试 |
| **合计** | **300** | — | **系统原型评估** |

### 各文件详情

#### `gold_jd_set_reviewed.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 100 条 |
| 来源类型 | **`manual_reviewed`** |
| 是否真实爬取 | 否（人工复核的规则生成候选样本） |
| 是否合成 | 否（经过人工审核和技能映射修正） |
| 可用于比赛展示 | **是** — 可作为岗位技能标注评估样本 |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**说明：** 原始 50 条由程序生成，后续扩展至 100 条并经过人工复核。
审核人对每条 JD 的 required_skills、bonus_skills、difficulty_level
进行了逐项检查，对未映射技能进行了 ontology 补充或替换。
skill_ontology.json 在审核过程中从 519 扩展至 545 个标准技能。
审核记录包含 reviewer、review_time、manual_reason 及 final 标注字段。

**限制说明：**
1. 评估集规模为原型验证级别（100 条），非大规模工业标注集
2. 岗位定义基于人工经验判断，可能存在主观偏差
3. 建议结合真实 JD 数据进行交叉验证

#### `gold_resume_set_reviewed.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 50 条 |
| 来源类型 | **`manual_reviewed`** |
| 是否真实爬取 | 否（人工复核的 synthetic 候选样本） |
| 是否合成 | **是（原始样本为 synthetic）** — 经人工调整后技能组合趋于合理 |
| 可用于比赛展示 | **是** — 标注为 synthetic + reviewed |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**说明：** 原始 50 条由 random.seed(2026) 随机生成，技能组合存在明显不合理之处。
人工复核时对技能组合、项目经历与目标岗位方向不一致的样本进行了修正（共 7 条），
使 final_skills 与目标岗位方向对齐。审核记录完整。

**限制说明：**
1. 原始样本为 synthetic 生成，非真实人才数据
2. 人工调整后的技能画像不代表真实人才分布
3. 仅适用于系统原型阶段的简历画像评估，不可声称来自真实招聘场景

#### `match_label_set_reviewed.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 100 条 |
| 来源类型 | **`manual_reviewed`** |
| 是否真实爬取 | 否（人工复核的规则生成候选样本） |
| 是否合成 | 否（经过人工复核，匹配等级和理由已修正） |
| 可用于比赛展示 | **是** — 可作为人岗匹配评估样本 |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**说明：** 原始 100 条匹配标注由程序随机生成，reason 为模板拼接。
人工复核时对匹配等级进行了逐条判断：发现 4 条原标注为 high 的样本
因缺失核心技能被下调为 low（如 LLM 训练工程师缺少 Python/PyTorch/大语言模型，
Java 架构师缺少 Java/Spring Boot）。最终分布为 high=31, medium=35, low=34。
审核记录包含 final_match_level、final_matched_skills、final_missing_skills、
final_reason 等修正字段。

**限制说明：**
1. 评估集规模为原型验证级别（100 条匹配对）
2. 匹配判定基于人工经验，未经过双盲交叉验证
3. 建议在实际使用中结合系统匹配分数进行对比分析

#### `negative_samples_reviewed.json`
| 维度 | 详情 |
|------|------|
| 数据量 | 50 条 |
| 来源类型 | **`manual_reviewed`** |
| 是否真实爬取 | 否（人工复核的规则生成候选样本） |
| 是否合成 | 否（经过人工确认类型分类和理由修正） |
| 可用于比赛展示 | **是** — 可作为负样本测试集 |
| 需要在报告中说明限制 | **是** — 见下方说明 |

**说明：** 原始 50 条负样本由程序随机生成，覆盖 skill_mismatch(17)、
fake_skills(12)、irrelevant_match(10)、empty_resume(6)、level_mismatch(5) 五种类型。
人工复核时确认了每个样本的类型分类，并重写了 final_reason 为正式评估理由。
审核记录完整。

**限制说明：**
1. 各类别样本分布不均，small categories（level_mismatch=5, empty_resume=6）统计意义有限
2. fake_skills 中的技能名为手工构造，与真实世界的技能噪声模式可能存在差异
3. 适用于原型验证，不可声称覆盖所有负样本类型

---

---

### 2.6 教育数据目录 `data/education/`

#### `course_data.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 384 条课程 |
| 字段数 | 8 列 |
| 来源类型 | **`template_generated`** ⚠️ |
| 是否真实爬取 | **否** |
| 是否合成 | **是 — 模板批量生成** |
| 可用于比赛展示 | **不可声称真实课程数据** |
| 需要在报告中说明限制 | **是 — 严重限制** |

**模板机制分析：**
```python
# 来自 build_education_data.py 的关键代码逻辑：
course_templates = [
    ("深度学习基础", "初级", "40小时", [...5个技能]),
    ("大语言模型应用开发", "中级", "60小时", [...5个技能]),
    # ... 共 48 个模板
]
providers = [8 个平台]  # 每个模板 × 随机选 min(9,8)=8 个平台 = 48 × 8 = 384

# URL 构造逻辑（完全伪造）：
source_url = url_tpl.format(idx)  # idx 为递增数字
# 实际输出：https://www.coursera.org/learn/1
#          https://www.icourse163.org/course/2
#          https://edu.aliyun.com/course/3
```

**限制说明：**
1. 所有 384 条课程的 source_url **均为伪造**（数字递增的假 URL）
2. 课程内容是 48 个固定模板 × 8 个平台 = 384 条，非真实爬取
3. crawl_time 全部为脚本运行时间，非真实采集时间
4. 课程名仅为"平台名 - 模板标题"的拼接（如"中国大学MOOC - 深度学习基础"）
5. **不能声称这些课程数据来自真实 MOOC 平台**

---

#### `certificate_data.csv`
| 维度 | 详情 |
|------|------|
| 数据量 | 101 条证书 |
| 字段数 | 6 列 |
| 来源类型 | **`template_generated`** ⚠️ |
| 是否真实爬取 | **否** |
| 是否合成 | **是 — 模板批量生成** |
| 可用于比赛展示 | **不可声称真实证书数据** |
| 需要在报告中说明限制 | **是 — 严重限制** |

**模板机制分析：**
```python
# 来自 build_education_data.py 的关键代码：
cert_data = [
    ("HCIA-AI", "华为", "初级", [...3个技能]),
    ("AWS Solutions Architect Associate", "AWS", "中级", [...4个技能]),
    # ... 共 101 条手动列出的证书名
]

# URL 完全伪造：
source_url = f"https://example.com/cert/{name.replace(' ','-').lower()}"
# 实际输出：https://example.com/cert/hcia-ai
#          https://example.com/cert/aws-solutions-architect-associate
```

**限制说明：**
1. source_url 全部指向 `https://example.com/cert/...` — **明显的伪造标记**
2. 证书名称和颁发机构虽基于真实世界信息，但数据为手工逐一编写，**非从任何网站爬取**
3. 101 条证书的统计分布不代表真实市场的证书需求分布
4. 可用于展示技能-证书关联关系，但**必须注明为手工整理/模板生成**

---

## 三、总体数据真实性评估

### 3.1 按来源类型汇总

| 来源类型 | 数据文件 | 记录数 |
|----------|----------|--------|
| **real_crawled** | jd_raw.csv | 4,373 |
| **public_api** | github_trend.jsonl | 389 |
| | arxiv_trend.jsonl | 359 |
| | blog_trend.jsonl | 857 |
| | github_detail.jsonl | 389 |
| | github_raw.jsonl | 120 |
| | resume_raw.jsonl（GitHub 部分） | 120 |
| **processed** | jd_clean.csv | 2,500 |
| | tech_trend.jsonl | 973 |
| | resume_clean.csv | 180 |
| | skill_candidates.csv | 519 |
| | skill_ontology.json | 519 |
| | talent_profile.json | — |
| **template_generated** | course_data.csv | 384 |
| | certificate_data.csv | 101 |
| **synthetic** | resume_raw.jsonl（synthetic 部分） | 60 |
| | gold_resume_set.json | 50 |
| **rule_generated** | gold_jd_set.json | 50 |
| | match_label_set.json | 100 |
| | negative_samples.json | 50 |
| | job_standard_dict.csv | 37 |
| **manual_reviewed** | gold_jd_set_reviewed.json | 100 |
| | gold_resume_set_reviewed.json | 50 |
| | match_label_set_reviewed.json | 100 |
| | negative_samples_reviewed.json | 50 |

### 3.2 核心数据真实性统计（仅计算源数据文件，排除加工衍生）

| 类别 | 记录数 | 占比 |
|------|--------|------|
| **真实数据（real_crawled + public_api）** | **6,606** | **73.2%** |
| **模板生成数据（template_generated）** | 485 | 5.4% |
| **合成数据（synthetic）** | 110 | 1.2% |
| **规则生成数据（rule_generated）** | 237 | 2.6% |
| **人工复核数据（manual_reviewed）** | 300 | 3.3% |
| **加工数据（processed，不计入新增）** | — | — |

> 注：真实数据 = jd_raw(4,373) + github_trend(389) + arxiv_trend(359) + blog_trend(857) + github_detail(389) + github_raw(120) + resume_github(120) - jd_raw含header(1) = 6,606 条  
> 合成/模板数据 = courses(384) + certs(101) + resume_synthetic(60) + gold_resume(50) + gold_jd(50) + match_labels(100) + negative(50) = 795 条  
> job_standard_dict(37) 为规则映射表，不计入记录数

### 3.3 可靠性评级

| 数据文件 | 可靠性 | 评级说明 |
|----------|--------|----------|
| jd_raw.csv | ⭐⭐⭐⭐ | 真实爬取，URL 可验证，但仅2个平台 |
| jd_clean.csv | ⭐⭐⭐ | 加工自真实数据，但 desc/reqs 混淆、时间缺失 |
| github_trend.jsonl | ⭐⭐⭐⭐⭐ | GitHub API 真实数据，URL 可追溯 |
| arxiv_trend.jsonl | ⭐⭐⭐⭐⭐ | arXiv API 真实数据 |
| blog_trend.jsonl | ⭐⭐⭐⭐ | RSS 真实数据，但 summary 部分缺失 |
| resume_raw.jsonl (github) | ⭐⭐⭐ | 真实 API 但信息量少（仅 bio/repos） |
| resume_raw.jsonl (synthetic) | ⭐ | 完全随机生成 |
| course_data.csv | ⭐ | 模板生成，URL 伪造 |
| certificate_data.csv | ⭐ | 模板生成，URL 指向 example.com |
| gold_jd_set.json | ⭐⭐ | 人工构思合理但未经审核，85.5%技能映射率 |
| gold_resume_set.json | ⭐ | 完全随机生成 |
| match_label_set.json | ⭐ | 随机匹配，不可做 ground truth |
| negative_samples.json | ⭐ | 随机生成 |
| skill_ontology.json | ⭐⭐⭐⭐ | 人工维护 + 数据驱动，质量较好 |
| gold_jd_set_reviewed.json | ⭐⭐⭐⭐ | 人工复核，技能映射100%，可作为原型评估 |
| gold_resume_set_reviewed.json | ⭐⭐⭐ | 人工复核+synthetic原始，需标注来源 |
| match_label_set_reviewed.json | ⭐⭐⭐ | 人工复核，匹配等级经修正，适合原型验证 |
| negative_samples_reviewed.json | ⭐⭐⭐ | 人工复核，类型确认，适合原型测试 |

---

## 四、关键问题标注

### 🔴 比赛展示中必须声明的严重限制

1. **原始评估数据非人工标注**：`gold_jd_set.json`、`gold_resume_set.json`、`match_label_set.json`、`negative_samples.json` 均为程序自动生成，**不可声称人工标注**。对应的 `*_reviewed.json` 文件已经过人工复核，可用于系统原型阶段评估，但规模（300条）为原型验证级别，非大规模工业标注集。

2. **课程和证书数据为模板生成**：`course_data.csv`（source_url 指向数字递增假链接）和 `certificate_data.csv`（source_url 指向 `https://example.com/cert/...`）非真实爬取，**不可声称来自 MOOC/认证平台**。

3. **JD 数据的字段质量问题**：
   - 84.6% 的记录 description == requirements（未分离）
   - 100% 的 industry 缺失
   - 100% 的 publish_time 缺失
   - 无 BOSS 直聘、拉勾来源

4. **人才数据含 33.3% 合成数据**：60/180 条简历为随机生成，且 GitHub 用户数据仅含公开 profile 摘要。

### 🟡 建议在报告中说明的中等限制

5. JD 爬虫仅覆盖智联招聘和猎聘两个平台，未达成多平台全覆盖目标
6. 技术博客仅覆盖英文 RSS 源，缺少 CSDN / 知乎等中文技术社区
7. evidence_score 为算法估算（基础分 0.70 + 字段加权），非真实可信度
8. time_slice 全部为同一季度，不支持时间演化分析

---

## 五、数据使用建议

### 明确可以声称的
- "爬虫采集了 4,373 条真实岗位数据，来自智联招聘（2,720 条）和猎聘（1,653 条）"
- "通过 GitHub API 采集了 389 个开源项目的技术栈数据"
- "通过 arXiv API 采集了 359 篇 AI 领域前沿论文"
- "构建了包含 545 个标准技能的技能本体，涵盖 10 大技术方向"

### 必须加限定词的
- "原始评估样本由规则生成（50 条岗位 + 50 份简历 + 100 条匹配对 + 50 条负样本）"
- "经过人工复核后形成 reviewed 版本（100 条岗位 + 50 份简历 + 100 条匹配对 + 50 条负样本，共 300 条），可用于系统原型阶段评估"
- "整理了 **参考性** 课程体系（384 门）和证书体系（101 项）"（不可说"真实课程数据"）
- "合成了 60 份 **模拟** 简历用于系统功能测试"（不可说"真实人才数据"）

### 不建议声称的
- ❌ "多平台覆盖" — 仅 2 个招聘平台
- ❌ "所有评估数据均为人工标注" — 原始评估数据为程序生成，reviewed 版本为人工复核（非从零标注）
- ❌ "完整字段" — JD 数据 description/requirements 未分离，industry/time 缺失
- ❌ "百万级数据" — 总数约 8,500 条
- ❌ "真实课程/证书数据" — 为模板生成

---

## 六、附表：完整文件清单

| # | 文件路径 | 数量 | 类型 | 真实爬取 | 合成 | 可展示 | 需说明限制 |
|---|----------|------|------|----------|------|--------|------------|
| 1 | data/raw/jd_raw.csv | 4,373 | real_crawled | ✅ | ❌ | ✅ | ✅ |
| 2 | data/raw/github_trend.jsonl | 389 | public_api | ✅ | ❌ | ✅ | ❌ |
| 3 | data/raw/github_detail.jsonl | 389 | public_api | ✅ | ❌ | ✅ | ❌ |
| 4 | data/raw/arxiv_trend.jsonl | 359 | public_api | ✅ | ❌ | ✅ | ❌ |
| 5 | data/raw/blog_trend.jsonl | 857 | public_api | ✅ | ❌ | ✅ | ✅ |
| 6 | data/raw/tech_trend.jsonl | 973 | processed | ❌ | ❌ | ⚠️ | ✅ |
| 7 | data/raw/github_raw.jsonl | 120 | public_api | ✅ | ❌ | ⚠️ | ✅ |
| 8 | data/raw/resume_raw.jsonl | 180 | 混合(API+合成) | ⚠️ | ⚠️ | ⚠️ | ✅ |
| 9 | data/clean/jd_clean.csv | 2,500 | processed | ⚠️ | ❌ | ✅ | ✅ |
| 10 | data/clean/resume_clean.csv | 180 | processed | ⚠️ | ⚠️ | ⚠️ | ✅ |
| 11 | data/clean/skill_candidates.csv | 519 | processed | ❌ | ❌ | ✅ | ❌ |
| 12 | data/clean/skill_clean.csv | 1 | 占位 | ❌ | ❌ | ❌ | ✅ |
| 13 | data/meta/skill_ontology.json | 519 | processed | ❌ | ❌ | ✅ | ❌ |
| 14 | data/meta/job_standard_dict.csv | 37 | rule_generated | ❌ | ❌ | ✅ | ❌ |
| 15 | data/meta/gold_jd_set.json | 50 | rule_generated | ❌ | ✅ | ⚠️ | ✅ |
| 16 | data/meta/gold_resume_set.json | 50 | synthetic | ❌ | ✅ | ⚠️ | ✅ |
| 17 | data/meta/match_label_set.json | 100 | rule_generated | ❌ | ✅ | ⚠️ | ✅ |
| 18 | data/meta/negative_samples.json | 50 | rule_generated | ❌ | ✅ | ⚠️ | ✅ |
| 19 | data/meta/talent_profile.json | — | processed | ❌ | ❌ | ✅ | ❌ |
| 20 | data/education/course_data.csv | 384 | template_generated | ❌ | ✅ | ⚠️ | ✅ |
| 21 | data/education/certificate_data.csv | 101 | template_generated | ❌ | ✅ | ⚠️ | ✅ |
| 22 | data/meta/gold_jd_set_reviewed.json | 100 | manual_reviewed | ❌ | ❌ | ✅ | ✅ |
| 23 | data/meta/gold_resume_set_reviewed.json | 50 | manual_reviewed | ❌ | ⚠️ | ✅ | ✅ |
| 24 | data/meta/match_label_set_reviewed.json | 100 | manual_reviewed | ❌ | ❌ | ✅ | ✅ |
| 25 | data/meta/negative_samples_reviewed.json | 50 | manual_reviewed | ❌ | ❌ | ✅ | ✅ |

> 图例：✅ = 是/可 | ❌ = 否/不可 | ⚠️ = 有条件的/需注意 | `—` = 不适用

---

> **报告结论**：整体数据资产中，约 **73% 的记录来自真实爬取或公开 API**（6,606 条），可用于比赛展示需加说明。**约 27% 的记录为模板生成、合成或规则生成**（约 795 条），在比赛展示中必须明确标注来源，不可混称为真实数据。评估数据分层管理：原始规则生成文件（237 条）保留可追溯性，人工复核 reviewed 文件（300 条）可用于系统原型阶段评估，但规模为原型验证级别，不应夸大为大规模工业标注集。
