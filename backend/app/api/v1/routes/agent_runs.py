from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AgentRun, RunEvent, AgentConfiguration, OutboxTask, User, ModelConnection, BudgetPolicy, ConfigurationTest
from app.security import current_user, require_csrf
from app.api.v1.routes.workspaces import editable, authorized_product
from app.api.v1.routes.workflows import require_workflow
from app.api.v1.routes.agent_configs import fingerprint

router = APIRouter(tags=['agent-runs'])

def read(run):
    return {key: getattr(run, key) for key in ('id', 'workflow_id', 'configuration_id', 'workspace_revision', 'status', 'error', 'created_at')}

class Start(BaseModel):
    revision: int = Field(ge=0)
    artifact_id: str | None = None
    unit_id: str | None = None
    instruction: str = Field(default='', max_length=2000)
    operation: Literal['draft', 'review'] = 'draft'

    @model_validator(mode='after')
    def local_edit(self):
        if self.operation == 'review':
            if not self.artifact_id or self.unit_id or self.instruction: raise ValueError('审核需要稿件ID，不能同时指定修改目标')
            return self
        if any([self.artifact_id, self.unit_id, self.instruction]) and not all([self.artifact_id, self.unit_id, self.instruction.strip()]):
            raise ValueError('局部修改需要指定稿件、段落和修改描述')
        return self

