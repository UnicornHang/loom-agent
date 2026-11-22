from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import MCPServer, User
from app.security import require_roles, require_csrf
from app.services.model_secrets import cipher
from app.services import mcp_gateway
from app.services.audit import record

router = APIRouter(prefix='/mcp-servers', tags=['mcp'])

class Write(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(max_length=500)
    token: str | None = Field(default=None, max_length=4096)
    clear_token: bool = False
    timeout_seconds: int = Field(default=15, ge=1, le=30)
    data_scope: Literal['none', 'public_only', 'authorized_product'] = 'none'
    enabled: bool = False
    revision: int = Field(default=0, ge=0)

    @field_validator('endpoint')
    @classmethod
    def url(cls, value):
        p = urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment: raise ValueError('请输入不含凭据与查询参数的 HTTPS MCP 地址')
        return value

def read(row):
    return {**{key: getattr(row, key) for key in ('id', 'revision', 'name', 'endpoint', 'timeout_seconds', 'data_scope', 'enabled', 'tools', 'tested_revision')}, 'has_token': bool(row.encrypted_token)}

def get(db, user, server_id):
    row = db.get(MCPServer, server_id)
    if not row or row.tenant_id != user.tenant_id: raise HTTPException(404, 'MCP 服务不存在')
    return row

@router.get('')
def servers(db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return [read(row) for row in db.scalars(select(MCPServer).where(MCPServer.tenant_id == user.tenant_id))]

@router.post('', status_code=201, dependencies=[Depends(require_csrf)])
def create(payload: Write, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = MCPServer(tenant_id=user.tenant_id, **payload.model_dump(exclude={'token', 'clear_token', 'revision'}), encrypted_token=cipher().encrypt(payload.token.encode()).decode() if payload.token else None)
    db.add(row); db.flush()
    record(db, user, 'mcp.created', row.id, '登记MCP服务；未授予业务工具执行权限')
    db.commit(); db.refresh(row)
    return read(row)

@router.put('/{server_id}', dependencies=[Depends(require_csrf)])
def edit(server_id: str, payload: Write, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = get(db, user, server_id)
    token = None if payload.clear_token else cipher().encrypt(payload.token.encode()).decode() if payload.token else row.encrypted_token
    result = db.execute(update(MCPServer).where(MCPServer.id == server_id, MCPServer.revision == payload.revision).values(**payload.model_dump(exclude={'token', 'clear_token', 'revision'}), encrypted_token=token, revision=payload.revision + 1, tested_revision=None, tools=[]))
    if not result.rowcount:
        db.rollback(); raise HTTPException(409, 'MCP 配置已变化，请刷新')
    record(db, user, 'mcp.updated', row.id, '修改MCP连接，清空旧工具发现状态')
    db.commit(); db.refresh(row)
    return read(row)

@router.post('/{server_id}/discover', dependencies=[Depends(require_csrf)])
def discover(server_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = get(db, user, server_id)
    revision = row.revision
    if not row.enabled: raise HTTPException(409, '请先启用服务登记')
    try: tools = mcp_gateway.discover(row.endpoint, cipher().decrypt(row.encrypted_token.encode()).decode() if row.encrypted_token else None, row.timeout_seconds)
    except Exception: raise HTTPException(502, 'MCP 初始化或工具发现失败；请检查授权、地址、协议版本及工具列表规模') from None
    result = db.execute(update(MCPServer).where(MCPServer.id == server_id, MCPServer.revision == revision).values(tools=tools, tested_revision=revision))
    if not result.rowcount:
        db.rollback(); raise HTTPException(409, '发现期间配置已变化，请重试')
    db.commit(); db.refresh(row)
    return read(row)
