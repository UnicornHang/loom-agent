from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.migrate import upgrade_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env != "development":
        raise RuntimeError("当前版本未实现登录与权限控制，仅允许 development 环境启动")
    upgrade_database()
    yield


app = FastAPI(title="Loom Agent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")
