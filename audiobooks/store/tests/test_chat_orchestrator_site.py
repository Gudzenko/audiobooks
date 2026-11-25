from types import SimpleNamespace

from django.test import TestCase
from django.utils import translation

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


class ChatSiteInventoryTests(ChatOrchestratorTestMixin, TestCase):
    def test_site_inventory_warns_when_source_content_is_limited(self):
        orchestrator, model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="site_inventory",
                web_query="Site inventory",
                web_objective="Find matching pages.",
                site_url="https://example.com/",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Book",
                        url="https://example.com/book",
                    )
                ],
                full_content_unavailable=True,
            ),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(
                    name="Book",
                    source_url="https://example.com/book",
                )
            ],
            coverage="complete",
        )

        response = orchestrator.reply(ChatRequest(message="Что есть на сайте?"))

        self.assertEqual(response.kind, "partial")
        self.assertIn("unavailable or limited", response.warnings[0])

    def test_site_inventory_omits_items_without_verified_source(self):
        orchestrator, model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="site_inventory",
                web_query="Site inventory",
                web_objective="Find matching pages.",
                site_url="https://example.com/",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Verified item",
                        url="https://example.com/verified",
                    )
                ]
            ),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(
                    name="Verified item",
                    source_url="https://example.com/verified",
                ),
                WebExtractedItem(
                    name="Invented item",
                    source_url="https://example.com/invented",
                ),
            ],
            coverage="complete",
        )

        response = orchestrator.reply(ChatRequest(message="Что есть на сайте?"))

        self.assertEqual(response.kind, "partial")
        self.assertIn("Verified item", response.message)
        self.assertNotIn("Invented item", response.message)
        self.assertEqual(
            [item.title for item in response.sections[0].items],
            ["Verified item"],
        )
        self.assertTrue(response.warnings)

    def test_site_inventory_skips_local_catalog_and_lists_site_pages_only(self):
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="site_inventory",
                web_query="site:audioboo.org Isaac Asimov audiobooks",
                web_objective="Find pages for audiobooks by Isaac Asimov.",
                site_url="https://audioboo.org/",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Азимов Айзек - Сами боги",
                        subtitle="Technical page description",
                        url="https://audioboo.org/book",
                    )
                ]
            ),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(
                    name="Сами боги",
                    source_url="https://audioboo.org/book",
                )
            ],
            coverage="partial",
            limitations="Сайт может содержать другие страницы.",
        )

        with translation.override("ru"):
            response = orchestrator.reply(
                ChatRequest(message="Что есть на audioboo.org из Азимова?")
            )

        catalog.search_books.assert_not_called()
        model.extract_web_list.assert_called_once_with(
            ChatRequest(message="Что есть на audioboo.org из Азимова?"),
            _web_search.search.return_value.results,
            mode="site_inventory",
        )
        self.assertNotIn("локаль", response.message.casefold())
        self.assertIn("- **Сами боги**", response.message)
        self.assertEqual(len(response.sections), 1)
        self.assertEqual(response.sections[0].items[0].subtitle, "")
        self.assertEqual(response.sections[0].items[0].title, "Сами боги")
        self.assertEqual(
            response.sections[0].items[0].links[0].label,
            "Открыть источник",
        )

    def test_site_inventory_preserves_link_when_source_url_format_differs(self):
        orchestrator, model, _catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="web",
                web_mode="site_inventory",
                web_query="Stanislaw Lem on example.com",
                web_objective="Find audiobook pages by Stanislaw Lem.",
                site_url="https://example.com/",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Solaris",
                        url="https://EXAMPLE.com/book/123/?source=search",
                    )
                ]
            ),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(
                    name="Solaris",
                    source_url="https://example.com/book/123",
                )
            ],
            coverage="complete",
        )

        response = orchestrator.reply(ChatRequest(message="Что есть на сайте?"))

        self.assertEqual(len(response.sections[0].items), 1)
        self.assertEqual(
            response.sections[0].items[0].links[0].url,
            "https://example.com/book/123/?source=search",
        )

    def test_site_inventory_comparison_matches_translated_titles(self):
        author = SimpleNamespace(name="Stanislaw Lem")
        local_books = [
            SimpleNamespace(title="Solaris", slug="solaris", authors=[author]),
            SimpleNamespace(
                title="The Cyberiad",
                slug="the-cyberiad",
                authors=[author],
            ),
        ]
        orchestrator, model, catalog, _web_search = self.build_orchestrator(
            ChatPlan(
                action="catalog_and_web",
                web_mode="site_inventory",
                web_query="Stanislaw Lem audiobooks",
                web_objective="Find audiobook pages authored by Stanislaw Lem.",
                site_url="https://audioboo.org/",
            ),
            web_result=WebSearchResponse(
                results=[
                    WebSearchItem(
                        title="Лем Станислав - Солярис",
                        url="https://audioboo.org/solaris",
                    ),
                    WebSearchItem(
                        title="Лем Станислав - Непобедимый",
                        url="https://audioboo.org/invincible",
                    ),
                ]
            ),
        )
        catalog.search_books.return_value = CatalogSearchResult(
            items=local_books,
            total=len(local_books),
        )
        model.extract_web_list.return_value = WebListExtraction(
            items=[
                WebExtractedItem(
                    name="Солярис",
                    source_url="https://audioboo.org/solaris",
                ),
                WebExtractedItem(
                    name="Непобедимый",
                    source_url="https://audioboo.org/invincible",
                ),
            ],
            coverage="partial",
            limitations="Возможно, найдены не все страницы.",
        )
        model.match_titles.return_value = TitleMatchResult(
            matches=[
                TitleMatch(external_name="Солярис", local_title="Solaris")
            ]
        )

        with translation.override("ru"):
            response = orchestrator.reply(
                ChatRequest(
                    message=(
                        "Что есть на audioboo.org из Stanislaw Lem и сравни "
                        "с библиотекой?"
                    )
                )
            )

        self.assertIn("**Солярис** — в библиотеке: **Solaris**", response.message)
        self.assertIn("- **Непобедимый**", response.message)
        self.assertIn("- **The Cyberiad**", response.message)
        self.assertNotIn("Сравнение не выполнялось", response.message)
