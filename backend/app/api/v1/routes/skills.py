import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import SkillVersion, User
from app.security import require_roles, require_csrf
from app.api.v1.routes.agent_configs import AgentType

router = APIRouter(prefix='/skills', tags=['skills'])

class Manifest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    industries: list[str] = Field(default_factory=list, max_length=30)
    agents: list[AgentType] = Field(min_length=1, max_length=8)
    variables: list[str] = Field(default_factory=list, max_length=50)

class Write(BaseModel):
    skill_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{1,99}$')
    base_version: int = Field(ge=0)
    manifest: Manifest
    content: str = Field(min_length=1, max_length=30000)

class Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    skill_key: str
    version: int
    status: str
    manifest: dict
    content: str
    created_at: datetime

def skill(db, user, skill_id):
    row = db.get(SkillVersion, skill_id)
    if not row or row.tenant_id != user.tenant_id: raise HTTPException(404, 'Skill 版本不存在')
    return row

def validate(manifest, content):
    missing = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', content)) - set(manifest['variables'])
    if missing: raise HTTPException(422, 'Skill 未声明变量：' + '、'.join(sorted(missing)))
    if not content.strip(): raise HTTPException(422, 'Skill 正文不能为空')
    if any(not re.fullmatch(r'\w+', key) for key in manifest['variables']): raise HTTPException(422, '变量名只能使用字母、数字和下划线')

@router.get('', response_model=list[Read])
def list_skills(db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return db.scalars(select(SkillVersion).where(SkillVersion.tenant_id == user.tenant_id).order_by(SkillVersion.created_at.desc())).all()

@router.post('', response_model=Read, status_code=201, dependencies=[Depends(require_csrf)])
def create(payload: Write, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    latest = db.scalar(select(func.max(SkillVersion.version)).where(SkillVersion.tenant_id == user.tenant_id, SkillVersion.skill_key == payload.skill_key)) or 0
    if latest != payload.base_version: raise HTTPException(409, 'Skill 已更新，请刷新')
    row = SkillVersion(tenant_id=user.tenant_id, skill_key=payload.skill_key, version=latest + 1, manifest=payload.manifest.model_dump(), content=payload.content)
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Skill 已更新，请刷新') from None
    db.refresh(row)
    return row

@router.post('/{skill_id}/publish', response_model=Read, dependencies=[Depends(require_csrf)])
def publish(skill_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = skill(db, user, skill_id)
    validate(row.manifest, row.content)
    # Publishing a Skill only makes its method available for binding. It grants no execution permission.
    row.status = 'published'
    db.commit(); db.refresh(row)
    return row

@router.post('/{skill_id}/preview')
def preview(skill_id: str, values: dict[str, str], db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = skill(db, user, skill_id)
    validate(row.manifest, row.content)
    missing = set(row.manifest['variables']) - values.keys()
    if missing: raise HTTPException(422, '预览缺少变量：' + '、'.join(sorted(missing)))
    return {'preview': re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: values[m[1]], row.content), 'scope': 'template_only'}
