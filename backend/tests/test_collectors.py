import asyncio
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import SourceConfiguration, CollectionRun, Hotspot
from app.collectors.douyin_hot import DouyinHotAdapter, CollectionError
from app.services.collection_scheduler import preflight, execute_collection

def adapter_for(payload, status=200):
    return DouyinHotAdapter(httpx.MockTransport(lambda request: httpx.Response(status, json=payload)))

def test_douyin_normalizes_real_fields_and_deduplicates():
    adapter = adapter_for({'status_code': 0, 'data': {'word_list': [
        {'word': '耳机新品', 'sentence_id': '1234', 'hot_value': 123456},
        {'word': '耳机新品', 'sentence_id': '1234', 'hot_value': 123456},
        {'word': '另一话题', 'hot_value': 'unknown'}, {'word': ''},
    ]}})
    batch = asyncio.run(adapter.fetch(None, None))
    assert batch.raw_count == 4 and len(batch.items) == 2
    assert batch.items[0].source_url == 'https://www.douyin.com/hot/1234'
    assert batch.items[0].metrics == {'hot_value': 123456}
    assert batch.items[0].rank == 1 and not batch.items[0].material_available
    assert batch.items[1].metrics == {}

@pytest.mark.parametrize('status', [403, 429])
def test_platform_restriction_stops_without_fallback(status):
    with pytest.raises(CollectionError) as error: asyncio.run(adapter_for({}, status).fetch(None, None))
    assert error.value.blocked

def test_changed_shape_and_empty_board_are_distinct():
    with pytest.raises(CollectionError): asyncio.run(adapter_for({'status_code': 0, 'data': {}}).fetch(None, None))
    batch = asyncio.run(adapter_for({'status_code': 0, 'data': {'word_list': []}}).fetch(None, None))
    assert batch.items == [] and batch.raw_count == 0

def test_collection_ingests_updates_and_isolates_tenants():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    def queue(tenant='demo'):
        with sessions() as db:
            source = db.scalar(select(SourceConfiguration).where(SourceConfiguration.tenant_id == tenant))
            if not source:
                source = SourceConfiguration(tenant_id=tenant, name='抖音热搜', adapter='douyin_hot_search', industry='通用', keywords=[], interval_minutes=60)
                db.add(source); db.flush()
            run = preflight(db, source, 'manual'); db.commit()
            return run.id, source.id
    payload = {'status_code': 0, 'data': {'word_list': [{'word': '真实标题', 'sentence_id': '123', 'hot_value': 100}]}}
    factory = lambda: adapter_for(payload)
    first, source_id = queue()
    with sessions() as db:
        existing = preflight(db, db.get(SourceConfiguration, source_id), 'manual')
        assert existing.id == first
    execute_collection(first, sessions, factory)
    execute_collection(first, sessions, lambda: pytest.fail('重复任务不应再次取数'))
    with sessions() as db:
        run = db.get(CollectionRun, first)
        assert run.status == 'succeeded' and run.counts['inserted'] == 1
        assert db.scalars(select(Hotspot)).first().source_metrics['hot_value'] == 100
    payload['data']['word_list'][0]['hot_value'] = 200
    second, _ = queue()
    execute_collection(second, sessions, factory)
    with sessions() as db:
        assert db.get(CollectionRun, second).counts['updated'] == 1
        assert len(db.scalars(select(Hotspot)).all()) == 1
        assert db.scalars(select(Hotspot)).first().source_metrics['hot_value'] == 200
    foreign, _ = queue('another-company')
    execute_collection(foreign, sessions, factory)
    with sessions() as db: assert len(db.scalars(select(Hotspot)).all()) == 2
    stale, source_id = queue()
    with sessions() as db:
        db.get(SourceConfiguration, source_id).revision += 1; db.commit()
    execute_collection(stale, sessions, lambda: pytest.fail('过期配置不应发起请求'))
    with sessions() as db: assert db.get(CollectionRun, stale).status == 'stale'
    engine.dispose()

def test_failure_does_not_insert_placeholder():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        source = SourceConfiguration(tenant_id='demo', name='抖音', adapter='douyin_hot_search', industry='通用', keywords=[], interval_minutes=60)
        db.add(source); db.flush()
        run = preflight(db, source, 'manual'); db.commit(); run_id = run.id
    execute_collection(run_id, sessions, lambda: adapter_for({}, 429))
    with sessions() as db:
        assert db.get(CollectionRun, run_id).status == 'blocked'
        assert db.scalars(select(Hotspot)).all() == []
    engine.dispose()
