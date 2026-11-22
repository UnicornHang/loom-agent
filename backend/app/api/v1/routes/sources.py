from typing import Literal, Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import SourceConfiguration, CollectionRun, User, utcnow
from app.security import require_roles, require_csrf
from app.services.collection_scheduler import preflight

router = APIRouter(prefix='/sources', tags=['sources'])

class SourceWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    adapter: Literal['douyin_hot_search', 'weibo_hot_search', 'bilibili_popular', 'xiaohongshu_hot_search', 'douyin_official', 'licensed_feed', 'custom_authorized']
    industry: str = Field(min_length=1, max_length=100)
    keywords: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=100)
    interval_minutes: int = Field(default=60, ge=15, le=1440)
    enabled: bool = False
    authorization_note: str = Field(default='', max_length=3000)
    revision: int = Field(default=0, ge=0)

class SourceRead(SourceWrite):
    model_config = ConfigDict(from_attributes=True)
    id: str
    next_run_at: datetime

def get_source(db, user, source_id):
    row = db.get(SourceConfiguration, source_id)
    if not row or row.tenant_id != user.tenant_id: raise HTTPException(404, '采集来源不存在')
    return row

@router.get('', response_model=list[SourceRead])
def sources(db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return db.scalars(select(SourceConfiguration).where(SourceConfiguration.tenant_id == user.tenant_id)).all()

@router.post('', response_model=SourceRead, status_code=201, dependencies=[Depends(require_csrf)])
def create(payload: SourceWrite, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = SourceConfiguration(tenant_id=user.tenant_id, **payload.model_dump(exclude={'revision'}))
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.put('/{source_id}', response_model=SourceRead, dependencies=[Depends(require_csrf)])
def edit(source_id: str, payload: SourceWrite, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = get_source(db, user, source_id)
    result = db.execute(update(SourceConfiguration).where(SourceConfiguration.id == source_id, SourceConfiguration.revision == payload.revision).values(**payload.model_dump(exclude={'revision'}), revision=payload.revision + 1, next_run_at=utcnow()))
    if not result.rowcount:
        db.rollback(); raise HTTPException(409, '来源配置已变化，请刷新')
    db.commit(); db.refresh(row)
    return row

@router.post('/{source_id}/run', dependencies=[Depends(require_csrf)])
def run(source_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    source = get_source(db, user, source_id)
    row = preflight(db, source, 'manual')
    db.commit()
    return {'id': row.id, 'status': row.status, 'summary': row.summary}

@router.get('/{source_id}/runs')
def runs(source_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    get_source(db, user, source_id)
    return [{'id': row.id, 'source_revision': row.source_revision, 'trigger': row.trigger, 'status': row.status, 'summary': row.summary, 'counts': row.counts, 'created_at': row.created_at} for row in db.scalars(select(CollectionRun).where(CollectionRun.source_id == source_id).order_by(CollectionRun.created_at.desc()).limit(100))]
