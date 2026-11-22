from typing import Literal
import hashlib
import json
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, Hotspot, Workflow, WorkflowWorkspace, AgentEvent
from app.schemas import WorkflowRead
from app.security import require_roles, require_csrf

router = APIRouter(tags=['workflow-entry'])

class Entry(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=300)
    material: str = Field(min_length=20, max_length=100000)
    content_type: Literal['text', 'article', 'video']
    source_url: str | None = Field(default=None, max_length=1000)
    industry: str = Field(default='3C', min_length=1, max_length=100)
    rights_confirmed: Literal[True]

@router.post('/workflow-entry', response_model=WorkflowRead, status_code=201, dependencies=[Depends(require_csrf)])
def create(payload: Entry, idempotency_key: str = Header(min_length=8, max_length=64), db: Session = Depends(get_db), user: User = Depends(require_roles('admin', 'creator'))):
    db.refresh(user, with_for_update=True)
    digest = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(Workflow).where(Workflow.tenant_id == user.tenant_id, Workflow.created_by_user_id == user.id, Workflow.entry_key == idempotency_key))
    if existing:
        if existing.entry_hash != digest: raise HTTPException(409, '相同请求标识已用于不同素材')
        return existing
    hotspot = Hotspot(tenant_id=user.tenant_id, title=payload.title, summary=payload.material[:500], content_type=payload.content_type, source_url=payload.source_url, source_kind='manual', industry=payload.industry)
    db.add(hotspot); db.flush()
    workflow = Workflow(tenant_id=user.tenant_id, created_by_user_id=user.id, entry_key=idempotency_key, entry_hash=digest, hotspot_id=hotspot.id, status='in_progress', current_step='drafting' if payload.content_type == 'text' else 'product_selection')
    db.add(workflow); db.flush()
    db.add(WorkflowWorkspace(workflow_id=workflow.id, revision=1, material=payload.material, rights_confirmed=True))
    db.add(AgentEvent(workflow_id=workflow.id, sequence=1, agent_type='user', event_type='manual_action', title='从聊天入口创建工作流', summary='用户提交并确认参考素材；尚未调用模型。'))
    db.commit(); db.refresh(workflow)
    return workflow
