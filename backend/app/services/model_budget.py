from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models import BudgetPolicy, UsageReservation

def money(value):
    return int((Decimal(str(value)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))

def reserve(db, tenant_id, connection, messages, max_tokens, task_budget):
    policy = db.scalar(select(BudgetPolicy).where(BudgetPolicy.tenant_id == tenant_id).with_for_update())
    options = connection.options or {}
    if not policy or policy.daily_limit_micros <= 0:
        raise HTTPException(409, '请先配置公司每日 AI 预算')
    if policy.currency != options.get('currency', 'CNY'): raise HTTPException(409, '模型计价币种与公司预算不一致')
    if options.get('input_price', 0) <= 0 or (options.get('capability') != 'embedding' and options.get('output_price', 0) <= 0): raise HTTPException(409, '请先填写模型输入和输出价格')
    # UTF-8 bytes conservatively bound standard byte-based text tokenizers, plus message framing.
    input_tokens = sum(len(m['content'].encode()) + 256 for m in messages) + 1024
    amount = int((Decimal(input_tokens) * Decimal(str(options['input_price'])) + Decimal(max_tokens) * Decimal(str(options['output_price']))).to_integral_value(rounding=ROUND_CEILING))
    if task_budget <= 0 or amount > money(task_budget): raise HTTPException(409, '单次预算未配置或不足')
    day = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    used = db.scalar(select(func.coalesce(func.sum(UsageReservation.amount_micros), 0)).where(UsageReservation.tenant_id == tenant_id, UsageReservation.day == day))
    if used + amount > policy.daily_limit_micros: raise HTTPException(409, '每日 AI 预算不足')
    row = UsageReservation(tenant_id=tenant_id, day=day, amount_micros=amount)
    db.add(row)
    db.flush()
    return row

def settle(row, usage, options):
    if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and usage[k] >= 0 for k in ('prompt_tokens', 'completion_tokens')):
        row.amount_micros = int((Decimal(usage['prompt_tokens']) * Decimal(str(options['input_price'])) + Decimal(usage['completion_tokens']) * Decimal(str(options['output_price']))).to_integral_value(rounding=ROUND_CEILING))
        row.status = 'settled'
    else:
        row.status = 'estimated'
