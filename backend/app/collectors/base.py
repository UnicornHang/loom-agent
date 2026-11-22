"""Source adapter boundary for authorized collection integrations."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    source_id: str
    source_item_id: str
    title: str
    source_url: str
    content_type: Literal["text", "article", "video"]
    published_at: datetime | None = None
    summary: str = ""
    metrics: dict[str, int] = Field(default_factory=dict)
    material_available: bool = False
    rank: int | None = None


class FetchBatch(BaseModel):
    items: list[SourceItem]
    next_cursor: str | None = None
    raw_count: int = 0


class SourceAdapter(ABC):
    source_id: str
    allowed_fields: frozenset[str]

    @abstractmethod
    async def fetch(self, cursor: str | None, since: datetime | None) -> FetchBatch:
        """Read one permitted page, applying source-specific rate limits."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> SourceItem:
        """Convert allowed provider fields into a source item."""
