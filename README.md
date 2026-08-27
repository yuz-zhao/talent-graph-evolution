# TalentGraph Evolution

TalentGraph Evolution 是一套面向数字经济岗位分析与人才能力评估的应用系统。项目将岗位数据、简历信息和技能关系组织为可查询的知识图谱，并提供人岗匹配、能力差距诊断、岗位演化分析、学习路径建议和 GraphRAG 证据解释。

项目同时包含管理员端和用户端：管理员负责数据接入、图谱构建、质量检查与系统监测；普通用户可以维护个人画像、解析简历、查看岗位推荐和生成能力提升计划。

## 主要功能

- 多来源岗位数据导入、清洗和质量检查
- 岗位、技能、人才及其关系的知识图谱构建
- 简历解析、人才画像和人岗匹配诊断
- 新兴岗位识别与岗位能力演化分析
- 基于证据的 GraphRAG 检索与回答
- 学习路径生成、执行反馈与能力提升闭环
- 管理端运行指标、数据质量和合规审计

## 技术栈

- 前端：Vue 3、Vite、Pinia、Tailwind CSS、Chart.js、ECharts
- API：Node.js、Express
- 关系数据：PostgreSQL
- 图数据：Neo4j
- 向量检索：Qdrant
- 部署：Docker、Docker Compose、Nginx

## 推荐方式：Docker 一键部署

### 1. 环境要求

- Windows 10/11、Linux 或 macOS
- Docker Desktop 4.x，或 Docker Engine 24+
- Docker Compose v2
- 建议至少 4 核 CPU、8 GB 内存和 15 GB 可用磁盘空间

### 2. 创建本地配置

PowerShell：

```powershell
Copy-Item .env.docker.example .env.docker
```

Bash：

```bash
cp .env.docker.example .env.docker
```

打开 `.env.docker`，至少修改以下三项：

```env
PGPASSWORD=请设置新的PostgreSQL密码
NEO4J_PASSWORD=请设置新的Neo4j密码
JWT_SECRET=请填写长度不少于32个字符的随机字符串
```

`DEEPSEEK_API_KEY` 等 AI 服务配置是可选项。未配置时，系统仍可使用证据约束的降级能力。

### 3. 校验并启动

```bash
docker compose --env-file .env.docker -f docker-compose.yml config --quiet
docker compose --env-file .env.docker -f docker-compose.yml up -d --build
```

首次启动会构建镜像、创建数据库并导入随项目提供的数据，所需时间取决于机器配置和网络速度。

### 4. 验收

```bash
npm run docker:e2e
```

也可以手工检查：

- Web 页面：<http://localhost:8080>
- API 健康检查：<http://localhost:8080/api/health>
- API 直连地址：<http://localhost:3001>
- Neo4j Browser：<http://localhost:7474>
- Qdrant：<http://localhost:6333>

查看容器状态和日志：

```bash
docker compose --env-file .env.docker -f docker-compose.yml ps
docker compose --env-file .env.docker -f docker-compose.yml logs --tail=200
```

停止服务但保留数据：

```bash
docker compose --env-file .env.docker -f docker-compose.yml down
```

更完整的环境变量、数据备份、更新回滚和故障排查说明见 [Docker 一键部署说明](docs/Docker一键部署说明.md)。

## 本地开发

本地开发需要 Node.js 20+ 和 npm。数据库服务可由 Docker 单独启动，前端与 API 在宿主机运行，便于热更新和调试。

```bash
npm install
Copy-Item .env.docker.example .env.docker
npm run docker:up
npm run dev
```

Windows 用户也可以运行：

```powershell
.\start-dev.bat
```

本地开发默认地址：

- 前端：<http://127.0.0.1:5173/signin>
- API 健康检查：<http://127.0.0.1:3001/api/health>

生产构建命令：

```bash
npm run build
```

构建产物位于 `dist/`。

## 测试与质量检查

```bash
# 后端测试
npm run test:server

# 前端测试
npm run test:web

# 完整覆盖率检查
npm run test:coverage

# 图谱契约与数据结构检查
npm run audit:graph

# UTF-8 编码检查
npm run audit:utf8
```

其他专项测试、评估和数据校验命令可在 `package.json` 的 `scripts` 中查看。

## 目录说明

```text
├─ src/                  前端页面、组件和状态管理
├─ server/               Express API、业务逻辑和后端测试
├─ crawler/              岗位数据处理、标注与评估脚本
├─ knowledge_graph/      图谱构建、导入与质量检查
├─ database/             PostgreSQL 初始化和数据导入
├─ docker/               Nginx 等容器配置
├─ docs/                 设计、部署和提交说明
├─ scripts/              测试、审计和辅助脚本
├─ docker-compose.yml    完整应用编排
└─ .env.docker.example   可提交的环境变量模板
```

## 提交与安全说明

作品包中应保留 Dockerfile、Compose 编排文件、Nginx 配置、`.env.docker.example` 和部署说明，以便评审复现运行环境。

以下内容不要提交到作品包或代码仓库：

- `.env`、`.env.docker` 等本地配置
- PostgreSQL、Neo4j 的真实密码
- JWT 密钥、API Key 和生产账号
- 未脱敏的真实简历或其他个人信息
- `node_modules`、日志、缓存、临时文件和上传文件

评审部署时，应复制 `.env.docker.example` 生成自己的 `.env.docker`，再填写本地密码和密钥。项目的 `.gitignore` 与 `.dockerignore` 已对常见敏感文件和无关目录进行排除。

## 编码说明

源码统一使用 UTF-8。Windows PowerShell 显示中文乱码时，可先执行：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

