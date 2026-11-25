import json
import tempfile
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from ..chat.catalog_provider import LocalCatalogProvider
from ..chat.contracts import CatalogFilterAmbiguous
from ..chat.schemas import CatalogSearchFilters
from ..models import Author, Book, Genre, Series


@override_settings(
    CHAT_MODEL_PROVIDER="mock",
    WEB_SEARCH_PROVIDER="mock",
    CHAT_REQUESTS_PER_MINUTE=100,
)
class ChatMessageTests(TransactionTestCase):
    def setUp(self):
        self.rate_limit_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.rate_limit_directory.cleanup)
        self.rate_limit_settings = override_settings(
            CHAT_RATE_LIMIT_DIR=self.rate_limit_directory.name
        )
        self.rate_limit_settings.enable()
        self.addCleanup(self.rate_limit_settings.disable)
        self.user = get_user_model().objects.create_user(
            email="assistant@example.com",
            username="assistant-user",
            password="test-password",
        )
        self.author = Author.objects.create(first_name="Isaac", last_name="Asimov")
        self.book = Book.objects.create(title="Foundation")
        self.book.authors.add(self.author)
        self.client.force_login(self.user)

    def post_message(self, message, history=None, client=None):
        return (client or self.client).post(
            reverse("chat_message"),
            data=json.dumps({"message": message, "history": history or []}),
            content_type="application/json",
        )

    def test_message_endpoint_requires_login(self):
        self.client.logout()

        response = self.post_message("Show my books")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Authentication required.")

    def test_message_endpoint_requires_json(self):
        response = self.client.post(reverse("chat_message"), {"message": "Hello"})

        self.assertEqual(response.status_code, 415)

    def test_invalid_json_and_invalid_schema_are_rejected(self):
        invalid_json = self.client.post(
            reverse("chat_message"),
            data="{",
            content_type="application/json",
        )
        extra_field = self.client.post(
            reverse("chat_message"),
            data=json.dumps({"message": "Hello", "unexpected": True}),
            content_type="application/json",
        )

        self.assertEqual(invalid_json.status_code, 400)
        self.assertEqual(extra_field.status_code, 400)
        self.assertNotIn("details", invalid_json.json())

    def test_message_and_history_limits_are_enforced(self):
        long_message = self.post_message("x" * 4001)
        long_history = self.post_message(
            "Hello",
            [{"role": "user", "content": "x"}] * 21,
        )

        self.assertEqual(long_message.status_code, 400)
        self.assertEqual(long_history.status_code, 400)

    def test_long_research_answer_can_be_sent_in_history(self):
        response = self.post_message(
            "Продолжи",
            history=[
                {
                    "role": "assistant",
                    "content": "Название\n" * 500,
                }
            ],
        )

        self.assertEqual(response.status_code, 200)

    def test_local_catalog_is_read_through_mcp(self):
        response = self.post_message("Show my books")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["kind"], "answer")
        self.assertIn("<p>", payload["message_html"])
        self.assertEqual(payload["sections"][0]["title"], "Local catalog")
        self.assertEqual(payload["sections"][0]["items"][0]["title"], "Foundation")
        self.assertEqual(
            payload["sections"][0]["items"][0]["links"][0]["url"],
            reverse("book_detail", kwargs={"slug": self.book.slug}),
        )

    def test_catalog_provider_reads_more_than_one_mcp_page(self):
        for index in range(105):
            Book.objects.create(title=f"Pagination book {index:03d}")

        provider = LocalCatalogProvider()
        result = async_to_sync(provider.search_books)(
            CatalogSearchFilters(),
            limit=105,
        )

        self.assertEqual(len(result.items), 105)
        self.assertEqual(result.items[0].title, "Foundation")
        self.assertEqual(result.items[-1].title, "Pagination book 103")
        self.assertEqual(result.total, 106)
        self.assertTrue(result.truncated)

    def test_catalog_provider_resolves_author_name_before_searching_books(self):
        other_author = Author.objects.create(
            first_name="Arthur",
            last_name="Clarke",
        )
        other_book = Book.objects.create(title="Childhood's End")
        other_book.authors.add(other_author)

        result = async_to_sync(LocalCatalogProvider().search_books)(
            CatalogSearchFilters(author_names=["Isaac Asimov"]),
            limit=100,
        )

        self.assertEqual(
            [book.title for book in result.items],
            ["Foundation"],
        )

    def test_catalog_provider_combines_multiple_named_filters(self):
        genre = Genre.objects.create(name="Science Fiction")
        series = Series.objects.create(title="Foundation Series")
        self.book.genres.add(genre)
        self.book.series = series
        self.book.is_read = True
        self.book.save()

        result = async_to_sync(LocalCatalogProvider().search_books)(
            CatalogSearchFilters(
                author_names=["Isaac Asimov"],
                genre_names=["Science Fiction"],
                series_names=["Foundation Series"],
                is_read=True,
            ),
            limit=100,
        )

        self.assertEqual(
            [book.title for book in result.items],
            ["Foundation"],
        )

    def test_catalog_provider_rejects_ambiguous_author_name(self):
        second_author = Author.objects.create(
            first_name="Isaac",
            last_name="Newton",
        )
        second_book = Book.objects.create(title="Principia")
        second_book.authors.add(second_author)

        with self.assertRaises(CatalogFilterAmbiguous):
            async_to_sync(LocalCatalogProvider().search_books)(
                CatalogSearchFilters(author_names=["Isaac"]),
                limit=100,
            )

    def test_catalog_provider_suggests_match_instead_of_guessing(self):
        with self.assertRaises(CatalogFilterAmbiguous) as raised:
            async_to_sync(LocalCatalogProvider().search_books)(
                CatalogSearchFilters(author_names=["Айзека Азимова"]),
                limit=100,
            )

        self.assertEqual(raised.exception.candidates, ["Isaac Asimov"])

    def test_url_adds_marked_demonstration_result(self):
        response = self.post_message("Check https://example.com")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["sections"]), 2)
        external_link = payload["sections"][1]["items"][0]["links"][0]
        self.assertTrue(external_link["is_demo"])
        self.assertTrue(payload["warnings"])

    def test_mock_can_request_clarification(self):
        response = self.post_message("Уточни мой запрос")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "clarification")

    def test_mock_reports_partial_result_when_web_is_unavailable(self):
        response = self.post_message("Web unavailable")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["kind"], "partial")
        self.assertTrue(payload["sections"])
        self.assertTrue(payload["warnings"])

    @override_settings(CHAT_REQUESTS_PER_MINUTE=1)
    def test_rate_limit_is_reported_to_the_user(self):
        first = self.post_message("Show my books")
        second = self.post_message("Show my books again")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["kind"], "error")

    @patch(
        "store.chat.catalog_provider.LocalCatalogProvider.search_books",
        new_callable=AsyncMock,
        side_effect=RuntimeError("catalog unavailable"),
    )
    def test_local_catalog_failure_is_reported_without_internal_details(self, _search):
        response = self.post_message("Show my books")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["kind"], "error")
        self.assertNotContains(response, "catalog unavailable", status_code=503)

    def test_csrf_is_required(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
