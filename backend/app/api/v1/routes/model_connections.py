from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ModelConnection, User
from app.security import require_csrf, require_roles
from app.services.model_secrets import cipher
from app.services.audit import record

router = APIRouter(prefix="/model-connections", tags=["models"])


class ConnectionOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    capability: Literal['text', 'vision', 'image', 'audio', 'embedding'] = 'text'
    input_price: float = Field(default=0, ge=0, le=100000)
    output_price: float = Field(default=0, ge=0, le=100000)
    currency: Literal['CNY', 'USD'] = 'CNY'


class ConnectionWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=4096)
    enabled: bool = False
    options: ConnectionOptions = Field(default_factory=ConnectionOptions)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("请填写不含凭据和查询参数的 HTTPS API 地址")
        return value.rstrip("/")


class ConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    base_url: str
    model_name: str
    enabled: bool
    options: dict
    created_at: datetime


@router.get("", response_model=list[ConnectionRead])
def list_connections(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return db.scalars(select(ModelConnection).where(ModelConnection.tenant_id == user.tenant_id)).all()


@router.post("", response_model=ConnectionRead, status_code=201, dependencies=[Depends(require_csrf)])
def create_connection(payload: ConnectionWrite, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(422, "新建连接需要 API Key")
    row = ModelConnection(**payload.model_dump(exclude={"api_key"}), tenant_id=user.tenant_id,
                          encrypted_key=cipher().encrypt(payload.api_key.encode()).decode())
    db.add(row)
    db.flush()
    record(db, user, 'model.created', row.id, '创建模型连接；凭据加密保存')
    db.commit()
    db.refresh(row)
    return row


@router.put("/{connection_id}", response_model=ConnectionRead, dependencies=[Depends(require_csrf)])
def update_connection(connection_id: str, payload: ConnectionWrite, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    row = db.get(ModelConnection, connection_id)
    if row is None or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "模型连接不存在")
    for key, value in payload.model_dump(exclude={"api_key"}).items():
        setattr(row, key, value)
    if payload.api_key and payload.api_key.strip():
        row.encrypted_key = cipher().encrypt(payload.api_key.encode()).decode()
    record(db, user, 'model.updated', row.id, '修改模型连接，已有配置测试需按新连接重新校验')
    db.commit()
    db.refresh(row)
    return row
