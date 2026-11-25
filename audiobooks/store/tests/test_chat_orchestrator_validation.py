from django.test import TestCase
from pydantic import ValidationError

from ..chat.contracts import CatalogFilterAmbiguous
from ..chat.schemas import (
    CatalogSearchFilters,
    ChatLink,
    ChatPlan,
    ChatRequest,
    ChatResponse,
    WebSearchItem,
)
from .chat_orchestrator_helpers import ChatOrchestratorTestMixin


class ChatOrchestratorValidationTests(ChatOrchestratorTestMixin, TestCase):
    def test_ambiguous_catalog_filter_asks_model_for_clarification(self):
        orchestrator, model, catalog, web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                catalog_filters=CatalogSearchFilters(
                    author_names=["Айзек Азимов"]
                ),
                web_query="Isaac Asimov bibliography",
                web_objective="Find reliable bibliographies.",
            )
        )
        ambiguity = CatalogFilterAmbiguous(
            entity="author",
            requested="Айзек Азимов",
            candidates=["Isaac Asimov", "Isaac Azimoff"],
        )
        catalog.search_books.side_effect = ambiguity
        request = ChatRequest(message="Какие книги написал Айзек Азимов?")

        response = orchestrator.reply(request)

        self.assertEqual(response.kind, "clarification")
        self.assertEqual(response.message, "Which author?")
        model.create_catalog_clarification.assert_called_once_with(
            request,
            ambiguity,
        )
        web_search.search.assert_not_called()

    def test_web_result_rejects_non_http_links(self):
        with self.assertRaises(ValidationError):
            WebSearchItem(
                title="Unsafe result",
                url="javascript:alert(1)",
            )

    def test_chat_link_rejects_protocol_relative_url(self):
        with self.assertRaises(ValidationError):
            ChatLink(label="Unsafe", url="//example.com/book")

    def test_long_response_warns_that_follow_up_context_is_truncated(self):
        response = ChatResponse(kind="answer", message="x" * 6001)

        self.assertEqual(len(response.history_content), 6000)
        self.assertEqual(len(response.warnings), 1)
        self.assertIn("too long", response.warnings[0])
        self.assertTrue(response.history_content.startswith("Warning:"))
        self.assertIn(response.warnings[0], response.history_content)

    def test_chat_plan_rejects_invalid_site_and_missing_action_data(self):
        with self.assertRaises(ValidationError):
            ChatPlan(
                action="catalog_and_web",
                web_query="Find books",
                web_objective="Find reliable book lists and extract titles.",
                site_url="javascript:alert(1)",
            )
        with self.assertRaises(ValidationError):
            ChatPlan(action="catalog_and_web")
        with self.assertRaises(ValidationError):
            ChatPlan(action="catalog_and_web", web_query="Find books")
        with self.assertRaises(ValidationError):
            ChatPlan(action="clarification")
