"""Password, session and CSRF primitives for the browser workbench."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LoginSession, User

SESSION_COOKIE = "loom_session"
CSRF_COOKIE = "loom_csrf"
SESSION_HOURS = 12
_password_hasher = PasswordHasher()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session(db: Session, user: User) -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(user_id=user.id, token_hash=digest(token), csrf_hash=digest(csrf),
                        expires_at=now_utc() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return token, csrf


def current_session(request: Request, db: Session = Depends(get_db)) -> LoginSession:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == digest(token)))
    if session is None or ensure_aware(session.expires_at) <= now_utc():
        raise HTTPException(status_code=401, detail="登录已过期")
    return session


def current_user(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)) -> User:
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="账号不可用")
    return user


def require_csrf(request: Request, session: LoginSession = Depends(current_session),
                 x_csrf_token: str | None = Header(default=None)) -> None:
    cookie = request.cookies.get(CSRF_COOKIE)
    if not cookie or not x_csrf_token or not secrets.compare_digest(cookie, x_csrf_token):
        raise HTTPException(status_code=403, detail="请求校验失败，请刷新页面后重试")
    if not secrets.compare_digest(digest(cookie), session.csrf_hash):
        raise HTTPException(status_code=403, detail="请求校验失败，请重新登录")


def require_roles(*roles: str):
    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="没有此操作权限")
        return user
    return check
