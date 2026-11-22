from celery import Celery
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import OutboxTask

celery = Celery('loom', broker=settings.redis_url)
celery.conf.update(task_serializer='json', accept_content=['json'], worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True, task_acks_late=True, task_reject_on_worker_lost=True,
    beat_schedule={'outbox': {'task': 'loom.dispatch', 'schedule': 5.0}, 'sources': {'task': 'loom.sources', 'schedule': 60.0}})

@celery.task(name='loom.sources')
def source_schedule():
    from app.services.collection_scheduler import dispatch_due
    with SessionLocal() as db: return dispatch_due(db)

@celery.task(name='loom.dispatch')
def dispatch():
    with SessionLocal() as db:
        rows = db.scalars(select(OutboxTask).where(OutboxTask.sent == False).with_for_update(skip_locked=True).limit(20)).all()
        for row in rows:
            run.delay(row.run_id)
            row.sent = True
        db.commit()

@celery.task(name='loom.run', soft_time_limit=1740, time_limit=1800)
def run(run_id):
    from langgraph.checkpoint.postgres import PostgresSaver
    from app.agents.runtime import execute
    url = settings.database_url.replace('postgresql+psycopg://', 'postgresql://')
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        execute(run_id, SessionLocal, saver)
