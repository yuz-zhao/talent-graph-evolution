from crawler.utils.skill_mapping import identify_skills


def standards(text: str) -> list[str]:
    return identify_skills(text)[1]


def test_english_stack_and_short_word_context():
    result = standards("Go backend engineer using Kubernetes, PostgreSQL, Kafka and CI/CD.")
    assert {"Golang", "Kubernetes", "PostgreSQL", "Kafka", "CI/CD"} <= set(result)


def test_ai_english_aliases_are_standardized():
    result = standards("Build RAG and AI agent applications with LLMs, PyTorch and LangChain.")
    assert {"检索增强生成", "AI智能体", "大语言模型", "PyTorch", "LangChain"} <= set(result)


def test_symbol_languages():
    result = standards("Develop services in C++, C# and .NET Core with SQL Server.")
    assert {"C/C++", "C#", ".NET", "SQL Server"} <= set(result)


def test_chinese_industrial_skills():
    result = standards("负责PLC编程、自动化控制、STM32嵌入式开发及CAN总线通信。")
    assert {"PLC", "自动化控制", "STM32", "嵌入式开发", "CAN总线"} <= set(result)


def test_does_not_match_ambiguous_business_words():
    result = standards("Regional sales manager for digital health and talent acquisition agents.")
    assert not ({"Git", "AI智能体", "Golang", "R语言"} & set(result))


def test_microsoft_365_english_job():
    assert "Microsoft 365" in standards("Modern Workplace Consultant for Microsoft 365 and Azure cloud.")


def test_generic_technical_roles_keep_domain_skill():
    result = standards("Software Engineer for autonomous driving and data architecture")
    assert {"软件工程", "自动驾驶", "数据架构"} <= set(result)


def test_fifty_chinese_skill_regression_cases():
    cases = [
        ("负责Python后端开发", "Python"), ("建设Java微服务", "Java"), ("使用Vue.js开发前端", "Vue.js"),
        ("维护PostgreSQL数据库", "PostgreSQL"), ("使用Redis缓存", "Redis"), ("建设Kafka消息平台", "Kafka"),
        ("负责数据分析", "数据分析"), ("开展统计分析", "统计分析"), ("建设数据仓库", "数据仓库"),
        ("实施数据治理", "数据治理"), ("保障数据质量", "数据质量"), ("开发实时计算任务", "实时计算"),
        ("开展机器学习建模", "机器学习"), ("负责深度学习算法", "深度学习"), ("研究自然语言处理", "自然语言处理"),
        ("开发计算机视觉系统", "计算机视觉"), ("构建大语言模型应用", "大语言模型"), ("建设检索增强生成系统", "检索增强生成"),
        ("开发AI智能体平台", "AI智能体"), ("建设知识图谱", "知识图谱"), ("优化推荐系统", "推荐系统"),
        ("使用PyTorch训练模型", "PyTorch"), ("基于TensorFlow开发", "TensorFlow"), ("使用OpenCV处理图像", "OpenCV"),
        ("负责模型微调", "模型微调"), ("负责模型部署", "模型部署"), ("建设云计算平台", "云计算"),
        ("使用Docker容器化", "Docker"), ("维护Kubernetes集群", "Kubernetes"), ("负责Linux系统运维", "Linux"),
        ("建设CI/CD流水线", "CI/CD"), ("使用Jenkins持续集成", "Jenkins"), ("使用Terraform管理基础设施", "Terraform"),
        ("建设网络安全体系", "网络安全"), ("开展渗透测试", "渗透测试"), ("执行安全审计", "安全审计"),
        ("负责自动化测试", "自动化测试"), ("开展性能测试", "性能测试"), ("使用Playwright测试", "Playwright"),
        ("负责嵌入式开发", "嵌入式开发"), ("开发物联网平台", "物联网"), ("进行PLC编程", "PLC"),
        ("开发STM32设备", "STM32"), ("维护CAN总线通信", "CAN总线"), ("建设5G移动通信网络", "5G移动通信"),
        ("研究6G通信技术", "6G通信"), ("负责边缘计算平台", "边缘计算"), ("建设工业互联网", "工业互联网"),
        ("开发数字孪生系统", "数字孪生"), ("推进智能制造", "智能制造"),
    ]
    assert len(cases) >= 50
    failures = [(text, expected, standards(text)) for text, expected in cases if expected not in standards(text)]
    assert failures == []
