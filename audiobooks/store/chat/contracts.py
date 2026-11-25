from dataclasses import dataclass
from typing import Protocol

from store.mcp.schemas import BookSearchItem

from .modes import WebSearchMode
from .schemas import (
    CatalogSearchFilters,
    ChatAnswerContext,
    ChatPlan,
    ChatRequest,
    TitleMatchResult,
    WebListExtraction,
    WebSearchItem,
    WebSearchResponse,
)


class WebSearchUnavailable(Exception):
    pass


class ChatModelUnavailable(Exception):
    pass


class CatalogFilterAmbiguous(Exception):
    def __init__(self, *, entity: str, requested: str, candidates: list[str]):
        self.entity = entity
        self.requested = requested
        self.candidates = candidates
        super().__init__(f"Ambiguous {entity}: {requested}")


@dataclass(frozen=True)
class CatalogSearchResult:
    items: list[BookSearchItem]
    total: int

    @property
    def truncated(self) -> bool:
        return self.total > len(self.items)


@dataclass(frozen=True)
class ChatTextResult:
    text: str
    truncated: bool = False


class ChatModelProvider(Protocol):
    def create_plan(self, chat_request: ChatRequest) -> ChatPlan: ...

    def create_catalog_clarification(
        self,
        chat_request: ChatRequest,
        ambiguity: CatalogFilterAmbiguous,
    ) -> ChatTextResult: ...

    def create_answer(
        self,
        chat_request: ChatRequest,
        context: ChatAnswerContext,
    ) -> ChatTextResult: ...

    def extract_web_list(
        self,
        chat_request: ChatRequest,
        web_results: list[WebSearchItem],
        mode: WebSearchMode = "complete_list",
    ) -> WebListExtraction: ...

    def match_titles(
        self,
        external_names: list[str],
        local_titles: list[str],
    ) -> TitleMatchResult: ...


class CatalogProvider(Protocol):
    async def search_books(
        self,
        filters: CatalogSearchFilters,
        *,
        limit: int = 1000,
    ) -> CatalogSearchResult: ...


class WebSearchProvider(Protocol):
    is_demo: bool

    def search(
        self,
        *,
        query: str,
        objective: str,
        site_url: str | None = None,
        mode: WebSearchMode = "lookup",
    ) -> WebSearchResponse: ...
