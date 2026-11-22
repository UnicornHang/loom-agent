from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AuditEvent, User
from app.security import require_roles

router = APIRouter(prefix='/audit-events', tags=['audit'])

@router.get('')
def events(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return [{key: getattr(row, key) for key in ('id', 'user_id', 'action', 'object_id', 'summary', 'created_at')} for row in db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == user.tenant_id).order_by(AuditEvent.created_at.desc()).limit(limit))]
