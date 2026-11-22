import asyncio

import httpx
import pytest

from app.collectors.douyin_hot import CollectionError
from app.collectors.public_boards import WeiboHotAdapter, BilibiliPopularAdapter, XiaohongshuHotAdapter
from app.collectors.registry import ADAPTERS
from app.api.v1.routes.sources import SourceWrite


CASES = [
    (WeiboHotAdapter, {'ok': 1, 'data': {'realtime': [
        {'word': '真实话题', 'num': '123'}, {'word': '广告', 'is_ad': 1},
        {'word': '真实话题', 'num': 456}, {'word': ''}]}}, 4, 1),
    (BilibiliPopularAdapter, {'code': 0, 'data': {'list': [
        {'title': '视频', 'bvid': 'BV1234567890', 'stat': {'view': 123, 'like': 5}},
        {'title': '无效', 'bvid': '../redirect'}]}}, 2, 1),
    (XiaohongshuHotAdapter, {'success': True, 'data': {'queries': [
        {'query': '护肤 & 耳机'}, {'query': '护肤 & 耳机'}]}}, 2, 1),
]


@pytest.mark.parametrize('cls,payload,raw,valid', CASES)
def test_board_normalization(cls, payload, raw, valid):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload)
    batch = asyncio.run(cls(httpx.MockTransport(respond)).fetch())
    assert batch.raw_count == raw and len(batch.items) == valid
    item = batch.items[0]
    assert item.source_id == cls.source_id and item.rank == 1
    assert not item.material_available
    assert len(requests) == 1
    if cls is BilibiliPopularAdapter:
        assert item.content_type == 'video' and item.metrics['view'] == 123
        assert item.source_url == 'https://www.bilibili.com/video/BV1234567890'
    elif cls is WeiboHotAdapter:
        assert item.metrics['hot_value'] == 123
    else:
        assert item.metrics == {} and '%26' in item.source_url


@pytest.mark.parametrize('cls', [case[0] for case in CASES])
@pytest.mark.parametrize('status,payload', [(429, {}), (403, {}), (200, {}), (200, []), (200, {'success': False})])
def test_restrictions_and_bad_shapes_never_return_placeholder(cls, status, payload):
    adapter = cls(httpx.MockTransport(lambda request: httpx.Response(status, json=payload)))
    with pytest.raises(CollectionError) as error:
        asyncio.run(adapter.fetch())
    assert error.value.blocked == (status in (403, 429))


@pytest.mark.parametrize('cls,payload', [
    (WeiboHotAdapter, {'ok': 1, 'data': {'realtime': []}}),
    (BilibiliPopularAdapter, {'code': 0, 'data': {'list': []}}),
    (XiaohongshuHotAdapter, {'success': True, 'data': {'queries': []}}),
])
def test_empty_success_is_distinct(cls, payload):
    batch = asyncio.run(cls(httpx.MockTransport(lambda request: httpx.Response(200, json=payload))).fetch())
    assert batch.items == [] and batch.raw_count == 0


@pytest.mark.parametrize('cls,payload,raw,valid', CASES)
def test_registered_source_ingestion(cls, payload, raw, valid):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import SourceConfiguration, CollectionRun, Hotspot
    from app.services.collection_scheduler import preflight, execute_collection

    assert ADAPTERS[cls.source_id] is cls
    SourceWrite(name='测试', adapter=cls.source_id, industry='通用')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        source = SourceConfiguration(tenant_id='demo', name='测试', adapter=cls.source_id,
                                     industry='通用', keywords=[], interval_minutes=60)
        db.add(source); db.flush()
        run = preflight(db, source, 'manual'); db.commit()
        run_id, source_id = run.id, source.id
    factory = lambda: cls(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    execute_collection(run_id, sessions, factory)
    with sessions() as db:
        assert db.get(CollectionRun, run_id).status == 'succeeded'
        item = db.scalar(select(Hotspot))
        assert item.source_kind == cls.source_id
        assert item.content_type == ('video' if cls is BilibiliPopularAdapter else 'text')
        run = preflight(db, db.get(SourceConfiguration, source_id), 'manual'); db.commit()
        second_id = run.id
    execute_collection(second_id, sessions, factory)
    with sessions() as db:
        assert db.get(CollectionRun, second_id).counts['updated'] == valid
        assert len(db.scalars(select(Hotspot)).all()) == valid
    engine.dispose()
