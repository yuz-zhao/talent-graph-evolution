"""
待爬取 URL 配置 — 中文优先 + 英文补充

说明：
1. 国内岗位优先放在 CHINESE_COMPANY_LIST_URLS / CHINESE_COMPANY_JOB_URLS / CHINESE_PUBLIC_JOB_URLS。
2. 英文 Greenhouse 数据保留，作为补充数据源。
3. 如果某些国内网站需要登录、验证码或强 JS 渲染，先跳过，不要强行爬。
4. 企业招聘列表页适合批量抓取；具体岗位详情页适合先测试。
"""

# ============================================================
# 国内企业招聘列表页
# 程序会先从这些页面提取岗位详情链接，再逐个解析
# ============================================================

CHINESE_COMPANY_LIST_URLS = [
    # 百度招聘：社会招聘列表
    "https://talent.baidu.com/jobs/social-list",

    # 美团招聘：首页/职位入口
    "https://zhaopin.meituan.com/",

    # 腾讯招聘：工作机会
    "https://careers.tencent.com/jobopportunity.html",

    # 阿里巴巴集团社会招聘职位列表
    "https://talent-holding.alibaba.com/off-campus/position-list",

    # 阿里巴巴集团招聘官网
    "https://job.alibaba.com/",

    # 阿里云社会招聘
    "https://careers.aliyun.com/off-campus/home",

    # 字节跳动社招
    "https://jobs.bytedance.com/experienced/product",

    # 字节跳动社招移动端入口
    "https://jobs.bytedance.com/experienced/m/",

    # 华为招聘官网
    "https://career.huawei.com/cn",

    # 华为校招职位列表
    "https://career.huawei.com/cn/campus-recruitment-job-list",
]


# ============================================================
# 国内企业官网具体岗位详情页
# 这里放“单个具体岗位页面”，适合先测试
# 示例：
# CHINESE_COMPANY_JOB_URLS = [
#     "https://talent.baidu.com/jobs/detail/xxx",
# ]
# ============================================================

CHINESE_COMPANY_JOB_URLS = [
    # 先留空
    # 你后面可以把具体岗位详情页复制到这里
]


# ============================================================
# 中文公开招聘平台具体岗位详情页
# 比如 BOSS、智联、猎聘、拉勾的公开岗位详情页
# 注意：如果遇到登录、验证码、反爬，就先跳过
# 示例：
# CHINESE_PUBLIC_JOB_URLS = [
#     "https://www.zhipin.com/job_detail/xxx.html",
# ]
# ============================================================

CHINESE_PUBLIC_JOB_URLS = [
    # 先留空
]


# ============================================================
# 国内技术岗位关键词
# 用于从企业招聘列表页里筛选技术岗位链接
# ============================================================

DOMESTIC_JOB_KEYWORDS = [
    "人工智能",
    "AI",
    "AIGC",
    "大模型",
    "大语言模型",
    "LLM",
    "RAG",
    "检索增强生成",
    "智能体",
    "Agent",
    "算法工程师",
    "机器学习",
    "深度学习",
    "自然语言处理",
    "NLP",
    "知识图谱",
    "推荐系统",
    "计算机视觉",
    "多模态",
    "数据分析",
    "数据开发",
    "大数据",
    "数据仓库",
    "数据湖",
    "Java开发",
    "Java工程师",
    "Python开发",
    "Python工程师",
    "后端开发",
    "前端开发",
    "全栈开发",
    "云计算",
    "云原生",
    "DevOps",
    "运维开发",
    "测试开发",
    "安全工程师",
    "网络安全",
    "架构师",
    "研发工程师",
    "软件工程师",
]


# ============================================================
# 中文 URL 汇总
# ============================================================

ALL_CHINESE_URLS = {
    "zh_company_list": CHINESE_COMPANY_LIST_URLS,
    "zh_company_job": CHINESE_COMPANY_JOB_URLS,
    "zh_public_job": CHINESE_PUBLIC_JOB_URLS,
}


# ============================================================
# 兼容旧版 main.py / 爬虫代码的配置
# 有些旧代码可能会读取 ALL_JOB_URLS
# ============================================================

