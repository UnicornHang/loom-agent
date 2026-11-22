from io import BytesIO
from uuid import uuid4
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError
from botocore.exceptions import ClientError
from app.config import settings
from app.db import get_db
from app.models import User, WorkflowAsset, ArtifactVersion, WorkflowWorkspace
from app.security import current_user, require_csrf
from app.api.v1.routes.workflows import require_workflow
from app.api.v1.routes.workspaces import editable, authorized_product, advance, event, artifact_read
from app.api.v1.routes.product_assets import storage, LIMIT

router = APIRouter(tags=['workflow-assets'])

@router.post('/workflows/{workflow_id}/artifacts/{artifact_id}/units/{unit_id}/image', status_code=201, dependencies=[Depends(require_csrf)])
async def attach(workflow_id: str, artifact_id: str, unit_id: str, request: Request, revision: int = Query(ge=0), db: Session = Depends(get_db), user: User = Depends(current_user)):
    # Read and validate the bounded upload before taking the workflow write lock.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > LIMIT: raise HTTPException(413, '图片不能超过10MB')
    try:
        with Image.open(BytesIO(body)) as picture:
            if picture.format not in ('JPEG', 'PNG', 'WEBP') or picture.width * picture.height > 25_000_000: raise ValueError()
            picture.load()
            output = BytesIO()
            # Composite transparency on white for document export.
            rgba = picture.convert('RGBA')
            background = Image.new('RGBA', rgba.size, 'white')
            background.alpha_composite(rgba)
            background.convert('RGB').save(output, format='JPEG', quality=92)
            image_bytes = output.getvalue()
            if len(image_bytes) > LIMIT * 2: raise ValueError()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError): raise HTTPException(400, '请上传有效的JPG、PNG或WebP图片') from None
    workflow, workspace = editable(db, workflow_id, user)
    authorized_product(db, user, workspace)
    artifact = db.get(ArtifactVersion, artifact_id)
    if not artifact or artifact.workflow_id != workflow_id or artifact.workspace_revision != workspace.revision or workspace.revision != revision or workflow.current_step not in ('drafting', 'storyboarding'): raise HTTPException(409, '请先保存并选择当前稿件')
    if workflow.hotspot.content_type == 'text': raise HTTPException(409, '纯文字流程不包含配图步骤')
    if not any(u['id'] == unit_id and u.get('image_description') for u in artifact.units): raise HTTPException(422, '该段落没有图片占位描述')
    image_id = uuid4().hex
    key = f'workflows/{user.tenant_id}/{workflow_id}/{image_id}.jpg'
    client = storage()
    try:
        try: client.create_bucket(Bucket=settings.object_storage_bucket)
        except ClientError as error:
            if error.response['Error']['Code'] not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'): raise
        client.put_object(Bucket=settings.object_storage_bucket, Key=key, Body=image_bytes, ContentType='image/jpeg')
    except Exception: raise HTTPException(503, '图片存储暂不可用') from None
    # Object upload can outlive a rolled-back transaction; retention cleanup handles unreferenced objects.
    advance(db, workspace, revision)
    db.add(WorkflowAsset(id=image_id, workflow_id=workflow_id, object_key=key, content_hash=hashlib.sha256(image_bytes).hexdigest()))
    units = [{**unit, 'image_asset_id': image_id if unit['id'] == unit_id else unit.get('image_asset_id')} for unit in artifact.units]
    version = (db.scalar(select(func.max(ArtifactVersion.version)).where(ArtifactVersion.workflow_id == workflow_id)) or 0) + 1
    digest = hashlib.sha256(json.dumps({'title': artifact.title, 'units': units}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    row = ArtifactVersion(workflow_id=workflow_id, version=version, workspace_revision=revision + 1, kind=artifact.kind, title=artifact.title, units=units, content_hash=digest, origin='manual')
    db.add(row)
    event(db, workflow, '图片已填入占位', '人工上传配图，保存新内容版本；旧审核不会沿用。')
    db.commit(); db.refresh(row)
    return artifact_read(row, db)

@router.get('/workflows/{workflow_id}/assets/{asset_id}')
def read(workflow_id: str, asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_workflow(workflow_id, db, user)
    workspace = db.get(WorkflowWorkspace, workflow_id)
    if workspace: authorized_product(db, user, workspace)
    asset = db.get(WorkflowAsset, asset_id)
    if not asset or asset.workflow_id != workflow_id: raise HTTPException(404, '图片不存在')
    try:
        response = storage().get_object(Bucket=settings.object_storage_bucket, Key=asset.object_key)
        with response['Body'] as stream: data = stream.read(LIMIT * 2)
    except Exception: raise HTTPException(503, '图片存储暂不可用') from None
    return Response(data, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})
