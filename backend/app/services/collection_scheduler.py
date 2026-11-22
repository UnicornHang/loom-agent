"""Source scheduling before credentials and authorized adapters are available."""
from datetime import timedelta
from sqlalchemy import select
from app.models import SourceConfiguration, CollectionRun, utcnow

def preflight(db, source, trigger):
    # No platform scraping or invented content: an adapter must be implemented and verified first.
    row = CollectionRun(source_id=source.id, source_revision=source.revision, trigger=trigger, status='blocked',
        summary='未发起外部请求：来源授权、凭据及适配器尚未接入。当前仅执行调度预检，不代表已覆盖该平台。')
    db.add(row)
    return row

def dispatch_due(db):
    now = utcnow()
    sources = db.scalars(select(SourceConfiguration).where(SourceConfiguration.enabled == True, SourceConfiguration.next_run_at <= now).with_for_update(skip_locked=True).limit(50)).all()
    for source in sources:
        preflight(db, source, 'scheduled')
        source.next_run_at = now + timedelta(minutes=source.interval_minutes)
    db.commit()
    return len(sources)
