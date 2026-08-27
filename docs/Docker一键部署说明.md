# TalentGraph Evolution 容器化部署说明

文档版本：V1.0  
适用范围：开发联调、赛题验收、单机演示和服务器部署  
默认访问地址：`http://localhost:8080`

## 1. 交付材料

仓库已包含完整容器化部署材料：

| 文件 | 用途 |
| --- | --- |
| `Dockerfile.web` | 构建 Vue 3 前端，并由 Nginx 提供静态页面与 `/api` 反向代理 |
| `server/Dockerfile` | 构建 Node.js API，包含 PDF 文本提取、Poppler 和 Tesseract OCR 运行环境 |
| `database/Dockerfile.importer` | 执行 PostgreSQL 迁移、金标数据导入和数据校验 |
| `docker-compose.yml` | 启动 PostgreSQL、Neo4j、Qdrant、数据导入、API 和 Web 全栈服务 |
| `docker-compose.data.yml` | 仅启动 PostgreSQL、Qdrant 和导入任务，供本地前后端开发使用 |
| `docker/nginx.conf` | 单页应用路由、API 代理、上传大小和超时配置 |
| `.env.docker.example` | 容器环境变量模板，不包含真实密码 |
| `.dockerignore` | 排除密钥、日志、依赖、临时文件和非必要数据 |
| `scripts/docker-e2e-smoke.mjs` | 验证 Web、API 代理和公共数据接口 |

## 2. 部署架构

```text
浏览器
  │  HTTP/HTTPS
  ▼
Web / Nginx :8080
  ├─ Vue 静态资源
  └─ /api/* ──────────────► API / Node.js :3001
                                ├─ PostgreSQL :5432  业务数据、用户、审计和事实快照
                                ├─ Neo4j :7687       岗位、技能、证据和演化关系
                                ├─ Qdrant :6333      证据向量与语义检索
                                └─ uploads volume    用户上传的简历文件

一次性任务：
  import-gold  ─► 数据库迁移、金标/参考数据导入、PostgreSQL 校验
  import-neo4j ─► 当前图谱和编码修复脚本导入 Neo4j
```

`import-gold` 和 `import-neo4j` 成功执行后显示为 `Exited (0)` 属于正常状态。API 会等待两个导入任务成功完成，并等待 Qdrant 健康后再启动。

## 3. 环境要求

### 3.1 软件

- Windows 10/11、Linux 或 macOS。
- Docker Desktop 4.x，或 Docker Engine 24+。
- Docker Compose V2，执行 `docker compose version` 应能返回版本信息。
- 首次部署需要访问镜像仓库和 npm 软件源。

### 3.2 资源

| 场景 | CPU | 内存 | 可用磁盘 |
| --- | ---: | ---: | ---: |
| 最低演示环境 | 4 核 | 8 GB | 15 GB |
| 推荐验收环境 | 8 核 | 16 GB | 30 GB |
| 数据扩展环境 | 8 核以上 | 32 GB以上 | 按图谱、向量和备份规模规划 |

Docker Desktop 建议至少分配 8 GB 内存。Neo4j 默认使用 512 MB 初始堆和 1 GB 最大堆；数据规模扩大后应同步调整 Compose 中的内存参数。

## 4. 首次完整部署

### 4.1 获取代码并进入目录

```bash
git clone <项目仓库地址>
cd talent-graph-evolution
```

如果使用赛题离线压缩包，解压后直接进入包含 `docker-compose.yml` 的目录。

### 4.2 创建环境变量文件

PowerShell：

```powershell
Copy-Item .env.docker.example .env.docker
```

Bash：

```bash
cp .env.docker.example .env.docker
```

编辑 `.env.docker`，至少替换以下三项：

```dotenv
PGPASSWORD=<强 PostgreSQL 密码>
NEO4J_PASSWORD=<强 Neo4j 密码>
JWT_SECRET=<不少于 32 个字符的随机字符串>
```

