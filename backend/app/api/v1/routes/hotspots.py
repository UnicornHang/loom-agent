from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Hotspot, User
from app.schemas import HotspotCreate, HotspotRead
from app.security import current_user, require_csrf, require_roles

router = APIRouter(prefix="/hotspots", tags=["hotspots"])


@router.get("", response_model=list[HotspotRead])
def list_hotspots(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Hotspot).where(Hotspot.tenant_id == user.tenant_id).order_by(Hotspot.collected_at.desc().nullslast(), Hotspot.created_at.desc())).all()


@router.post("", response_model=HotspotRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def create_hotspot(payload: HotspotCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "creator"))):
    hotspot = Hotspot(**payload.model_dump(), source_kind="manual", tenant_id=user.tenant_id)
    db.add(hotspot)
    db.commit()
    db.refresh(hotspot)
    return hotspot
