import re

from .contracts import (
    CatalogFilterAmbiguous,
    ChatTextResult,
    WebSearchUnavailable,
)
from .modes import WebSearchMode
from .schemas import (
    ChatAnswerContext,
    ChatPlan,
    ChatRequest,
    TitleMatchResult,
    WebListExtraction,
    WebSearchItem,
    WebSearchResponse,
)


URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class MockChatModelProvider:
    def create_plan(self, chat_request: ChatRequest) -> ChatPlan:
        message = chat_request.message.strip()
        normalized = message.casefold()

        if any(
            marker in normalized
            for marker in ("уточни", "clarify", "doprecyzuj")
        ):
            return ChatPlan(
                action="clarification",
                clarification=(
                    "What should I show: all matching items, only missing items, "
                    "or a comparison with the local catalog?"
                ),
            )

        url_match = URL_PATTERN.search(message)
        requests_failed_web = any(
            marker in normalized
            for marker in (
                "внешний сервис недоступен",
                "web unavailable",
                "brak internetu",
            )
        )
        if url_match or requests_failed_web:
            return ChatPlan(
                action="catalog_and_web",
                web_query=message,
                web_objective=(
                    "Find pages relevant to the user's audiobook question and "
                    "extract book titles, alternative titles, authors and source links."
                ),
                site_url=url_match.group(0).rstrip(".,;)") if url_match else None,
            )

        return ChatPlan(action="catalog")

    def create_catalog_clarification(
        self,
        chat_request: ChatRequest,
        ambiguity: CatalogFilterAmbiguous,
    ) -> ChatTextResult:
        candidates = ", ".join(ambiguity.candidates) or "no similar items"
        return ChatTextResult(
            text=(
                f"I found similar {ambiguity.entity} entries: {candidates}. "
                "Which one did you mean?"
            )
        )

    def create_answer(
        self,
        chat_request: ChatRequest,
        context: ChatAnswerContext,
    ) -> ChatTextResult:
        if context.web_search_unavailable:
            return ChatTextResult(
                text="The local catalog was checked, but web search is unavailable."
            )
        return ChatTextResult(
            text=(
                "The mock assistant received the message and checked the "
                "local catalog."
            )
        )

    def extract_web_list(
        self,
        chat_request: ChatRequest,
        web_results: list[WebSearchItem],
        mode: WebSearchMode = "complete_list",
    ) -> WebListExtraction:
        return WebListExtraction(
            items=[],
            coverage="partial",
            limitations="Demonstration provider has no extracted list.",
        )

    def match_titles(
        self,
        external_names: list[str],
        local_titles: list[str],
    ) -> TitleMatchResult:
        return TitleMatchResult()


class MockWebSearchProvider:
    is_demo = True

    def search(
        self,
        *,
        query: str,
        objective: str,
        site_url: str | None = None,
        mode: WebSearchMode = "lookup",
    ) -> WebSearchResponse:
        normalized = query.casefold()
        if any(
            marker in normalized
            for marker in (
                "внешний сервис недоступен",
                "web unavailable",
                "brak internetu",
            )
        ):
            raise WebSearchUnavailable

        return WebSearchResponse(
            results=[
                WebSearchItem(
                    title="Demonstration external result",
                    subtitle="Example data returned by the mock search provider.",
                    url=site_url or "https://example.com/",
                )
            ]
        )