可使用以下方式生成 JWT 密钥：

```bash
openssl rand -hex 32
```

Windows 没有 OpenSSL 时，可使用密码管理器生成 64 位随机字符串。不要把 `.env.docker` 提交到 Git，也不要放进提交材料或截图。

### 4.3 校验 Compose

```bash
docker compose --env-file .env.docker -f docker-compose.yml config --quiet
```

命令无输出且退出码为 0 表示语法和必填变量通过校验。

### 4.4 构建并启动

```bash
docker compose --env-file .env.docker -f docker-compose.yml up -d --build
```

也可以使用项目脚本：

```bash
npm run docker:full:up
```

首次构建会下载 Node.js、Python、Nginx、PostgreSQL、Neo4j 和 Qdrant 镜像，并安装项目依赖，耗时取决于网络和磁盘速度。

### 4.5 查看启动过程

```bash
docker compose --env-file .env.docker -f docker-compose.yml ps
docker compose --env-file .env.docker -f docker-compose.yml logs -f --tail=200
```

重点检查：

- `postgres`、`neo4j`、`qdrant`、`api` 和 `web` 为 `running` 或 `healthy`。
- `import-gold` 和 `import-neo4j` 为 `Exited (0)`。
- API 日志中没有数据库认证、迁移或图谱导入失败信息。

按 `Ctrl+C` 只会退出日志跟随，不会停止容器。

## 5. 访问地址与端口

| 服务 | 默认地址 | 用途 |
| --- | --- | --- |
| TalentGraph Web | `http://localhost:8080` | 用户端和管理端统一入口 |
| API 健康检查 | `http://localhost:8080/api/health` | 经 Nginx 代理检查 API |
| Web 健康检查 | `http://localhost:8080/healthz` | 检查 Nginx |
| API 直连 | `http://localhost:3001` | 本机调试，不建议公网暴露 |
| Neo4j Browser | `http://localhost:7474` | 图谱调试和验收 |
| PostgreSQL | `localhost:5433` | 数据库管理工具连接 |
| Qdrant | `http://localhost:6333` | 向量服务接口 |

修改外部端口时，只改 `.env.docker`：

```dotenv
WEB_PORT=8080
API_PORT_HOST=3001
PGPORT_HOST=5433
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
```

容器间通信使用服务名和容器端口，不随宿主机映射端口变化。

## 6. 环境变量说明

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `PGDATABASE` | 是 | PostgreSQL 数据库名 |
| `PGUSER` | 是 | PostgreSQL 用户 |
| `PGPASSWORD` | 是 | PostgreSQL 密码 |
| `NEO4J_USER` | 是 | Neo4j 用户，默认 `neo4j` |
| `NEO4J_PASSWORD` | 是 | Neo4j 密码 |
| `JWT_SECRET` | 是 | JWT 签名密钥，不少于 32 个字符 |
| `CORS_ORIGIN` | 建议 | API 直连时允许的浏览器来源，例如 `https://talent.example.com` |
| `QDRANT_COLLECTION` | 否 | 证据向量集合名 |
| `DEEPSEEK_API_KEY` | 否 | 外部大模型密钥；不配置时使用证据约束降级能力 |
| `DEEPSEEK_BASE_URL` | 否 | OpenAI 兼容接口地址 |
| `DEEPSEEK_MODEL` | 否 | 模型名称 |
| `EMBEDDING_URL` | 否 | 外部向量服务地址 |

容器内固定变量：

- `TESSERACT_PATH=/usr/bin/tesseract`
- `PDFTOPPM_PATH=/usr/bin/pdftoppm`
- `PGHOST=postgres`
- `NEO4J_URI=bolt://neo4j:7687`
- `QDRANT_URL=http://qdrant:6333`

## 7. 部署验收

### 7.1 自动冒烟测试

```bash
npm run docker:e2e
```

该命令验证：

