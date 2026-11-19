from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AgentEvent, Hotspot, User, Workflow
from app.schemas import AgentEventRead, WorkflowCreate, WorkflowRead
from app.security import current_user, require_csrf, require_roles

router = APIRouter(prefix="/workflows", tags=["workflows"])


def require_workflow(workflow_id: str, db: Session, user: User) -> Workflow:
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.tenant_id != user.tenant_id or (user.role != "admin" and workflow.created_by_user_id != user.id):
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin", "creator"))):
    hotspot = db.get(Hotspot, payload.hotspot_id)
    if hotspot is None or hotspot.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="热点不存在")
    workflow = Workflow(hotspot_id=hotspot.id, tenant_id=user.tenant_id, created_by_user_id=user.id)
    db.add(workflow)
    db.flush()
    db.add(AgentEvent(workflow_id=workflow.id, sequence=1, agent_type="system", event_type="created",
                      title="工作流已创建", summary="等待确认素材，尚未调用模型。"))
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("", response_model=list[WorkflowRead])
def list_workflows(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Workflow).where(Workflow.tenant_id == user.tenant_id)
    if user.role != "admin":
        query = query.where(Workflow.created_by_user_id == user.id)
    return db.scalars(query.order_by(Workflow.created_at.desc())).all()


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return require_workflow(workflow_id, db, user)


@router.get("/{workflow_id}/events", response_model=list[AgentEventRead])
def get_events(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_workflow(workflow_id, db, user)
    return db.scalars(select(AgentEvent).where(AgentEvent.workflow_id == workflow_id).order_by(AgentEvent.sequence)).all()


@router.post("/{workflow_id}/run", dependencies=[Depends(require_csrf)])
def run_workflow(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_workflow(workflow_id, db, user)
    raise HTTPException(status_code=503, detail="Agent 模型尚未配置；当前骨架不会伪造生成结果")
