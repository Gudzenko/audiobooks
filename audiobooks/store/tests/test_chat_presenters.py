from django.test import TestCase

from ..chat.formatting import make_source_excerpt, render_chat_markdown
from ..chat.prompts import (
    ANSWER_PROMPT,
    SITE_INVENTORY_EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
    get_list_extraction_prompt,
)
from ..chat.response_sections import build_site_inventory_section
from ..chat.schemas import WebExtractedItem, WebSearchItem


class ChatPromptAndFormattingTests(TestCase):
    def test_planner_decides_when_web_is_required_without_permission_prompt(self):
        self.assertIn("never use it to ask\npermission for web search", SYSTEM_PROMPT)

    def test_answer_prompt_does_not_expand_title_lists_into_descriptions(self):
        self.assertIn("Match the requested level of detail exactly", ANSWER_PROMPT)
        self.assertIn("Do not add plots, descriptions", ANSWER_PROMPT)

    def test_site_inventory_prompt_is_not_limited_to_authors_or_books(self):
        self.assertIn(
            "Do not assume that the\ncriteria concern an author",
            SITE_INVENTORY_EXTRACTION_PROMPT,
        )
        self.assertIn(
            "Include collections,\nanthologies, series",
            SITE_INVENTORY_EXTRACTION_PROMPT,
        )
        self.assertIn(
            SITE_INVENTORY_EXTRACTION_PROMPT,
            get_list_extraction_prompt("site_inventory"),
        )

    def test_chat_markdown_is_rendered_and_sanitized(self):
        rendered = render_chat_markdown(
            "**Автор** • Первая книга • Вторая книга "
            "<script>alert(1)</script> "
            "[опасная ссылка](javascript:alert(1))"
        )

        self.assertIn("<strong>Автор</strong>", rendered)
        self.assertIn("<ul>", rendered)
        self.assertEqual(rendered.count("<li>"), 2)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("javascript:", rendered)

    def test_source_excerpt_removes_markdown_table_and_heading(self):
        excerpt = make_source_excerpt(
            "## Published stories Intro text. | Story | Year | "
            "| --- | --- | | Robbie | 1940 |"
        )

        self.assertEqual(excerpt, "Published stories Intro text.")
        self.assertNotIn("##", excerpt)
        self.assertNotIn("|", excerpt)

    def test_source_links_keep_distinct_query_parameters(self):
        results = [
            WebSearchItem(
                title="First book",
                url="https://example.com/book?id=10",
            ),
            WebSearchItem(
                title="Second book",
                url="https://example.com/book?id=20",
            ),
        ]

        section = build_site_inventory_section(
            [
                WebExtractedItem(
                    name="Second book",
                    source_url="https://example.com/book?id=20#description",
                )
            ],
            results,
            is_demo=False,
        )

        self.assertEqual(len(section.items), 1)
        self.assertEqual(
            section.items[0].links[0].url,
            "https://example.com/book?id=20",
        )

    def test_source_link_without_query_is_not_guessed_when_ambiguous(self):
        section = build_site_inventory_section(
            [
                WebExtractedItem(
                    name="Unknown book",
                    source_url="https://example.com/book",
                )
            ],
            [
                WebSearchItem(
                    title="First book",
                    url="https://example.com/book?id=10",
                ),
                WebSearchItem(
                    title="Second book",
                    url="https://example.com/book?id=20",
                ),
            ],
            is_demo=False,
        )

        self.assertEqual(section.items, [])
