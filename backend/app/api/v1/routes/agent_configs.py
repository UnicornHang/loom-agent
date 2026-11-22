"""Immutable configuration snapshots. Validation is structural, never a model test."""
import re
import hashlib
import json
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AgentConfiguration, ModelConnection, User, ConfigurationTest, SkillVersion
from app.services import model_gateway
from app.services.model_secrets import cipher
from app.services.model_budget import reserve, settle
from app.services.audit import record
from app.services.locks import tenant_lock
from app.security import require_roles, require_csrf

router = APIRouter(prefix="/agent-configs", tags=["agent-configs"])
AgentType = Literal['collector', 'analyst', 'recommender', 'writer', 'designer', 'screenwriter', 'storyboard', 'reviewer']

class Skill(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=30000)
    source_version_id: str | None = None
    industries: list[str] = Field(default_factory=list, max_length=30)

class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    primary_model_id: str | None = None
    fallback_model_id: str | None = None
    prompt: str = Field(default='', max_length=50000)
    variables: dict[str, str] = Field(default_factory=dict, max_length=50)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    retries: int = Field(default=2, ge=0, le=5)
    concurrency: int = Field(default=1, ge=1, le=20)
    max_iterations: int = Field(default=3, ge=1, le=20)
    max_tool_calls: int = Field(default=10, ge=0, le=100)
    budget: float = Field(default=0, ge=0, le=10000)
    skills: list[Skill] = Field(default_factory=list, max_length=30)
    allowed_tools: list[Literal['search_authorized_products', 'get_product_evidence', 'get_hotspot_material', 'read_allowed_asset', 'create_image_candidate', 'check_claims', 'save_draft_candidate']] = Field(default_factory=list)

class Write(BaseModel):
    base_version: int = Field(ge=0)
    configuration: Configuration

class Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_type: str
    version: int
    status: str
    configuration: Configuration
    created_at: datetime

def history(db, user, agent_type):
    return select(AgentConfiguration).where(AgentConfiguration.tenant_id == user.tenant_id, AgentConfiguration.agent_type == agent_type)

def check(config: Configuration, db, user):
    errors = []
    if not config.prompt.strip(): errors.append('提示词不能为空')
    remainder = re.sub(r'\{\{\s*(\w+)\s*\}\}', '', config.prompt)
    if '{{' in remainder or '}}' in remainder: errors.append('提示词变量格式无效，请使用{{变量名}}')
    missing = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', config.prompt)) - config.variables.keys()
    if missing: errors.append('缺少变量：' + '、'.join(sorted(missing)))
    for s in config.skills:
        missing = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', s.content)) - config.variables.keys()
        if missing: errors.append('Skill 缺少变量：' + '、'.join(sorted(missing)))
    if not config.primary_model_id: errors.append('请选择主模型')
    for model_id in [config.primary_model_id, config.fallback_model_id]:
        if model_id:
            model = db.get(ModelConnection, model_id)
            if not model or model.tenant_id != user.tenant_id or not model.enabled:
                errors.append('选定的模型不存在或未启用')
    if config.primary_model_id and config.primary_model_id == config.fallback_model_id: errors.append('主模型和备用模型不能相同')
    return errors

