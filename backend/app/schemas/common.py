from __future__ import annotations

from typing import Any

from app.core.config import settings


def ok(data: Any = None, meta: dict | None = None) -> dict:
    return {"success": True, "data": data, "meta": meta or {}}


def paginated(result: dict) -> dict:
    """`result` is the dict shape returned by app.analytics.entities.list_entity_metrics
    (items/page/page_size/total/total_pages)."""
    items = result["items"]
    meta = {k: v for k, v in result.items() if k != "items"}
    return ok(items, meta)


class PageParams:
    def __init__(self, page: int = 1, page_size: int | None = None):
        self.page = max(page, 1)
        self.page_size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