@router.post('/workflows/{workflow_id}/agent-runs', status_code=202, dependencies=[Depends(require_csrf)])
def start(workflow_id: str, payload: Start, idempotency_key: str = Header(min_length=8, max_length=64), db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow, workspace = editable(db, workflow_id, user)
    existing = db.scalar(select(AgentRun).where(AgentRun.workflow_id == workflow_id, AgentRun.request_key == idempotency_key))
    if existing:
        if existing.workspace_revision != payload.revision: raise HTTPException(409, '重复请求的输入版本不一致')
        if existing.snapshot.get('edit_request') != payload.model_dump(exclude={'revision'}): raise HTTPException(409, '同一幂等键不能用于不同请求')
        return read(existing)
    authorized_product(db, user, workspace)
    if workspace.revision != payload.revision or workflow.current_step not in ('drafting', 'storyboarding'): raise HTTPException(409, '请先完成素材和产品确认，并刷新当前版本')
    pending = db.scalar(select(AgentRun.id).where(AgentRun.workflow_id == workflow_id, AgentRun.status.in_(['queued', 'running'])))
    if pending: raise HTTPException(409, '已有生成任务正在执行')
    agent_type = 'screenwriter' if workflow.hotspot.content_type == 'video' else 'writer'
    if workflow.current_step == 'storyboarding': agent_type = 'storyboard'
    if payload.operation == 'review': agent_type = 'reviewer'
    configuration = db.scalar(select(AgentConfiguration).where(AgentConfiguration.tenant_id == user.tenant_id, AgentConfiguration.agent_type == agent_type, AgentConfiguration.status == 'published'))
    if configuration is None: raise HTTPException(409, '请先发布对应创作 Agent 的配置')
    config = configuration.configuration
    if config.get('allowed_tools'): raise HTTPException(409, '当前创作执行器尚不支持工具调用')
    connections = [db.get(ModelConnection, i) for i in [config.get('primary_model_id'), config.get('fallback_model_id')] if i]
    if not connections or any(not c or c.tenant_id != user.tenant_id or not c.enabled for c in connections): raise HTTPException(409, '模型已停用或不存在')
    fp = fingerprint(config, connections)
    if not db.scalar(select(ConfigurationTest.id).where(ConfigurationTest.configuration_id == configuration.id, ConfigurationTest.fingerprint == fp, ConfigurationTest.succeeded == True).limit(1)): raise HTTPException(409, '模型连接已变化，请重新测试并发布配置')
    policy = db.get(BudgetPolicy, user.tenant_id)
    if not policy or policy.daily_limit_micros <= 0 or config.get('budget', 0) <= 0: raise HTTPException(409, '请先配置每日预算和 Agent 单次预算')
    snapshot = {'configuration': config, 'connections': [{'id': c.id, 'name': c.name, 'base_url': c.base_url, 'model_name': c.model_name, 'encrypted_key': c.encrypted_key, 'options': c.options} for c in connections],
                'material': workspace.material, 'industry': workflow.hotspot.industry, 'product': workspace.product_snapshot, 'user_id': user.id, 'tenant_id': user.tenant_id, 'step': workflow.current_step, 'kind': 'storyboard' if workflow.current_step == 'storyboarding' else 'script' if workflow.hotspot.content_type == 'video' else 'article'}
    if workflow.current_step == 'storyboarding':
        from app.models import ArtifactVersion
        script = db.scalar(select(ArtifactVersion).where(ArtifactVersion.workflow_id == workflow_id, ArtifactVersion.kind == 'script', ArtifactVersion.status == 'approved').order_by(ArtifactVersion.version.desc()).limit(1))
        if not script: raise HTTPException(409, '请先确认剧本')
        snapshot['approved_script'] = {'id': script.id, 'hash': script.content_hash, 'title': script.title, 'units': script.units}
    snapshot['edit_request'] = payload.model_dump(exclude={'revision'})
    if payload.artifact_id:
        from app.models import ArtifactVersion
        artifact = db.get(ArtifactVersion, payload.artifact_id)
        if not artifact or artifact.workflow_id != workflow_id or artifact.workspace_revision != workspace.revision or artifact.status == 'stale': raise HTTPException(409, '请先保存并选择当前稿件')
        if payload.operation != 'review' and not any(u['id'] == payload.unit_id for u in artifact.units): raise HTTPException(422, '修改目标段落不存在')
        snapshot['base_artifact'] = {'id': artifact.id, 'content_hash': artifact.content_hash, 'title': artifact.title, 'units': artifact.units}
    run = AgentRun(workflow_id=workflow_id, request_key=idempotency_key, configuration_id=configuration.id, workspace_revision=workspace.revision, snapshot=snapshot)
    db.add(run); db.flush()
    db.add(OutboxTask(run_id=run.id))
    db.add(RunEvent(run_id=run.id, sequence=1, kind='queued', summary='任务已持久化，等待后台执行；配置、产品和素材版本已固定。'))
    db.commit(); db.refresh(run)
    return read(run)

@router.get('/workflows/{workflow_id}/agent-runs')
def runs(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_workflow(workflow_id, db, user)
    return [read(r) for r in db.scalars(select(AgentRun).where(AgentRun.workflow_id == workflow_id).order_by(AgentRun.created_at.desc()))]

@router.post('/agent-runs/{run_id}/cancel', dependencies=[Depends(require_csrf)])
def cancel(run_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    run = db.get(AgentRun, run_id)
    if not run: raise HTTPException(404, '任务不存在')
    if user.role not in ('admin', 'creator'): raise HTTPException(403, '没有任务操作权限')
    require_workflow(run.workflow_id, db, user)
    db.refresh(run, with_for_update=True)
    if run.status not in ('queued', 'running'): raise HTTPException(409, '任务已结束，不能取消')
    run.status = 'cancelled'; run.error = '用户取消任务；已发出的模型请求可能仍产生费用，后续结果不会提交。'
    from sqlalchemy import func
    sequence = db.scalar(select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)) or 0
    db.add(RunEvent(run_id=run_id, sequence=sequence + 1, kind='cancelled', summary=run.error))
    db.commit()
    return read(run)

@router.get('/agent-runs/{run_id}/events')
def events(run_id: str, after: int = Query(default=0, ge=0), db: Session = Depends(get_db), user: User = Depends(current_user)):
    run = db.get(AgentRun, run_id)
    if not run: raise HTTPException(404, '任务不存在')
    require_workflow(run.workflow_id, db, user)
    from app.models import WorkflowWorkspace
    workspace = db.get(WorkflowWorkspace, run.workflow_id)
    if workspace: authorized_product(db, user, workspace)
    return [{'id': e.id, 'sequence': e.sequence, 'kind': e.kind, 'summary': e.summary, 'created_at': e.created_at} for e in db.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence > after).order_by(RunEvent.sequence))]

@router.get('/agent-runs/{run_id}/events/stream')
def stream(run_id: str, request: Request, after: int = Query(default=0, ge=0), last_event_id: str | None = Header(default=None), db: Session = Depends(get_db), user: User = Depends(current_user)):
    import json
    import time
    from fastapi.responses import StreamingResponse
    from app.security import current_session
    events(run_id, after, db, user)
    try: cursor = max(after, int(last_event_id or 0))
    except ValueError: raise HTTPException(422, '无效的事件游标') from None
    def generate():
        nonlocal cursor
        for _ in range(30):
            db.rollback()
            try:
                db.expire_all()
                active = current_user(current_session(request, db), db)
                rows = events(run_id, cursor, db, active)
            except HTTPException:
                yield 'event: access_revoked\ndata: {}\n\n'
                return
            for row in rows:
                cursor = row['sequence']
                yield f'id: {cursor}\ndata: {json.dumps(row, ensure_ascii=False, default=str)}\n\n'
            run = db.get(AgentRun, run_id)
            if run.status not in ('queued', 'running'):
                yield 'event: finished\ndata: {}\n\n'
                return
            yield ': heartbeat\n\n'
            time.sleep(1)
    return StreamingResponse(generate(), media_type='text/event-stream', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
