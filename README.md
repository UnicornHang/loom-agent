# Loom 内容工作台

多 Agent 种草内容平台的第一阶段代码骨架。现在可以录入产品和内容灵感、从灵感创建工作流、查看流程事件。Agent 模型、自动采集和实际内容生成尚未接入，界面会明确显示待配置状态。

## 本地启动

### Docker 开发环境

在项目根目录运行：

```powershell
docker compose up -d --build
docker compose ps
```

工作台：`http://localhost:5173`；API 文档：`http://localhost:8000/docs`；MinIO 管理台：`http://localhost:19001`（开发账号 `loom_dev`，密码 `loom_dev_password`）。PostgreSQL、Redis、MinIO API 分别仅绑定本机端口 `15432`、`16379`、`19000`，避免与其他项目冲突。容器内部仍使用标准端口。数据保存在 Docker 命名卷中，停止容器不会清空数据。

```powershell
docker compose logs -f api
docker compose down
```

开发容器使用源码挂载和热更新。Compose 中的固定口令只供本机开发；后台 Worker、自动采集和 MinIO 业务接入尚未实现。`docker compose down -v` 会删除开发数据卷，请仅在明确需要重置数据时使用。

首次启动后，在终端创建管理员（交互输入密码，不会写入配置文件）：

```powershell
docker compose exec api python -m app.cli create-admin --username admin
```

随后打开工作台登录，在“成员与授权”中创建产品分组、成员账号并授权。已登录用户可在右上角修改密码，修改后需重新登录。现有未分组的历史产品仅管理员可见；新产品必须选择分组。若不使用 Docker，可在 `backend` 目录运行 `.venv\Scripts\python -m app.cli create-admin --username admin`。

### 不使用 Docker

后端（Python 3.12）：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

前端（Node 22）：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。API 文档位于 `http://localhost:8000/docs`。

本地默认使用 SQLite 以便快速启动；设置 `DATABASE_URL` 后可切换 PostgreSQL。当前已加入开发阶段的账号登录与产品分组授权，服务仍限制为 `development` 环境，不适合直接部署给团队使用。

## 当前范围

- 管理员建号、登录与退出；产品分组授权和服务端可见范围过滤。
- 产品创建与列表；手动录入内容灵感。
- 创建工作流、查看首条执行事件。
- Agent 运行接口返回 503，明确提示模型尚未配置。

## 下一阶段

产品图片与批量导入、上传素材、热点采集适配器、Agent 编排与模型配置、混合产品推荐、文章和视频剧本生成、人工确认节点、内容库及下载，均尚未实现。

项目文档入口：[docs/README.md](docs/README.md)。其中包含[产品需求文档](docs/产品方案-多Agent热点内容创作平台.md)、[前后端技术方案](docs/技术方案-Python-React多Agent内容平台.md)和[项目架构与目录约定](docs/项目架构与目录约定.md)。