1. Web 首页返回 Vue 应用。
2. `/api/health` 能经 Nginx 反向代理访问。
3. 公共数据状态接口返回有效 JSON。

如修改了 Web 端口：

PowerShell：

```powershell
$env:TALENTGRAPH_URL='http://127.0.0.1:新端口'
npm run docker:e2e
```

Bash：

```bash
TALENTGRAPH_URL=http://127.0.0.1:新端口 npm run docker:e2e
```

### 7.2 手工验收

- 打开 Web 首页和登录页，确认静态资源没有 404。
- 上传一份小于 10 MB 的 PDF 或 Word 简历，确认解析状态完成。
- 对扫描版 PDF 验证 OCR；API 镜像已包含 Poppler 和 Tesseract，并使用仓库中的中英文语言数据。
- 打开岗位探索和匹配详情，确认岗位、技能、分项得分与证据正常显示。
- 打开管理端数据源、图谱和新岗位页面，确认数据健康状态与审核流程可见。
- 在 Neo4j Browser 执行 `MATCH (n) RETURN count(n);`，确认图谱已导入。

## 8. 日常运维

### 查看状态

```bash
docker compose --env-file .env.docker -f docker-compose.yml ps
```

### 查看单个服务日志

```bash
docker compose --env-file .env.docker -f docker-compose.yml logs -f --tail=200 api
docker compose --env-file .env.docker -f docker-compose.yml logs -f --tail=200 web
docker compose --env-file .env.docker -f docker-compose.yml logs -f --tail=200 postgres
```

### 重启应用层

```bash
docker compose --env-file .env.docker -f docker-compose.yml restart api web
```

### 停止并保留数据

```bash
docker compose --env-file .env.docker -f docker-compose.yml down
```

不要在常规停止、升级或故障处理时添加 `-v`。`down -v` 会永久删除数据库、图谱、向量和上传文件卷。

### 重新构建代码

```bash
docker compose --env-file .env.docker -f docker-compose.yml up -d --build api web
```

修改数据库迁移、导入数据或图谱脚本后，执行：

```bash
docker compose --env-file .env.docker -f docker-compose.yml up --build import-gold import-neo4j
docker compose --env-file .env.docker -f docker-compose.yml up -d api web
```

## 9. 数据持久化与备份

Compose 使用四个命名卷：

| 卷 | 数据 |
| --- | --- |
| `talentgraph_pgdata` | PostgreSQL 数据 |
| `talentgraph_neo4j_data` | Neo4j 图谱 |
| `talentgraph_qdrant_data` | Qdrant 向量 |
| `talentgraph_uploads` | 用户上传文件 |

实际卷名通常带 Compose 项目前缀，可用以下命令确认：

```bash
docker volume ls
docker compose --env-file .env.docker -f docker-compose.yml config --volumes
```

### PostgreSQL 逻辑备份

先创建本地 `backups` 目录，再执行：

```bash
docker compose --env-file .env.docker -f docker-compose.yml exec -T postgres pg_dump -U talentgraph -d talentgraph_dev --clean --if-exists > backups/postgres.sql
```

如果修改了 `PGUSER` 或 `PGDATABASE`，同步替换命令中的用户和数据库名。

恢复前应停止 API 写入，并先在测试环境验证备份：

```bash
docker compose --env-file .env.docker -f docker-compose.yml exec -T postgres psql -U talentgraph -d talentgraph_dev < backups/postgres.sql
```

Neo4j、Qdrant 和上传卷应使用宿主机或云平台的卷快照能力备份。生产环境至少执行每日备份，并定期做恢复演练。只保存压缩包而不验证恢复，不算有效备份。

## 10. 服务器与生产环境建议

当前 Compose 为单机验收方案，默认映射数据库和中间件端口，方便评委检查。公网部署时应调整：

