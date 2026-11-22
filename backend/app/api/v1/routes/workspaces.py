import hashlib
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import WorkflowWorkspace, ArtifactVersion, Workflow, User, Product, AgentEvent, ReviewResult, WorkflowAsset
from app.security import current_user, require_csrf, require_roles
from app.services.product_access import visible_products
from app.api.v1.routes.workflows import require_workflow

router = APIRouter(tags=['workspace'])

def workspace(db, workflow):
    row = db.get(WorkflowWorkspace, workflow.id)
    if row is None:
        row = WorkflowWorkspace(workflow_id=workflow.id)
        db.add(row)
        db.flush()
    return row

def authorized_product(db, user, row):
    if row.product_id and not db.scalar(visible_products(user).where(Product.id == row.product_id)):
        raise HTTPException(403, '产品授权已变化，请重新选择产品')

def editable(db, workflow_id, user):
    if user.role not in ('admin', 'creator'): raise HTTPException(403, '没有创作权限')
    workflow = require_workflow(workflow_id, db, user)
    db.refresh(workflow, with_for_update=True)
    return workflow, workspace(db, workflow)

def advance(db, row, revision, **values):
    result = db.execute(update(WorkflowWorkspace).where(WorkflowWorkspace.workflow_id == row.workflow_id,
        WorkflowWorkspace.revision == revision).values(revision=revision + 1, **values))
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, '工作流已更新，请刷新后重试')

def event(db, workflow, title, summary):
    sequence = db.scalar(select(func.max(AgentEvent.sequence)).where(AgentEvent.workflow_id == workflow.id)) or 0
    db.add(AgentEvent(workflow_id=workflow.id, sequence=sequence + 1, agent_type='user', event_type='manual_action', title=title, summary=summary))

