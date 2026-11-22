"""Explicit allowlist; source configuration cannot supply arbitrary request URLs."""
from app.collectors.douyin_hot import DouyinHotAdapter
from app.collectors.public_boards import WeiboHotAdapter, BilibiliPopularAdapter, XiaohongshuHotAdapter

ADAPTERS = {adapter.source_id: adapter for adapter in (
    DouyinHotAdapter, WeiboHotAdapter, BilibiliPopularAdapter, XiaohongshuHotAdapter,
)}
