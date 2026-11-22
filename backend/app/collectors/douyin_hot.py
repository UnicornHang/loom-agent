"""Read Douyin's public web hot-search list; no login, video downloads or fallback data."""
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import quote
import httpx
from app.collectors.base import SourceAdapter, SourceItem, FetchBatch

class CollectionError(Exception):
    def __init__(self, message, blocked=False):
        super().__init__(message)
        self.blocked = blocked

class DouyinHotAdapter(SourceAdapter):
    source_id = 'douyin_hot_search'
    allowed_fields = frozenset({'word', 'sentence_id', 'hot_value', 'event_time'})
    endpoint = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'

    def __init__(self, transport=None):
        self.transport = transport

    def normalize(self, raw):
        word = raw.get('word')
        if not isinstance(word, str) or not word.strip(): raise ValueError('缺少话题标题')
        word = word.strip()[:300]
        sentence = str(raw.get('sentence_id') or '')
        valid_id = sentence.isascii() and sentence.isdigit() and len(sentence) <= 40
        item_id = sentence if valid_id else hashlib.sha256(word.encode()).hexdigest()
        url = f'https://www.douyin.com/hot/{sentence}' if valid_id else 'https://www.douyin.com/search/' + quote(word, safe='')
        heat = raw.get('hot_value')
        metrics = {}
        if type(heat) is int and 0 <= heat <= 10**15: metrics['hot_value'] = heat
        elif isinstance(heat, str) and heat.isascii() and heat.isdigit() and len(heat) <= 15: metrics['hot_value'] = int(heat)
        published_at = None
        try:
            timestamp = int(raw.get('event_time', 0))
            if 946684800 <= timestamp <= 4102444800: published_at = datetime.fromtimestamp(timestamp, timezone.utc)
        except (TypeError, ValueError, OverflowError): pass
        return SourceItem(source_id=self.source_id, source_item_id=item_id, title=word, source_url=url,
            content_type='text', published_at=published_at, summary='抖音公开热搜话题线索；未取得原视频或完整正文。', metrics=metrics, material_available=False)

    async def fetch(self, cursor=None, since=None):
        timeout = httpx.Timeout(20, connect=5)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport, follow_redirects=False, trust_env=False) as client:
                async with client.stream('GET', self.endpoint,
                    params={'device_platform': 'webapp', 'aid': 6383, 'channel': 'channel_pc_web', 'detail_list': 1},
                    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.douyin.com/', 'Accept': 'application/json', 'Accept-Encoding': 'identity'}) as response:
                    if response.status_code in (401, 403, 429): raise CollectionError('平台限制访问或触发限流，已停止本轮采集，请稍后重试。', blocked=True)
                    if response.status_code != 200: raise CollectionError(f'热榜请求失败（HTTP {response.status_code}）')
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000: raise CollectionError('热榜响应超过大小限制')
            value = json.loads(body)
            rows = value.get('data', {}).get('word_list')
            if type(value.get('status_code')) is not int or value['status_code'] != 0 or not isinstance(rows, list): raise CollectionError('平台响应结构变化或访问受限，未生成热点数据。')
            items = []
            seen = set()
            for rank, row in enumerate(rows[:100], 1):
                if not isinstance(row, dict): continue
                try: item = self.normalize(row)
                except ValueError: continue
                if item.source_item_id in seen: continue
                seen.add(item.source_item_id); item.rank = rank; items.append(item)
            if rows and not items: raise CollectionError('榜单条目均无法解析，可能需要更新采集器')
            return FetchBatch(items=items, raw_count=len(rows))
        except CollectionError: raise
        except (httpx.HTTPError, json.JSONDecodeError, AttributeError, TypeError):
            raise CollectionError('热榜请求超时、返回空响应或格式不兼容，请查看来源状态后重试。') from None