@router.get('/workflows/{workflow_id}/workspace')
def get_workspace(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow = require_workflow(workflow_id, db, user)
    row = db.get(WorkflowWorkspace, workflow_id)
    if row is None: return {'revision': 0, 'material': '', 'rights_confirmed': False, 'product_id': None, 'product_snapshot': None, 'step': workflow.current_step}
    authorized_product(db, user, row)
    return {'revision': row.revision, 'material': row.material, 'rights_confirmed': row.rights_confirmed,
            'product_id': row.product_id, 'product_snapshot': row.product_snapshot, 'step': workflow.current_step}

class MaterialWrite(BaseModel):
    revision: int = Field(ge=0)
    material: str = Field(min_length=20, max_length=100000)
    rights_confirmed: Literal[True]

    @field_validator('material')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 20: raise ValueError('请补充至少20字的有效参考素材')
        return value

@router.put('/workflows/{workflow_id}/material', dependencies=[Depends(require_csrf)])
def set_material(workflow_id: str, payload: MaterialWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow, row = editable(db, workflow_id, user)
    if workflow.status == 'saved': raise HTTPException(409, '已保存成果的工作流不能替换素材，请新建工作流')
    advance(db, row, payload.revision, material=payload.material, rights_confirmed=True, product_id=None, product_snapshot=None)
    db.execute(update(ArtifactVersion).where(ArtifactVersion.workflow_id == workflow_id).values(status='stale'))
    workflow.current_step = 'drafting' if workflow.hotspot.content_type == 'text' else 'product_selection'
    workflow.status = 'in_progress'
    event(db, workflow, '参考素材已确认', '用户提交了有权使用的正文或视频文字资料；旧产品选择和下游草稿失效。')
    db.commit()
    return {'ok': True}

class ProductChoice(BaseModel):
    revision: int = Field(ge=0)
    product_id: str | None = None

@router.put('/workflows/{workflow_id}/product', dependencies=[Depends(require_csrf)])
def choose_product(workflow_id: str, payload: ProductChoice, db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow, row = editable(db, workflow_id, user)
    if not row.rights_confirmed or workflow.current_step != 'product_selection': raise HTTPException(409, '请先确认素材并进入产品选择')
    snapshot = None
    if payload.product_id:
        product = db.scalar(visible_products(user).where(Product.id == payload.product_id, Product.status == 'active'))
        if not product: raise HTTPException(404, '产品不存在或未启用')
        snapshot = {'id': product.id, 'sku': product.sku, 'name': product.name, 'category': product.category, 'description': product.description}
    advance(db, row, payload.revision, product_id=payload.product_id, product_snapshot=snapshot)
    workflow.current_step = 'drafting'
    event(db, workflow, '产品选择已确认', '已锁定产品资料快照。' if snapshot else '用户选择无产品继续。')
    db.commit()
    return {'ok': True}

class Unit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    text: str = Field(min_length=1, max_length=20000)
    image_description: str = Field(default='', max_length=2000)
    shot_size: str = Field(default='', max_length=100)
    camera_movement: str = Field(default='', max_length=200)
    composition: str = Field(default='', max_length=500)
    duration_seconds: float = Field(default=0, ge=0, le=60)
    image_asset_id: str | None = Field(default=None, max_length=32)

    @field_validator('text')
    @classmethod
    def meaningful(cls, value):
        if not value.strip(): raise ValueError('段落正文不能为空白')
        return value

class DraftWrite(BaseModel):
    revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    units: list[Unit] = Field(min_length=1, max_length=100)

def review_state(db, artifact):
    result = db.scalar(select(ReviewResult).where(ReviewResult.artifact_id == artifact.id, ReviewResult.content_hash == artifact.content_hash).order_by(ReviewResult.created_at.desc()).limit(1))
    if not result: return '未审核', []
    return ('AI审核通过' if result.passed else 'AI审核发现问题'), result.findings

def artifact_read(row, db=None):
    value = {key: getattr(row, key) for key in ('id', 'workflow_id', 'version', 'kind', 'title', 'units', 'content_hash', 'origin', 'status', 'created_at')}
    if db:
        value['review_status'], value['findings'] = review_state(db, row)
    return value

@router.get('/workflows/{workflow_id}/artifacts')
def artifacts(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_workflow(workflow_id, db, user)
    row = db.get(WorkflowWorkspace, workflow_id)
    if row: authorized_product(db, user, row)
    return [artifact_read(v, db) for v in db.scalars(select(ArtifactVersion).where(ArtifactVersion.workflow_id == workflow_id).order_by(ArtifactVersion.version.desc()))]

@router.post('/workflows/{workflow_id}/artifacts', status_code=201, dependencies=[Depends(require_csrf)])
def save_draft(workflow_id: str, payload: DraftWrite, db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow, row = editable(db, workflow_id, user)
    authorized_product(db, user, row)
    if workflow.current_step not in ('drafting', 'storyboarding'): raise HTTPException(409, '请先完成素材与产品确认')
    if len({unit.id for unit in payload.units}) != len(payload.units): raise HTTPException(422, '段落标识不能重复')
    advance(db, row, payload.revision)
    version = (db.scalar(select(func.max(ArtifactVersion.version)).where(ArtifactVersion.workflow_id == workflow_id)) or 0) + 1
    units = [u.model_dump() for u in payload.units]
    for unit in units: unit['image_asset_id'] = None
    content_hash = hashlib.sha256(json.dumps({'title': payload.title, 'units': units}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    kind = 'storyboard' if workflow.current_step == 'storyboarding' else 'script' if workflow.hotspot.content_type == 'video' else 'article'
    if kind == 'storyboard' and (not all(u['shot_size'] and u['camera_movement'] and u['composition'] and u['duration_seconds'] > 0 for u in units) or not 30 <= sum(u['duration_seconds'] for u in units) <= 60):
        raise HTTPException(422, '分镜须填写景别、运镜、构图和时长，总时长应为30–60秒')
    artifact = ArtifactVersion(workflow_id=workflow_id, version=version, workspace_revision=payload.revision + 1, kind=kind, title=payload.title, units=units, content_hash=content_hash)
    db.add(artifact)
    event(db, workflow, '人工草稿已保存', f'保存第 {version} 版，来源标记为人工编辑，尚未执行 AI 审核。')
    db.commit()
    db.refresh(artifact)
    return artifact_read(artifact)

class Finalize(BaseModel):
    revision: int = Field(ge=0)
    artifact_id: str

@router.post('/workflows/{workflow_id}/finalize', dependencies=[Depends(require_csrf)])
def finalize(workflow_id: str, payload: Finalize, db: Session = Depends(get_db), user: User = Depends(current_user)):
    workflow, row = editable(db, workflow_id, user)
    authorized_product(db, user, row)
    if workflow.current_step not in ('drafting', 'storyboarding'): raise HTTPException(409, '当前步骤不能确认成果')
    artifact = db.get(ArtifactVersion, payload.artifact_id)
    if not artifact or artifact.workflow_id != workflow_id or artifact.workspace_revision != row.revision: raise HTTPException(409, '请确认当前最新稿件')
    # Material changes must never make an old draft eligible for confirmation.
    if artifact.status == 'stale': raise HTTPException(409, '素材已变化，请重新保存草稿')
    if artifact.kind == 'article' and workflow.hotspot.content_type == 'article' and any(u.get('image_description') and not u.get('image_asset_id') for u in artifact.units): raise HTTPException(409, '请先为所有图片占位上传配图，再确认成果')
    for unit in artifact.units:
        if unit.get('image_asset_id'):
            asset = db.get(WorkflowAsset, unit['image_asset_id'])
            if not asset or asset.workflow_id != workflow_id: raise HTTPException(409, '配图引用已失效，请重新上传')
    advance(db, row, payload.revision)
    if artifact.kind == 'script':
        artifact.status = 'approved'
        workflow.current_step = 'storyboarding'
        event(db, workflow, '剧本已确认', '已固定剧本版本，进入分镜设计；分镜尚未生成。')
        db.commit()
        return {'ok': True}
    artifact.status = 'saved'
    if artifact.kind == 'storyboard':
        db.execute(update(ArtifactVersion).where(ArtifactVersion.workflow_id == workflow_id, ArtifactVersion.status == 'approved', ArtifactVersion.kind == 'script').values(status='saved'))
    workflow.status = 'saved'
    workflow.current_step = 'completed'
    event(db, workflow, '成果已确认保存', '人工确认完成；当前内容状态：' + review_state(db, artifact)[0] + '。')
    db.commit()
    return {'ok': True}

@router.get('/contents')
def contents(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ArtifactVersion).join(Workflow).where(Workflow.tenant_id == user.tenant_id, ArtifactVersion.status == 'saved')
    if user.role != 'admin': query = query.where(Workflow.created_by_user_id == user.id)
    rows = []
    for artifact in db.scalars(query.order_by(ArtifactVersion.created_at.desc())):
        row = db.get(WorkflowWorkspace, artifact.workflow_id)
        if row and row.product_id and not db.scalar(visible_products(user).where(Product.id == row.product_id)): continue
        rows.append(artifact_read(artifact, db))
    return rows

@router.get('/contents/{artifact_id}/download')
def download(artifact_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    artifact = db.get(ArtifactVersion, artifact_id)
    if not artifact: raise HTTPException(404, '成果不存在')
    require_workflow(artifact.workflow_id, db, user)
    authorized_product(db, user, workspace(db, db.get(Workflow, artifact.workflow_id)))
    if artifact.status != 'saved': raise HTTPException(409, '请先确认保存成果')
    text = '# ' + artifact.title + '\n\n> 审核状态：' + review_state(db, artifact)[0] + '\n> 内容来源：' + ('Agent 生成' if artifact.origin == 'agent' else '人工编辑') + '\n\n'
    text += '\n\n'.join(u['text'] + ('\n\n[图片占位：' + u['image_description'] + ']' if u['image_description'] else '') + (f"\n\n景别：{u.get('shot_size', '')}；运镜：{u.get('camera_movement', '')}；构图：{u.get('composition', '')}；时长：{u.get('duration_seconds', 0)}秒" if artifact.kind == 'storyboard' else '') for u in artifact.units)
    image_ids = list(dict.fromkeys(u['image_asset_id'] for u in artifact.units if u.get('image_asset_id')))
    if image_ids:
        from io import BytesIO
        from zipfile import ZipFile, ZIP_DEFLATED
        from app.api.v1.routes.workflow_assets import read
        buffer = BytesIO()
        size = 0
        with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
            for image_id in image_ids:
                data = read(artifact.workflow_id, image_id, db, user).body
                size += len(data)
                if size > 50 * 1024 * 1024: raise HTTPException(413, '图片导出超过50MB，请减少图片或分别下载')
                archive.writestr(f'images/{image_id}.jpg', data)
            text = '# ' + artifact.title + '\n\n> 审核状态：' + review_state(db, artifact)[0] + '\n\n' + '\n\n'.join(u['text'] + (f"\n\n![配图](images/{u['image_asset_id']}.jpg)" if u.get('image_asset_id') else '') + (f"\n\n景别：{u.get('shot_size', '')}；运镜：{u.get('camera_movement', '')}；构图：{u.get('composition', '')}；时长：{u.get('duration_seconds', 0)}秒" if artifact.kind == 'storyboard' else '') for u in artifact.units)
            archive.writestr('content.md', text)
        return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="content-{artifact.id}.zip"', 'Cache-Control': 'no-store'})
    return Response(text, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="content-{artifact.id}.md"', 'Cache-Control': 'no-store'})
