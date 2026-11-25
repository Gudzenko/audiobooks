from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase

from ..chat.contracts import WebSearchUnavailable
from ..chat.exa_provider import ExaWebSearchProvider
from ..chat.schemas import WebSearchItem


class ExaProviderTests(TestCase):
    def test_site_inventory_at_result_limit_is_marked_incomplete(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title=f"Book {index}",
                    url=f"https://example.com/book-{index}",
                    highlights=[],
                )
                for index in range(2)
            ]
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=1,
            site_result_limit=2,
            client=client,
        )

        response = provider.search(
            query="site inventory",
            objective="Find every matching page.",
            mode="site_inventory",
        )

        self.assertTrue(response.full_content_unavailable)

    def test_exa_adapter_limits_search_to_requested_site(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title="Foundation",
                    url="https://books.example.com/foundation",
                    highlights=["A matching audiobook."],
                )
            ]
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        results = provider.search(
            query="Foundation audiobook",
            objective="Find audiobook pages and extract title and availability.",
            site_url="https://books.example.com/catalog",
        )

        self.assertEqual(results.results[0].title, "Foundation")
        self.assertEqual(results.results[0].subtitle, "A matching audiobook.")
        self.assertEqual(results.results[0].content, "A matching audiobook.")
        call = client.search.call_args
        self.assertEqual(call.args, ("Foundation audiobook",))
        self.assertEqual(
            call.kwargs["objective"],
            "Find audiobook pages and extract title and availability.",
        )
        self.assertEqual(call.kwargs["num_results"], 4)
        self.assertEqual(
            call.kwargs["include_domains"],
            ["books.example.com/catalog"],
        )
        self.assertEqual(call.kwargs["contents"], {"highlights": True})

    def test_exa_adapter_preserves_requested_site_path(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(results=[])
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        provider.search(
            query="Foundation audiobook",
            objective="Find audiobook pages.",
            site_url="https://books.example.com/catalog/audiobooks/",
        )

        self.assertEqual(
            client.search.call_args.kwargs["include_domains"],
            ["books.example.com/catalog/audiobooks"],
        )

    def test_exa_adapter_loads_full_pages_for_complete_list(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title="Complete bibliography",
                    url="https://example.com/bibliography",
                    highlights=["A short excerpt."],
                )
            ],
            output=SimpleNamespace(
                content={
                    "items": [],
                    "coverage": "partial",
                    "limitations": "Only excerpts were available.",
                }
            ),
        )
        client.get_contents.return_value = SimpleNamespace(
            statuses=[
                SimpleNamespace(
                    id="https://example.com/bibliography",
                    status="success",
                )
            ],
            results=[
                SimpleNamespace(
                    url="https://example.com/bibliography",
                    text="Complete page text with every title.",
                )
            ],
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        result = provider.search(
            query="Complete bibliography",
            objective="Extract every title.",
            mode="complete_list",
        )

        self.assertEqual(
            result.results[0].content,
            "Complete page text with every title.",
        )
        self.assertEqual(result.coverage, "not_applicable")
        self.assertEqual(result.limitations, "")
        client.get_contents.assert_called_once_with(
            ["https://example.com/bibliography"],
            text={"max_characters": 10000},
            timeout=60,
        )

    def test_exa_adapter_applies_configured_full_page_limit(self):
        client = Mock()
        client.get_contents.return_value = SimpleNamespace(
            statuses=[],
            results=[],
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            content_max_chars=25000,
            client=client,
        )

        provider._load_full_contents(
            [
                WebSearchItem(
                    title="Bibliography",
                    url="https://example.com/bibliography",
                )
            ]
        )

        client.get_contents.assert_called_once_with(
            ["https://example.com/bibliography"],
            text={"max_characters": 24000},
            timeout=60,
        )

    def test_exa_adapter_divides_total_content_limit_between_pages(self):
        client = Mock()
        client.get_contents.return_value = SimpleNamespace(
            statuses=[],
            results=[],
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            content_max_chars=20000,
            content_total_max_chars=30000,
            client=client,
        )

        provider._load_full_contents(
            [
                WebSearchItem(title="First", url="https://example.com/first"),
                WebSearchItem(title="Second", url="https://example.com/second"),
            ]
        )

        client.get_contents.assert_called_once_with(
            ["https://example.com/first", "https://example.com/second"],
            text={"max_characters": 15000},
            timeout=60,
        )

    def test_exa_adapter_enforces_total_content_limit_on_all_results(self):
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            content_total_max_chars=10000,
            client=Mock(),
        )
        items = [
            WebSearchItem(
                title="First",
                content="a" * 8000,
                url="https://example.com/first",
            ),
            WebSearchItem(
                title="Second",
                content="b" * 8000,
                url="https://example.com/second",
            ),
        ]

        results, incomplete = provider._limit_result_contents(items)

        self.assertEqual(sum(len(item.content) for item in results), 10000)
        self.assertTrue(incomplete)

    def test_exa_adapter_limits_site_inventory_excerpts(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title="First",
                    url="https://example.com/first",
                    highlights=["a" * 8000],
                ),
                SimpleNamespace(
                    title="Second",
                    url="https://example.com/second",
                    highlights=["b" * 8000],
                ),
            ]
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            content_total_max_chars=10000,
            client=client,
        )

        response = provider.search(
            query="site inventory",
            objective="Find matching pages.",
            mode="site_inventory",
        )

        self.assertEqual(
            sum(len(item.content) for item in response.results),
            10000,
        )
        self.assertTrue(response.full_content_unavailable)

    def test_exa_adapter_marks_page_at_character_limit_as_incomplete(self):
        client = Mock()
        client.get_contents.return_value = SimpleNamespace(
            statuses=[],
            results=[
                SimpleNamespace(
                    url="https://example.com/bibliography",
                    text="a" * 5000,
                )
            ],
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            content_max_chars=5000,
            client=client,
        )

        _, incomplete = provider._load_full_contents(
            [
                WebSearchItem(
                    title="Bibliography",
                    url="https://example.com/bibliography",
                )
            ]
        )

        self.assertTrue(incomplete)

    def test_exa_adapter_marks_partial_content_failures(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title="First page",
                    url="https://example.com/first",
                    highlights=["First excerpt."],
                ),
                SimpleNamespace(
                    title="Second page",
                    url="https://example.com/second",
                    highlights=["Second excerpt."],
                ),
            ]
        )
        client.get_contents.return_value = SimpleNamespace(
            statuses=[
                SimpleNamespace(
                    id="https://example.com/first",
                    status="success",
                ),
                SimpleNamespace(
                    id="https://example.com/second",
                    status="error",
                ),
            ],
            results=[
                SimpleNamespace(
                    url="https://example.com/first",
                    text="Full first page.",
                )
            ],
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        result = provider.search(
            query="Complete bibliography",
            objective="Extract every title.",
            mode="complete_list",
        )

        self.assertTrue(result.full_content_unavailable)
        self.assertEqual(result.results[0].content, "Full first page.")
        self.assertEqual(result.results[1].content, "Second excerpt.")

    def test_exa_adapter_keeps_search_results_when_full_pages_fail(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(
                    title="Complete bibliography",
                    url="https://example.com/bibliography",
                    highlights=["Robbie, Foundation, Nightfall."],
                )
            ]
        )
        client.get_contents.side_effect = RuntimeError("contents unavailable")
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        result = provider.search(
            query="Complete bibliography",
            objective="Extract every title.",
            mode="complete_list",
        )

        self.assertTrue(result.full_content_unavailable)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(
            result.results[0].content,
            "Robbie, Foundation, Nightfall.",
        )

    def test_exa_adapter_converts_sdk_errors(self):
        client = Mock()
        client.search.side_effect = RuntimeError("provider details")
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        with self.assertRaises(WebSearchUnavailable):
            provider.search(
                query="Foundation",
                objective="Find reliable pages about the audiobook.",
            )

    def test_exa_adapter_does_not_mask_result_mapping_errors(self):
        client = Mock()
        client.search.return_value = SimpleNamespace(
            results=[SimpleNamespace(title="Broken result")]
        )
        provider = ExaWebSearchProvider(
            api_key="test-key",
            timeout=3,
            result_limit=4,
            client=client,
        )

        with self.assertRaises(AttributeError):
            provider.search(
                query="Foundation",
                objective="Find reliable pages about the audiobook.",
            )
