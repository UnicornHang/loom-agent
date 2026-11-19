# 部署与运维

开发环境使用项目根目录的 `compose.yaml` 和前后端各自的 `Dockerfile.dev`，可启动前端、API、PostgreSQL + pgvector、Redis 与 MinIO。API 仍只运行在 `development` 模式；Redis 和 MinIO 目前是后续任务及资产功能的依赖服务，业务代码尚未接入。

云端正式部署文件将放这里：API/Worker 镜像、HTTPS 网关、备份、日志和监控。当前开发版已有基础登录与产品分组授权，但尚无完整资产、审计和任务能力，不提供可直接上线的配置。
