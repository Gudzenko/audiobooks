from fastmcp import Client

from store.mcp.schemas import BookSearchItem
from store.mcp.server import mcp
from store.mcp.text_matching import normalize_text

from .contracts import CatalogFilterAmbiguous, CatalogSearchResult
from .schemas import CatalogSearchFilters


class LocalCatalogProvider:
    def __init__(self, *, timeout: float = 10):
        self.timeout = timeout

    async def search_books(
        self,
        filters: CatalogSearchFilters,
        *,
        limit: int = 1000,
    ) -> CatalogSearchResult:
        async with Client(mcp, name="audiobooks-chat", timeout=self.timeout) as client:
            author_ids = await self._resolve_ids(
                client, "author", filters.author_names
            )
            genre_ids = await self._resolve_ids(client, "genre", filters.genre_names)
            series_ids = await self._resolve_ids(
                client, "series", filters.series_names
            )
            items = []
            offset = 0
            total = 0
            while len(items) < limit:
                page_limit = min(100, limit - len(items))
                result = await client.call_tool(
                    "search_books",
                    {
                        "filters": {
                            "text": filters.text,
                            "author_ids": author_ids,
                            "genre_ids": genre_ids,
                            "series_ids": series_ids,
                            "is_read": filters.is_read,
                            "has_audio": filters.has_audio,
                            "authors_match": filters.authors_match,
                            "genres_match": filters.genres_match,
                            "limit": page_limit,
                            "offset": offset,
                        }
                    },
                )
                content = result.structured_content or {}
                page_items = content.get("items", [])
                items.extend(page_items)
                offset += len(page_items)
                total = content.get("total", offset)
                if not page_items or offset >= total:
                    break

        return CatalogSearchResult(
            items=[BookSearchItem.model_validate(item) for item in items],
            total=total,
        )

    @staticmethod
    async def _resolve_ids(client, entity: str, names: list[str]) -> list[int]:
        search_tool = {
            "author": "search_authors",
            "genre": "search_genres",
            "series": "search_series",
        }[entity]
        ids = []
        for name in names:
            result = await client.call_tool(
                search_tool,
                {"query": {"text": name, "limit": 20}},
            )
            content = result.structured_content or {}
            items = content.get("items", [])
            if not items:
                suggestion_result = await client.call_tool(
                    "suggest_items",
                    {
                        "query": {
                            "entity": entity,
                            "text": name,
                            "limit": 5,
                            "min_score": 50,
                        }
                    },
                )
                suggestions = (
                    suggestion_result.structured_content or {}
                ).get("suggestions", [])
                raise CatalogFilterAmbiguous(
                    entity=entity,
                    requested=name,
                    candidates=[item["name"] for item in suggestions],
                )
            exact = [
                item
                for item in items
                if normalize_text(item["name"]) == normalize_text(name)
            ]
            matches = exact or items
            if len(matches) != 1:
                raise CatalogFilterAmbiguous(
                    entity=entity,
                    requested=name,
                    candidates=[item["name"] for item in items[:5]],
                )
            ids.append(matches[0]["id"])
        return ids