1. 公网只开放 80/443，数据库、Neo4j、Qdrant 和 API 直连端口只允许内网或运维白名单访问。
2. 在 Web 容器前部署 Caddy、Nginx、Traefik 或云负载均衡，配置可信 TLS 证书。
3. 将 `CORS_ORIGIN` 设置为实际 HTTPS 域名。
4. 密钥使用部署平台 Secret、Docker Secret 或受控环境变量注入，不写进镜像和 Git。
5. 为宿主机、数据库卷和备份目录配置磁盘监控与告警。
6. 定期检查基础镜像和 npm 依赖漏洞，升级前先备份并在测试环境回归。
7. 管理端和 Neo4j Browser 不直接暴露到互联网。

Nginx 已将上传限制设为 12 MB，API 的单文件限制为 10 MB，并为解析请求配置 120 秒代理超时。

## 11. 更新与回滚

### 更新

```bash
git pull
docker compose --env-file .env.docker -f docker-compose.yml build --pull
docker compose --env-file .env.docker -f docker-compose.yml up -d
```

更新前固定代码版本并完成备份。验收材料应记录提交哈希：

```bash
git rev-parse HEAD
```

### 回滚

1. 切换到上一个已验证的 Git 标签或提交。
2. 重新构建 `api` 和 `web`。
3. 如果新版执行了不兼容数据库迁移，停止写入并恢复升级前备份。
4. 重新执行冒烟测试和核心业务流程。

不要通过删除命名卷来代替回滚。

## 12. 常见问题

### 镜像下载超时

现象：`failed to fetch anonymous token`、`i/o timeout` 或无法连接 Docker Hub。  
处理：检查 Docker Desktop 代理、DNS 和镜像加速配置，网络恢复后重新执行构建命令。

### API 一直等待启动

检查一次性导入任务：

```bash
docker compose --env-file .env.docker -f docker-compose.yml ps -a
docker compose --env-file .env.docker -f docker-compose.yml logs import-gold import-neo4j
```

如果任务退出码不为 0，先修复密码、迁移或导入文件问题，再重新运行对应任务。

### PostgreSQL 认证失败

命名卷首次创建后，修改 `.env.docker` 中的密码不会自动修改数据库内部密码。应恢复原密码，或由管理员在数据库内安全修改；不要直接删除卷。

### Neo4j 健康检查失败

确认 `NEO4J_PASSWORD` 符合 Neo4j 密码要求，检查 7474/7687 端口冲突，并查看：

```bash
docker compose --env-file .env.docker -f docker-compose.yml logs neo4j
```

### 简历 OCR 显示不可用

重新构建 API 镜像，确认容器内工具存在：

```bash
docker compose --env-file .env.docker -f docker-compose.yml exec api tesseract --version
docker compose --env-file .env.docker -f docker-compose.yml exec api pdftoppm -v
```

### 上传返回 413

Web 层限制为 12 MB，API 单文件限制为 10 MB。压缩文件或调整 Nginx 与 Multer 两处限制，并重新构建对应镜像。

### 页面能打开但 API 请求失败

优先访问 `http://localhost:8080/api/health`。如果 API 直连正常而代理失败，检查 `docker/nginx.conf`、`api` 服务健康状态和容器网络。

## 13. 验收交付清单

- [ ] Dockerfile、Compose、Nginx 和环境变量模板已随代码提交。
- [ ] `.env.docker` 使用现场密钥，未进入 Git 和镜像。
- [ ] `docker compose config --quiet` 通过。
- [ ] 全部常驻服务为运行或健康状态。
- [ ] 两个导入任务均为 `Exited (0)`。
- [ ] `npm run docker:e2e` 通过。
- [ ] 登录、简历上传、解析、岗位匹配、差距诊断、学习验证和再匹配流程可运行。
- [ ] PostgreSQL、Neo4j、Qdrant 和上传文件具备备份方案。
- [ ] 提交材料记录代码版本、数据快照、部署时间和评测命令。

完成以上检查后，该部署包可用于单机演示和赛题验收。公网生产使用前，必须完成端口收敛、HTTPS、密钥托管、监控告警和备份恢复演练。
