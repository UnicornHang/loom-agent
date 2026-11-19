from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProductGrant, ProductGroup, User
from app.schemas import ProductGrantCreate, ProductGroupCreate, ProductGroupRead, UserRead
from app.security import current_user, require_csrf, require_roles

router = APIRouter(prefix="/product-groups", tags=["product-groups"])


@router.get("", response_model=list[ProductGroupRead])
def list_groups(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ProductGroup).where(ProductGroup.tenant_id == user.tenant_id)
    if user.role != "admin":
        query = query.join(ProductGrant, ProductGrant.group_id == ProductGroup.id).where(ProductGrant.user_id == user.id)
    return db.scalars(query.order_by(ProductGroup.name)).all()


@router.post("", response_model=ProductGroupRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def create_group(payload: ProductGroupCreate, db: Session = Depends(get_db),
                 admin: User = Depends(require_roles("admin"))):
    group = ProductGroup(tenant_id=admin.tenant_id, name=payload.name)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="分组名称已存在") from None
    db.refresh(group)
    return group


@router.post("/{group_id}/grants", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def grant_group(group_id: str, payload: ProductGrantCreate, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    group = db.get(ProductGroup, group_id)
    user = db.get(User, payload.user_id)
    if group is None or user is None or group.tenant_id != admin.tenant_id or user.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="分组或用户不存在")
    if db.scalar(select(ProductGrant).where(ProductGrant.group_id == group_id, ProductGrant.user_id == user.id)):
        return {"ok": True}
    db.add(ProductGrant(group_id=group_id, user_id=user.id))
    db.commit()
    return {"ok": True}


@router.get("/{group_id}/grants", response_model=list[UserRead])
def list_group_grants(group_id: str, db: Session = Depends(get_db),
                      admin: User = Depends(require_roles("admin"))):
    group = db.get(ProductGroup, group_id)
    if group is None or group.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="分组不存在")
    return db.scalars(select(User).join(ProductGrant, ProductGrant.user_id == User.id)
                      .where(ProductGrant.group_id == group_id, User.tenant_id == admin.tenant_id)
                      .order_by(User.username)).all()


@router.delete("/{group_id}/grants/{user_id}", dependencies=[Depends(require_csrf)])
def revoke_group(group_id: str, user_id: str, db: Session = Depends(get_db),
                 admin: User = Depends(require_roles("admin"))):
    group = db.get(ProductGroup, group_id)
    if group is None or group.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="分组不存在")
    grant = db.scalar(select(ProductGrant).where(ProductGrant.group_id == group_id, ProductGrant.user_id == user_id))
    if grant:
        db.delete(grant)
        db.commit()
    return {"ok": True}
