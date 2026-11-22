from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import BudgetPolicy, UsageReservation, User
from app.security import require_roles, require_csrf
from app.services.model_budget import money
from app.services.audit import record
from app.services.locks import tenant_lock

router = APIRouter(prefix='/budget', tags=['budget'])

class Policy(BaseModel):
    daily_limit: float = Field(ge=0, le=1000)
    currency: Literal['CNY', 'USD'] = 'CNY'

@router.get('')
def get_policy(db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    row = db.get(BudgetPolicy, user.tenant_id)
    return {'daily_limit': row.daily_limit_micros / 1_000_000 if row else 0, 'currency': row.currency if row else 'CNY'}

@router.put('', dependencies=[Depends(require_csrf)])
def set_policy(payload: Policy, db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    tenant_lock(db, user.tenant_id, 'budget-policy')
    row = db.scalar(select(BudgetPolicy).where(BudgetPolicy.tenant_id == user.tenant_id).with_for_update())
    if row is None:
        row = BudgetPolicy(tenant_id=user.tenant_id)
        db.add(row)
    row.daily_limit_micros = money(payload.daily_limit)
    # Changing currency with an existing ledger would mix units.
    if row.currency and row.currency != payload.currency and db.scalar(select(UsageReservation.id).where(UsageReservation.tenant_id == user.tenant_id).limit(1)):
        from fastapi import HTTPException
        raise HTTPException(409, '已有计费记录，暂不支持直接切换记账币种')
    row.currency = payload.currency
    record(db, user, 'budget.updated', user.tenant_id, f'每日预算调整为 {payload.daily_limit} {payload.currency}')
    db.commit()
    return payload

@router.get('/usage')
def usage(db: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    return [{'id': row.id, 'day': row.day, 'amount': row.amount_micros / 1_000_000, 'status': row.status} for row in db.scalars(select(UsageReservation).where(UsageReservation.tenant_id == user.tenant_id).order_by(UsageReservation.created_at.desc()).limit(100))]
