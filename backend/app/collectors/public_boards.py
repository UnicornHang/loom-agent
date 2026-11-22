"""Bounded public board readers, independently implemented from daily-hot-mcp API leads."""
import hashlib
import json
import re
from urllib.parse import urlencode

import httpx

from app.collectors.base import SourceAdapter, SourceItem, FetchBatch
from app.collectors.douyin_hot import CollectionError


class PublicBoardAdapter(SourceAdapter):
    allowed_fields = frozenset({'title', 'id', 'rank', 'metrics', 'url'})

    def __init__(self, transport=None):
        self.transport = transport

    def rows(self, payload):
        raise NotImplementedError

    async def fetch(self, cursor=None, since=None):
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(20, connect=5),
                                         follow_redirects=False, trust_env=False) as client:
                async with client.stream('GET', self.endpoint, headers={
                    'User-Agent': 'Mozilla/5.0', 'Referer': self.referer,
                    'Accept': 'application/json', 'Accept-Encoding': 'identity',
                }) as response:
                    if response.status_code in (401, 403, 412, 429):
                        raise CollectionError('平台限制访问或触发限流，已停止本轮采集。', blocked=True)
                    if response.status_code != 200:
                        raise CollectionError(f'榜单请求失败（HTTP {response.status_code}）')
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise CollectionError('榜单响应超过大小限制')
            rows = self.rows(json.loads(body))
            if not isinstance(rows, list):
                raise CollectionError('平台响应结构变化，未生成热点数据。')
            items, seen = [], set()
            for rank, row in enumerate(rows[:100], 1):
                if not isinstance(row, dict) or row.get('is_ad'): continue
                try:
                    item = self.normalize(row)
                except ValueError:
                    continue
                if item.source_item_id in seen: continue
                seen.add(item.source_item_id)
                item.rank = rank
                items.append(item)
            if rows and not items:
                raise CollectionError('榜单条目均无法解析，可能需要更新采集器')
            return FetchBatch(items=items, raw_count=len(rows))
        except CollectionError:
            raise
        except (httpx.HTTPError, ValueError, AttributeError, TypeError, KeyError):
            raise CollectionError('榜单请求失败或格式不兼容，未使用占位数据。') from None

    def item(self, title, url, item_id=None, metrics=None, content_type='text'):
        if not isinstance(title, str) or not title.strip(): raise ValueError('缺少标题')
        title = title.strip()[:300]
        clean = {}
        for key, value in (metrics or {}).items():
            if type(value) is int and 0 <= value <= 10**15:
                clean[key] = value
            elif isinstance(value, str) and re.fullmatch(r'[0-9]{1,15}', value):
                clean[key] = int(value)
        return SourceItem(source_id=self.source_id, source_item_id=item_id or hashlib.sha256(title.encode()).hexdigest(),
                          title=title, source_url=url, content_type=content_type, metrics=clean,
                          summary='公开榜单线索；未取得完整正文或视频素材。', material_available=False)


class WeiboHotAdapter(PublicBoardAdapter):
    source_id = 'weibo_hot_search'
    endpoint = 'https://weibo.com/ajax/side/hotSearch'
    referer = 'https://weibo.com/'

    def rows(self, payload):
        if payload['ok'] != 1: raise CollectionError('微博榜单返回失败状态')
        return payload['data']['realtime']

    def normalize(self, raw):
        title = raw.get('word')
        return self.item(title, 'https://s.weibo.com/weibo?' + urlencode({'q': title}),
                         metrics={'hot_value': raw.get('num')})


class BilibiliPopularAdapter(PublicBoardAdapter):
    source_id = 'bilibili_popular'
    endpoint = 'https://api.bilibili.com/x/web-interface/popular?pn=1&ps=50'
    referer = 'https://www.bilibili.com/'

    def rows(self, payload):
        if payload['code'] != 0: raise CollectionError('B站榜单返回失败状态')
        return payload['data']['list']

    def normalize(self, raw):
        bvid = raw.get('bvid')
        if not isinstance(bvid, str) or not re.fullmatch(r'BV[A-Za-z0-9]{10}', bvid):
            raise ValueError('无效视频标识')
        stat = raw.get('stat') or {}
        return self.item(raw.get('title'), f'https://www.bilibili.com/video/{bvid}', bvid,
                         {'hot_value': stat.get('view'), 'view': stat.get('view'), 'like': stat.get('like')}, 'video')


class XiaohongshuHotAdapter(PublicBoardAdapter):
    source_id = 'xiaohongshu_hot_search'
    endpoint = 'https://www.xiaohongshu.com/web_api/sns/v1/search/hot_list'
    referer = 'https://www.xiaohongshu.com/'

    def rows(self, payload):
        if payload['success'] is not True: raise CollectionError('小红书热词接口返回失败状态')
        return payload['data']['queries']

    def normalize(self, raw):
        title = raw.get('query')
        return self.item(title, 'https://www.xiaohongshu.com/search_result?' + urlencode({'keyword': title}))
