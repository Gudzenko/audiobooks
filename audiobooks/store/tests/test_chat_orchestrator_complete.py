from types import SimpleNamespace

from django.test import TestCase

from ..chat.catalog_comparison import compare_external_list
from ..chat.contracts import CatalogSearchResult
from ..chat.schemas import (
    ChatPlan,
    ChatRequest,
    TitleMatch,
    TitleMatchResult,
    WebExtractedItem,
    WebListExtraction,
    WebSearchItem,
    WebSearchResponse,
)
from .chat_orchestrator_helpers import ChatOrchestratorTestMixin


class ChatCompleteListTests(ChatOrchestratorTestMixin, TestCase):
    def test_complete_list_is_formatted_without_model_descriptions(self):
        author = SimpleNamespace(name="Isaac Asimov")
        local_book = SimpleNamespace(
            title="Foundation",
            slug="foundation",
            authors=[author],
        )
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                web_mode="complete_list",
                web_query="Isaac Asimov stories",
                web_objective="Extract every story title.",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Bibliography",
                        subtitle="Long technical search excerpt.",
                        url="https://example.com/bibliography",
                    )
                ]
            ),
        )
        catalog.search_books.return_value = CatalogSearchResult(
            items=[local_book],
            total=1,
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(name="Foundation"),
                WebExtractedItem(name="Robbie"),
            ],
            coverage="complete",
        )

        response = orchestrator.reply(
            ChatRequest(message="Что есть и чего нет? Только перечень.")
        )

        self.assertEqual(response.kind, "answer")
        self.assertIn("- **Foundation**", response.message)
        self.assertIn("- **Robbie**", response.message)
        self.assertNotIn("сюжет", response.message.casefold())
        self.assertEqual(response.sections[1].items[0].subtitle, "")
        model.create_answer.assert_not_called()
        model.match_titles.assert_not_called()

    def test_complete_list_warns_when_only_search_excerpts_are_available(self):
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="complete_list",
                web_query="Isaac Asimov bibliography",
                web_objective="Extract every title.",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Bibliography",
                        content="Robbie, Foundation, Nightfall.",
                        url="https://example.com/bibliography",
                    )
                ],
                full_content_unavailable=True,
            ),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[WebExtractedItem(name="Robbie")],
            coverage="complete",
        )

        response = orchestrator.reply(ChatRequest(message="Покажи весь список"))

        self.assertEqual(response.kind, "partial")
        self.assertIn("- **Robbie**", response.message)
        self.assertEqual(len(response.sections[0].items), 1)
        self.assertIn("unavailable or limited", response.warnings[0])
        self.assertIn(response.warnings[0], response.history_content)
        catalog.search_books.assert_not_called()

    def test_complete_list_matches_translated_titles(self):
        author = SimpleNamespace(name="Stanislaw Lem")
        local_book = SimpleNamespace(
            title="Solaris",
            slug="solaris",
            authors=[author],
        )
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                web_mode="complete_list",
                web_query="Stanislaw Lem bibliography",
                web_objective="Extract every title.",
            )
        )
        catalog.search_books.return_value = CatalogSearchResult(
            items=[local_book],
            total=1,
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[WebExtractedItem(name="Солярис")],
            coverage="complete",
        )
        model.match_titles.return_value = TitleMatchResult(
            matches=[
                TitleMatch(external_name="Солярис", local_title="Solaris")
            ]
        )

        response = orchestrator.reply(ChatRequest(message="Сравни список"))

        self.assertIn("- **Солярис**", response.message)
        self.assertNotIn("Not found as separate catalog entries\n\n-", response.message)
        model.match_titles.assert_called_once_with(["Солярис"], ["Solaris"])

    def test_web_only_complete_list_does_not_compare_with_catalog(self):
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="complete_list",
                web_query="Stanislaw Lem bibliography",
                web_objective="Extract every title.",
            )
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(name="Solaris"),
                WebExtractedItem(name="The Cyberiad"),
            ],
            coverage="complete",
        )

        response = orchestrator.reply(
            ChatRequest(message="Перечисли произведения Лема")
        )

        catalog.search_books.assert_not_called()
        model.match_titles.assert_not_called()
        self.assertIn("Found in external sources", response.message)
        self.assertIn("- **Solaris**", response.message)
        self.assertNotIn("catalog", response.message.casefold())

    def test_oversized_external_list_is_returned_as_partial_with_warning(self):
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="complete_list",
                web_query="Complete bibliography",
                web_objective="Extract every title.",
            )
        )
        model.extract_web_list.return_value = WebListExtraction.model_validate(
            {
                "items": [
                    {"name": f"Book {index:03d}"}
                    for index in range(101)
                ],
                "coverage": "complete",
            }
        )

        response = orchestrator.reply(ChatRequest(message="Покажи полный список"))

        self.assertEqual(response.kind, "partial")
        self.assertEqual(response.message.count("\n- **Book"), 100)
        self.assertEqual(len(response.warnings), 1)
        self.assertIn("first 100", response.warnings[0])
        self.assertIn(response.warnings[0], response.history_content)
        catalog.search_books.assert_not_called()

    def test_complete_comparison_does_not_match_two_items_to_one_book(self):
        comparison = compare_external_list(
            [
                WebExtractedItem(
                    name="Солярис",
                    alternative_names=["Solaris"],
                ),
                WebExtractedItem(name="Solaris"),
            ],
            [SimpleNamespace(title="Solaris")],
        )

        self.assertEqual(comparison.matched, ["Солярис"])
        self.assertEqual(comparison.missing, ["Solaris"])