@router.get('/{agent_type}', response_model=list[Read])
def versions(agent_type: AgentType, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return db.scalars(history(db, user, agent_type).order_by(AgentConfiguration.version.desc())).all()

@router.post('/{agent_type}/validate')
def validate(agent_type: AgentType, payload: Configuration, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    errors = check(payload, db, user)
    preview = re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: payload.variables.get(m[1], m[0]), payload.prompt)
    return {'valid': not errors, 'errors': errors, 'preview': preview, 'scope': 'configuration_only'}

@router.post('/{agent_type}', response_model=Read, status_code=201, dependencies=[Depends(require_csrf)])
def save(agent_type: AgentType, payload: Write, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    for s in payload.configuration.skills:
        if s.source_version_id:
            version = db.get(SkillVersion, s.source_version_id)
            if not version or version.tenant_id != user.tenant_id or version.status != 'published': raise HTTPException(422, '引用的 Skill 版本不存在或未发布')
            if agent_type not in version.manifest['agents']: raise HTTPException(422, 'Skill 不适用于当前 Agent')
            s.name = version.manifest['name']; s.version = str(version.version); s.content = version.content; s.industries = version.manifest['industries']
    latest = db.scalar(history(db, user, agent_type).with_only_columns(func.max(AgentConfiguration.version))) or 0
    if payload.base_version != latest: raise HTTPException(409, '配置已更新，请刷新后重试')
    row = AgentConfiguration(tenant_id=user.tenant_id, agent_type=agent_type, version=latest + 1, configuration=payload.configuration.model_dump())
    db.add(row)
    record(db, user, 'agent.draft_saved', agent_type, f'创建配置草稿 v{latest + 1}')
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '配置已更新，请刷新后重试') from None
    db.refresh(row)
    return row


def selected(db, user, agent_type, version_id):
    row = db.scalar(history(db, user, agent_type).where(AgentConfiguration.id == version_id))
    if row is None: raise HTTPException(404, '配置版本不存在')
    return row


def fingerprint(config, connections):
    data = {'configuration': config, 'connections': [{'id': m.id, 'url': m.base_url, 'model': m.model_name, 'key_hash': hashlib.sha256(m.encrypted_key.encode()).hexdigest(), 'options': m.options, 'enabled': m.enabled} for m in connections]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@router.post('/{agent_type}/{version_id}/test', dependencies=[Depends(require_csrf)])
def test_configuration(agent_type: AgentType, version_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = selected(db, user, agent_type, version_id)
    config = Configuration.model_validate(row.configuration)
    errors = check(config, db, user)
    if errors: raise HTTPException(422, '；'.join(errors))
    if config.allowed_tools: raise HTTPException(409, '工具执行引擎尚未接入，请先移除工具白名单后测试纯文本配置')
    connections = [db.get(ModelConnection, i) for i in [config.primary_model_id, config.fallback_model_id] if i]
    if any((m.options or {}).get('capability', 'text') != 'text' for m in connections): raise HTTPException(409, '当前真实测试仅支持文本模型')
    expected = fingerprint(row.configuration, connections)
    prompt = re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: config.variables[m[1]], config.prompt)
    skills = '\n\n'.join(re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: config.variables[m[1]], s.content) for s in config.skills)
    messages = [{'role': 'system', 'content': prompt + '\n\n' + skills}, {'role': 'user', 'content': '这是配置连通性测试，请简短确认已收到，不调用工具。'}]
    # Each configured model must succeed independently, including the fallback.
    test = ConfigurationTest(configuration_id=row.id, fingerprint=expected, succeeded=False, summary='测试已开始，尚未完成')
    db.add(test)
    db.flush()
    test_id = test.id
    for connection in connections:
        reservation = reserve(db, user.tenant_id, connection, messages, min(config.max_tokens, 128), config.budget / len(connections))
        # Persist the reservation before making an external, potentially billable call.
        reservation_id = reservation.id
        db.commit()
        try:
            key = cipher().decrypt(connection.encrypted_key.encode()).decode()
            result = model_gateway.complete(connection.base_url, key, connection.model_name, messages, min(config.max_tokens, 128), config.temperature, min(config.timeout_seconds, 30))
        except Exception:
            reservation = db.get(type(reservation), reservation_id)
            reservation.status = 'uncertain'
            db.get(ConfigurationTest, test_id).summary = '模型测试未完成，请检查连接、密钥和协议；额度暂保留，避免重复计费。'
            db.commit()
            raise HTTPException(502, '模型测试失败；请检查连接、密钥和协议。预留额度暂保留。') from None
        reservation = db.get(type(reservation), reservation_id)
        settle(reservation, result['usage'], connection.options)
        db.commit()
    test = db.get(ConfigurationTest, test_id)
    test.succeeded = True
    test.summary = '所选主备文本模型均完成真实响应测试；未执行业务工作流或工具。'
    db.commit()
    return {'id': test.id, 'succeeded': True, 'summary': test.summary}


@router.get('/{agent_type}/{version_id}/tests')
def test_history(agent_type: AgentType, version_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    selected(db, user, agent_type, version_id)
    return [{'id': t.id, 'succeeded': t.succeeded, 'summary': t.summary, 'created_at': t.created_at} for t in db.scalars(select(ConfigurationTest).where(ConfigurationTest.configuration_id == version_id).order_by(ConfigurationTest.created_at.desc()).limit(20))]


class Publish(BaseModel):
    expected_active_id: str | None = None

@router.post('/{agent_type}/{version_id}/publish', response_model=Read, dependencies=[Depends(require_csrf)])
def publish(agent_type: AgentType, version_id: str, payload: Publish, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    tenant_lock(db, user.tenant_id, 'agent-publication')
    # Serialize publication per tenant using its shared budget row, not an individual administrator.
    from app.models import BudgetPolicy
    db.scalar(select(BudgetPolicy).where(BudgetPolicy.tenant_id == user.tenant_id).with_for_update())
    row = selected(db, user, agent_type, version_id)
    active = db.scalar(history(db, user, agent_type).where(AgentConfiguration.status == 'published'))
    if (active.id if active else None) != payload.expected_active_id: raise HTTPException(409, '生效版本已变化，请刷新')
    errors = check(Configuration.model_validate(row.configuration), db, user)
    if errors: raise HTTPException(422, '；'.join(errors))
    connections = [db.get(ModelConnection, i) for i in [row.configuration.get('primary_model_id'), row.configuration.get('fallback_model_id')] if i]
    fp = fingerprint(row.configuration, connections)
    passed = db.scalar(select(ConfigurationTest.id).where(ConfigurationTest.configuration_id == row.id, ConfigurationTest.fingerprint == fp, ConfigurationTest.succeeded == True).limit(1))
    if not passed: raise HTTPException(409, '当前配置或连接尚未通过真实测试，请先测试此版本')
    if active: active.status = 'retired'
    row.status = 'published'
    record(db, user, 'agent.published', row.id, f'{agent_type} 生效版本切换为 v{row.version}')
    db.commit()
    db.refresh(row)
    return row
