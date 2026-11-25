from types import SimpleNamespace

from django.test import TestCase
from pydantic import ValidationError

from ..chat.catalog_comparison import compare_external_list, compare_site_inventory
from ..chat.schemas import (
    ChatHistoryItem,
    ChatLink,
    ChatPlan,
    ChatRequest,
    ChatResponse,
    ChatResultItem,
    ChatSection,
    TitleMatch,
    WebExtractedItem,
)


class ChatSchemaAndComparisonTests(TestCase):
    def test_response_history_contains_structured_result_titles(self):
        response = ChatResponse(
            kind="answer",
            message="Found books.",
            sections=[
                ChatSection(
                    title="Local catalog",
                    items=[
                        ChatResultItem(
                            title="Solaris",
                            subtitle="Stanislaw Lem",
                        )
                    ],
                )
            ],
        )

        self.assertIn("Found books.", response.history_content)
        self.assertIn("Local catalog", response.history_content)
        self.assertIn("Solaris — Stanislaw Lem", response.history_content)

    def test_request_rejects_excessive_total_history_size(self):
        with self.assertRaises(ValidationError):
            ChatRequest(
                message="Continue",
                history=[
                    ChatHistoryItem(role="assistant", content="x" * 5000)
                    for _ in range(5)
                ],
            )

    def test_chat_link_rejects_unsafe_scheme(self):
        with self.assertRaises(ValidationError):
            ChatLink(label="Unsafe", url="javascript:alert(1)")

    def test_external_item_limits_alternative_names(self):
        with self.assertRaises(ValidationError):
            WebExtractedItem(
                name="Book",
                alternative_names=[f"Alias {index}" for index in range(6)],
            )

    def test_site_url_rejects_local_addresses_and_credentials(self):
        for site_url in (
            "http://localhost/catalog",
            "http://127.0.0.1/catalog",
            "http://user:password@example.com/catalog",
        ):
            with self.subTest(site_url=site_url):
                with self.assertRaises(ValidationError):
                    ChatPlan(
                        action="web",
                        web_query="Find books",
                        web_objective="Find audiobook pages.",
                        site_url=site_url,
                    )

    def test_comparison_deduplicates_items_and_uses_alternative_names(self):
        local_books = [SimpleNamespace(title="Solaris")]
        external_items = [
            WebExtractedItem(
                name="Солярис",
                alternative_names=["Solaris"],
            ),
            WebExtractedItem(name="Солярис"),
        ]

        comparison = compare_external_list(external_items, local_books)

        self.assertEqual(comparison.matched, ["Солярис"])
        self.assertEqual(comparison.missing, [])
        self.assertEqual(comparison.unmatched_local, [])

    def test_site_comparison_validates_model_matches_and_keeps_one_to_one(self):
        local_books = [
            SimpleNamespace(title="Solaris"),
            SimpleNamespace(title="The Cyberiad"),
        ]
        external_items = [
            WebExtractedItem(name="Солярис"),
            WebExtractedItem(name="Кибериада"),
        ]
        matches = [
            TitleMatch(external_name="Солярис", local_title="Solaris"),
            TitleMatch(external_name="Кибериада", local_title="Solaris"),
            TitleMatch(external_name="Unknown", local_title="The Cyberiad"),
        ]

        comparison = compare_site_inventory(
            external_items,
            local_books,
            matches,
        )

        self.assertEqual(comparison.matched, [("Солярис", "Solaris")])
        self.assertEqual(comparison.site_only, ["Кибериада"])
        self.assertEqual(comparison.local_only, ["The Cyberiad"])
