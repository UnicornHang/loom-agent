from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LoginSession, User
from app.schemas import LoginRequest, PasswordChange, UserRead
from app.security import (CSRF_COOKIE, SESSION_COOKIE, SESSION_HOURS, current_session,
                          current_user, ensure_aware, hash_password, new_session,
                          now_utc, require_csrf, verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.tenant_id == "demo", User.username == payload.username))
    if user and user.locked_until and ensure_aware(user.locked_until) > now_utc():
        raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试")
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        if user and user.is_active:
            user.failed_attempts += 1
            if user.failed_attempts >= 5:
                user.locked_until = now_utc() + timedelta(minutes=15)
                user.failed_attempts = 0
            db.commit()
        raise HTTPException(status_code=401, detail="账号或密码错误")
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    token, csrf = new_session(db, user)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=False, samesite="lax",
                        max_age=SESSION_HOURS * 3600, path="/")
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=False, samesite="lax",
                        max_age=SESSION_HOURS * 3600, path="/")
    return user


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.post("/change-password", dependencies=[Depends(require_csrf)])
def change_password(payload: PasswordChange, response: Response, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    for session in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
        db.delete(session)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}
