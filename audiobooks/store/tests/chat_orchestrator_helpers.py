from unittest.mock import AsyncMock, Mock

from ..chat.contracts import CatalogSearchResult, ChatTextResult
from ..chat.schemas import (
    ChatPlan,
    TitleMatchResult,
    WebListExtraction,
    WebSearchResponse,
)
from ..chat.services import ChatOrchestrator


class ChatOrchestratorTestMixin:
    def build_orchestrator(self, plan, *, web_result=None, web_error=None):
        model = Mock()
        model.create_plan.return_value = plan
        model.create_answer.return_value = ChatTextResult("Generated answer")
        model.create_catalog_clarification.return_value = ChatTextResult(
            "Which author?"
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[],
            coverage="partial",
            limitations="No complete list.",
        )
        model.match_titles.return_value = TitleMatchResult()
        catalog = Mock()
        catalog.search_books = AsyncMock(
            return_value=CatalogSearchResult(items=[], total=0)
        )
        web_search = Mock()
        web_search.is_demo = False
        if web_error:
            web_search.search.side_effect = web_error
        else:
            web_search.search.return_value = web_result or WebSearchResponse()
        orchestrator = ChatOrchestrator(
            model=model,
            catalog=catalog,
            web_search=web_search,
        )
        return orchestrator, model, catalog, web_search
