"""Public trend scheduling and ingestion; unimplemented adapters remain preflight-only."""
from datetime import timedelta, timezone
import asyncio
from sqlalchemy import select
from app.models import SourceConfiguration, CollectionRun, Hotspot, utcnow
from app.collectors.douyin_hot import CollectionError
from app.services.locks import tenant_lock
from app.collectors.registry import ADAPTERS

def preflight(db, source, trigger):
    db.refresh(source, with_for_update=True)
    pending = db.scalar(select(CollectionRun).where(CollectionRun.source_id == source.id, CollectionRun.status.in_(['queued', 'running'])).order_by(CollectionRun.created_at.desc()).limit(1))
    if pending:
        created = pending.created_at.replace(tzinfo=timezone.utc) if pending.created_at.tzinfo is None else pending.created_at
        if utcnow() - created < timedelta(minutes=5): return pending
        pending.status = 'failed'; pending.summary = '任务超过执行窗口，已停止等待；可重新发起采集。'
    if source.adapter in ADAPTERS:
        row = CollectionRun(source_id=source.id, source_revision=source.revision, trigger=trigger, status='queued',
            summary='采集任务已入队，等待后台获取公开榜单。', snapshot={'adapter': source.adapter, 'tenant_id': source.tenant_id})
        db.add(row); db.flush()
        return row
    row = CollectionRun(source_id=source.id, source_revision=source.revision, trigger=trigger, status='blocked',
        summary='未发起外部请求：来源授权、凭据及适配器尚未接入。当前仅执行调度预检，不代表已覆盖该平台。')
    db.add(row)
    return row


def execute_collection(run_id, session_factory, adapter_factory=None):
    with session_factory() as db:
        run = db.get(CollectionRun, run_id)
        if not run or run.status not in ('queued', 'running'): return
        source = db.get(SourceConfiguration, run.source_id)
        if not source or source.revision != run.source_revision or (run.trigger == 'scheduled' and not source.enabled):
            run.status = 'stale'; run.summary = '来源配置已变化或定时来源已停用，本轮未提交数据。'; db.commit(); return
        if source.adapter not in ADAPTERS or run.snapshot.get('adapter') != source.adapter:
            run.status = 'blocked'; run.summary = '当前来源适配器未实现。'; db.commit(); return
        run.status = 'running'; run.summary = '正在读取公开榜单，未下载视频或正文。'; db.commit()
        try:
            batch = asyncio.run((adapter_factory or ADAPTERS[source.adapter])().fetch(None, None))
            # Only ingestion is serialized; no external request holds this database lock.
            tenant_lock(db, source.tenant_id, 'public-board-ingestion')
            db.refresh(run, with_for_update=True); db.refresh(source)
            if run.status != 'running': db.rollback(); return
            if source.revision != run.source_revision or (run.trigger == 'scheduled' and not source.enabled):
                run.status = 'stale'; run.summary = '采集期间来源配置发生变化，结果未入库。'; db.commit(); return
            inserted = updated = 0
            now = utcnow()
            for item in batch.items:
                existing = db.scalar(select(Hotspot).where(Hotspot.tenant_id == source.tenant_id, Hotspot.source_kind == source.adapter, Hotspot.source_item_id == item.source_item_id))
                metrics = {**item.metrics, 'rank': item.rank, 'material_available': False, 'is_topic': item.content_type == 'text'}
                if existing:
                    existing.title = item.title; existing.source_url = item.source_url
                    existing.source_metrics = metrics; existing.collected_at = now
                    updated += 1
                else:
                    db.add(Hotspot(tenant_id=source.tenant_id, source_kind=source.adapter, source_item_id=item.source_item_id,
                        title=item.title, summary=item.summary, content_type=item.content_type, source_url=item.source_url, industry='通用', source_metrics=metrics, collected_at=now))
                    inserted += 1
            run.counts = {'received': batch.raw_count, 'valid': len(batch.items), 'inserted': inserted, 'updated': updated}
            run.status = 'succeeded' if batch.items else 'empty'
            run.summary = f'取得 {len(batch.items)} 条榜单线索，新增 {inserted} 条，更新 {updated} 条；仅榜单线索，未取得原始作品。'
            db.commit()
        except Exception as error:
            db.rollback()
            run = db.get(CollectionRun, run_id)
            db.refresh(run, with_for_update=True)
            if run.status not in ('queued', 'running'): db.rollback(); return
            run.status = 'blocked' if isinstance(error, CollectionError) and error.blocked else 'failed'
            run.summary = str(error) if isinstance(error, CollectionError) else '采集或入库失败，请稍后重试；未使用占位数据。'
            db.commit()

def dispatch_due(db):
    now = utcnow()
    sources = db.scalars(select(SourceConfiguration).where(SourceConfiguration.enabled == True, SourceConfiguration.next_run_at <= now).with_for_update(skip_locked=True).limit(50)).all()
    for source in sources:
        preflight(db, source, 'scheduled')
        source.next_run_at = now + timedelta(minutes=source.interval_minutes)
    db.commit()
    return len(sources)
