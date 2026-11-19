from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LoginSession, User
from app.schemas import UserActiveUpdate, UserCreate, UserRead
from app.security import hash_password, require_csrf, require_roles

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return db.scalars(select(User).where(User.tenant_id == admin.tenant_id).order_by(User.username)).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    user = User(tenant_id=admin.tenant_id, username=payload.username,
                password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在") from None
    db.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=UserRead, dependencies=[Depends(require_csrf)])
def set_user_active(user_id: str, payload: UserActiveUpdate, db: Session = Depends(get_db),
                    admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="不能停用当前账号")
    user.is_active = payload.is_active
    if not user.is_active:
        for session in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
            db.delete(session)
    db.commit()
    db.refresh(user)
    return user