ALL_JOB_URLS = {
    "zh_company_list": CHINESE_COMPANY_LIST_URLS,
    "zh_company_job": CHINESE_COMPANY_JOB_URLS,
    "zh_public_job": CHINESE_PUBLIC_JOB_URLS,
    "en_ats": [],
}


# ============================================================
# 企业官网招聘入口字典
# 兼容 company_spider.py 里的 COMPANY_CAREER_URLS
# ============================================================

COMPANY_CAREER_URLS = {
    "baidu": "https://talent.baidu.com/jobs/social-list",
    "meituan": "https://zhaopin.meituan.com/",
    "tencent": "https://careers.tencent.com/jobopportunity.html",
    "alibaba": "https://talent-holding.alibaba.com/off-campus/position-list",
    "aliyun": "https://careers.aliyun.com/off-campus/home",
    "bytedance": "https://jobs.bytedance.com/experienced/product",
    "huawei": "https://career.huawei.com/cn",
}


# ============================================================
# 英文 ATS 招聘页
# 说明：
# 这些是英文补充数据，不删除。
# 中文岗位排序时会排在英文岗位前面。
# ============================================================

ENGLISH_ATS_JOB_URLS = [
    "https://job-boards.greenhouse.io/gitlab/jobs/8503792002",
]


# ============================================================
# Greenhouse 企业招聘 API
# 当前已有 400 条左右英文岗位主要来自这些 API
# 保留，作为英文补充数据源
# ============================================================

GREENHOUSE_BOARDS = {
    "gitlab": "https://api.greenhouse.io/v1/boards/gitlab/jobs?content=true",
    "datadog": "https://api.greenhouse.io/v1/boards/datadog/jobs?content=true",
    "cloudflare": "https://api.greenhouse.io/v1/boards/cloudflare/jobs?content=true",
    "mongodb": "https://api.greenhouse.io/v1/boards/mongodb/jobs?content=true",
    "figma": "https://api.greenhouse.io/v1/boards/figma/jobs?content=true",
    "grafanalabs": "https://api.greenhouse.io/v1/boards/grafanalabs/jobs?content=true",
    "reddit": "https://api.greenhouse.io/v1/boards/reddit/jobs?content=true",
    "elastic": "https://api.greenhouse.io/v1/boards/elastic/jobs?content=true",
    "airbnb": "https://api.greenhouse.io/v1/boards/airbnb/jobs?content=true",
    "roblox": "https://api.greenhouse.io/v1/boards/roblox/jobs?content=true",
    # 第二批：自动驾驶、硬件、云安全、数据基础设施与基础软件企业
    "scaleai": "https://api.greenhouse.io/v1/boards/scaleai/jobs?content=true",
    "andurilindustries": "https://api.greenhouse.io/v1/boards/andurilindustries/jobs?content=true",
    "samsara": "https://api.greenhouse.io/v1/boards/samsara/jobs?content=true",
    "okta": "https://api.greenhouse.io/v1/boards/okta/jobs?content=true",
    "fastly": "https://api.greenhouse.io/v1/boards/fastly/jobs?content=true",
    "waymo": "https://api.greenhouse.io/v1/boards/waymo/jobs?content=true",
    "stripe": "https://api.greenhouse.io/v1/boards/stripe/jobs?content=true",
    "coinbase": "https://api.greenhouse.io/v1/boards/coinbase/jobs?content=true",
    "lyft": "https://api.greenhouse.io/v1/boards/lyft/jobs?content=true",
    "instacart": "https://api.greenhouse.io/v1/boards/instacart/jobs?content=true",
    "doordashusa": "https://api.greenhouse.io/v1/boards/doordashusa/jobs?content=true",
    "canonical": "https://api.greenhouse.io/v1/boards/canonical/jobs?content=true",
    "spacex": "https://api.greenhouse.io/v1/boards/spacex/jobs?content=true",
}


# ============================================================
# GitHub API
# 用于技术趋势 / 开源项目数据
# ============================================================

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"


# ============================================================
# 技术博客 RSS
# 用于技术趋势数据
# ============================================================

TECH_RSS_FEEDS = {
    "huggingface": "https://huggingface.co/blog/feed.xml",
}
