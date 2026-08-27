# Crawler Module

TalentGraph 多源异构数据采集模块。

## 目录结构

```
crawler/
├── main.py              # 统一入口
├── requirements.txt     # Python 依赖
├── config/              # 配置
│   ├── settings.py      # 通用配置 (请求间隔/超时/字段定义)
│   └── urls.py          # 待爬取 URL
├── spiders/             # 爬虫
│   ├── greenhouse_spider.py  # Greenhouse 企业招聘
│   ├── company_spider.py     # 企业官网招聘
│   ├── github_spider.py      # GitHub 技术趋势
│   └── tech_spider.py        # 技术博客/趋势
├── utils/               # 工具
│   ├── request_utils.py      # HTTP 请求封装
│   ├── save_utils.py         # CSV/JSONL 保存
│   ├── clean_utils.py        # 数据清洗
│   └── skill_mapping.py      # 技能映射
└── data/                # 数据
    ├── raw/             # 原始采集数据
    ├── clean/           # 清洗后数据
    └── meta/            # 元数据 (技能本体/岗位字典)
```

## 运行

```bash
cd crawler
pip install -r requirements.txt
python main.py                    # 全部爬虫
python main.py --spider greenhouse  # 单个爬虫
```

## R01 多源持续采集

统一入口会为每次采集生成不可变批次、增量状态和质量报告，并补充
`crawl_batch_id`、`content_hash`、`first_seen_at`、`last_seen_at`、
`source_published_at`、`crawled_at` 等审计字段。

```bash
# 推荐先离线验证：读取仓库已有原始数据，不发送网络请求
python scripts/run_collection.py --from-existing --sources github,arxiv,blog

# 在线调用现有官方 API/RSS 采集器
python scripts/run_collection.py --sources github,arxiv,blog

# 采集 Greenhouse 公开 ATS 岗位
python scripts/run_collection.py --sources greenhouse

# 从企业官方公开 ATS 采集约 500 条技术岗位，直接合并到岗位主 CSV
python scripts/collect_company_jobs.py --target 500

# 国家大学生就业服务平台公开技术岗位，直接合并到岗位主 CSV
python scripts/collect_ncss_jobs.py --target 1000

# Arbeitnow + Remotive 官方公开 API 技术岗位
python scripts/collect_remote_job_boards.py --arbeitnow-target 500

# 人工导入企业授权的 CSV/JSON/JSONL
python scripts/run_collection.py --import-file company_jobs.csv \
  --import-source company-career-site --data-type job
```

输出目录：

```text
data/collection/
├── batches/   # 每次采集的不可变 JSONL 快照
├── state/     # 每个来源的最新状态，用于增量识别
└── reports/   # 每次任务的数量和质量 JSON 报告
```

记录状态：

- `inserted`：第一次发现；
- `updated`：同一来源记录内容发生变化；
- `unchanged`：本批次再次出现但内容未变化；
- `rejected`：既没有来源 URL，也没有可用内容。

在线采集应遵守目标站点服务条款、robots 规则、访问频率与数据许可。
招聘平台如无明确授权，优先使用企业官网、公开 ATS API 或人工导入。

运行采集层测试：

```bash
python -m unittest crawler.tests.test_collection_pipeline -v
```

## 数据字段 (JD 标准)

job_title, standard_job_name, company, industry, location, salary,
education, experience, description, requirements, publish_time,
source_url, crawl_time, skill_raw, skill_standard, time_slice,
evidence_score, duplicate_score

岗位主表已升级为 v2。除上述兼容字段外，还包含来源岗位 ID、标准岗位实体 ID、
版本有效期、原始正文、必备/加分/提及技能、逐技能证据 JSON、企业性质、统计口径、
数据来源类型和生命周期。英文岗位的 `statistics_scope` 固定为
`overseas_reference`，不会进入中国地区主统计。

迁移并补全腾讯、中国信通院和中国电信三个官方来源：

```bash
python scripts/enrich_jd_dataset.py --online
```

脚本会先备份 `jd_clean.csv`，不新增岗位；质量结果写入
`data/report/jd_quality_report.json`。

## GitHub 技术趋势 v2

仓库主表使用 GitHub 仓库 ID 去重，明确区分创建、元数据更新、代码推送和
本地观测时间。API 原始响应、查询批次、周快照和热度结果分别保存。

```bash
# GitHub 查询、主表、周快照和少量 activity 补采
python spiders/tech/github_trend_spider.py --pages 1 --activity-limit 10

# 按 API 限额分批刷新旧URL；配置 GITHUB_TOKEN 后可提高 limit
python scripts/refresh_github_legacy.py --limit 10

# 国内 Gitee 官方项目，指标独立保存
python spiders/tech/gitee_trend_spider.py

# 构建可复算热度；增长率至少需要两个不同周快照
python scripts/build_github_hotness.py
python scripts/validate_github_trend_v2.py
```

严禁运行旧式随机补值逻辑。`fix_github_detail.py` 已停用；API没有公开的字段
保持为空。GitHub 与 Gitee 的 stars/forks 不跨平台直接相加。
