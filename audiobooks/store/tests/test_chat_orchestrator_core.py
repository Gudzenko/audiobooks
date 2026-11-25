from django.test import TestCase, override_settings

from ..chat.contracts import (
    CatalogSearchResult,
    ChatTextResult,
    WebSearchUnavailable,
)
from ..chat.schemas import (
    CatalogSearchFilters,
    ChatPlan,
    ChatRequest,
    WebExtractedItem,
    WebSearchItem,
    WebSearchResponse,
)
from .chat_orchestrator_helpers import ChatOrchestratorTestMixin


@override_settings(CHAT_CATALOG_RESULT_LIMIT=200)
class ChatOrchestratorCoreTests(ChatOrchestratorTestMixin, TestCase):
    def test_truncated_answer_preserves_sections_and_adds_warning(self):
        orchestrator, model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(action="catalog")
        )
        model.create_answer.return_value = ChatTextResult(
            "Partial answer",
            truncated=True,
        )

        response = orchestrator.reply(ChatRequest(message="Show local books"))

        self.assertEqual(response.kind, "partial")
        self.assertEqual(response.message, "Partial answer")
        self.assertEqual(len(response.sections), 1)
        self.assertTrue(response.warnings)

    def test_clarification_does_not_call_catalog_or_web_search(self):
        orchestrator, model, catalog, web_search = self.build_orchestrator(
            ChatPlan(action="clarification", clarification="Which books?")
        )
        request = ChatRequest(message="Find books")

        response = orchestrator.reply(request)

        self.assertEqual(response.kind, "clarification")
        model.create_plan.assert_called_once_with(request)
        catalog.search_books.assert_not_called()
        web_search.search.assert_not_called()

    def test_catalog_plan_does_not_call_web_search(self):
        orchestrator, _model, catalog, web_search = self.build_orchestrator(
            ChatPlan(action="catalog")
        )

        response = orchestrator.reply(ChatRequest(message="Show local books"))

        self.assertEqual(response.kind, "answer")
        catalog.search_books.assert_awaited_once_with(
            CatalogSearchFilters(),
            limit=200,
        )
        web_search.search.assert_not_called()

    def test_truncated_catalog_returns_partial_result_and_warning(self):
        orchestrator, _model, catalog, web_search = self.build_orchestrator(
            ChatPlan(action="catalog")
        )
        catalog.search_books.return_value = CatalogSearchResult(
            items=[],
            total=1200,
        )

        response = orchestrator.reply(ChatRequest(message="Show local books"))

        self.assertEqual(response.kind, "partial")
        self.assertEqual(len(response.warnings), 1)
        self.assertIn("1200", response.warnings[0])
        self.assertIn("author, series, genre", response.warnings[0])
        self.assertIn(response.warnings[0], response.history_content)
        web_search.search.assert_not_called()

    def test_web_plan_forwards_query_and_site_to_provider(self):
        orchestrator, _model, _catalog, web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                catalog_filters=CatalogSearchFilters(
                    author_names=["Isaac Asimov"],
                    has_audio=True,
                ),
                web_query="Find Foundation",
                web_objective="Find reliable book lists and extract titles.",
                site_url="https://example.com",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Foundation",
                        subtitle="External result",
                        url="https://example.com/foundation",
                    )
                ],
                extracted_items=[
                    WebExtractedItem(name="Foundation", alternative_names=[])
                ],
                coverage="complete",
            ),
        )

        response = orchestrator.reply(ChatRequest(message="Find Foundation"))

        self.assertEqual(response.kind, "answer")
        self.assertEqual(len(response.sections), 2)
        self.assertFalse(response.warnings)
        self.assertFalse(response.sections[1].items[0].links[0].is_demo)
        _catalog.search_books.assert_awaited_once_with(
            CatalogSearchFilters(
                author_names=["Isaac Asimov"],
                has_audio=True,
            ),
            limit=200,
        )
        web_search.search.assert_called_once_with(
            query="Find Foundation",
            objective="Find reliable book lists and extract titles.",
            site_url="https://example.com",
            mode="lookup",
        )

    def test_truncated_web_answer_preserves_local_and_external_sections(self):
        orchestrator, model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                web_query="Find Foundation",
                web_objective="Find reliable information about Foundation.",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Foundation",
                        url="https://example.com/foundation",
                    )
                ]
            ),
        )
        model.create_answer.return_value = ChatTextResult(
            "Partial web answer",
            truncated=True,
        )

        response = orchestrator.reply(ChatRequest(message="Find Foundation"))

        self.assertEqual(response.kind, "partial")
        self.assertEqual(response.message, "Partial web answer")
        self.assertEqual(len(response.sections), 2)
        self.assertTrue(response.warnings)

    def test_web_failure_preserves_local_result(self):
        orchestrator, _model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                web_query="Find Foundation",
                web_objective="Find reliable book lists and extract titles.",
            ),
            web_error=WebSearchUnavailable(),
        )

        response = orchestrator.reply(ChatRequest(message="Find Foundation"))

        self.assertEqual(response.kind, "partial")
        self.assertEqual(len(response.sections), 1)
        self.assertTrue(response.warnings)
