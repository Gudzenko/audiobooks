from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase

from ..chat.contracts import (
    CatalogFilterAmbiguous,
    ChatModelUnavailable,
)
from ..chat.openai_provider import OpenAIChatModelProvider
from ..chat.schemas import (
    ChatAnswerContext,
    ChatEvidenceItem,
    ChatHistoryItem,
    ChatPlan,
    ChatRequest,
    TitleMatchResult,
    WebExtractedItem,
    WebListExtraction,
)


class OpenAIProviderTests(TestCase):
    def test_openai_adapter_returns_typed_plan_and_passes_history(self):
        expected_plan = ChatPlan(
            action="catalog_and_web",
            web_query="Find missing Foundation books",
            web_objective="Find reliable lists and extract missing titles.",
            site_url="https://example.com",
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=expected_plan
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )
        request = ChatRequest(
            message="And on this site?",
            history=[ChatHistoryItem(role="user", content="Find Foundation")],
        )

        result = provider.create_plan(request)

        self.assertEqual(result, expected_plan)
        call = client.responses.parse.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["text_format"], ChatPlan)
        self.assertEqual(call["max_output_tokens"], 1200)
        self.assertEqual(call["input"][-2]["content"], "Find Foundation")
        self.assertEqual(call["input"][-1]["content"], "And on this site?")

    def test_openai_adapter_converts_sdk_errors(self):
        client = Mock()
        client.responses.parse.side_effect = RuntimeError("provider details")
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )

        with self.assertRaises(ChatModelUnavailable):
            provider.create_plan(ChatRequest(message="Find books"))

    def test_openai_adapter_rejects_incomplete_response(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            status="incomplete",
            output_parsed=ChatPlan(action="catalog"),
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )

        with self.assertRaises(ChatModelUnavailable):
            provider.create_plan(ChatRequest(message="Find books"))

    def test_openai_adapter_preserves_partial_text_response(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            status="incomplete",
            output_text="Partial answer",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )

        result = provider.create_answer(
            ChatRequest(message="List books"),
            ChatAnswerContext(),
        )

        self.assertEqual(result.text, "Partial answer")
        self.assertTrue(result.truncated)

    def test_openai_adapter_rejects_partial_text_for_other_incomplete_reason(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            status="incomplete",
            output_text="Unsafe partial answer",
            incomplete_details=SimpleNamespace(reason="content_filter"),
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )

        with self.assertRaises(ChatModelUnavailable):
            provider.create_answer(
                ChatRequest(message="List books"),
                ChatAnswerContext(),
            )

    def test_openai_adapter_builds_answer_from_typed_evidence(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="Foundation is in the local catalog."
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )
        context = ChatAnswerContext(
            local_items=[
                ChatEvidenceItem(title="Foundation", subtitle="Isaac Asimov")
            ]
        )

        answer = provider.create_answer(
            ChatRequest(message="Do I have Foundation?"),
            context,
        )

        self.assertEqual(answer.text, "Foundation is in the local catalog.")
        self.assertFalse(answer.truncated)
        call = client.responses.create.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["max_output_tokens"], 1600)
        self.assertIn('"title":"Foundation"', call["input"][-1]["content"])

    def test_openai_adapter_builds_catalog_clarification_from_candidates(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text=(
                "Я нашёл похожего автора: Isaac Asimov. "
                "Вы имели в виду его?"
            )
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )
        ambiguity = CatalogFilterAmbiguous(
            entity="author",
            requested="Айзек Азимов",
            candidates=["Isaac Asimov"],
        )

        question = provider.create_catalog_clarification(
            ChatRequest(message="Какие книги написал Айзек Азимов?"),
            ambiguity,
        )

        self.assertIn("Isaac Asimov", question.text)
        call = client.responses.create.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["max_output_tokens"], 500)
        self.assertIn("Isaac Asimov", call["input"][-1]["content"])

    def test_list_extraction_receives_original_request_history(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=WebListExtraction(
                items=[WebExtractedItem(name="Robbie")],
                coverage="complete",
            )
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )
        request = ChatRequest(
            message="да",
            history=[
                ChatHistoryItem(
                    role="user",
                    content="Составь полный перечень рассказов Азимова.",
                ),
                ChatHistoryItem(
                    role="assistant",
                    content="Вы имеете в виду Isaac Asimov?",
                ),
            ],
        )

        provider.extract_web_list(request, [])

        messages = client.responses.parse.call_args.kwargs["input"]
        self.assertEqual(
            client.responses.parse.call_args.kwargs["max_output_tokens"],
            6000,
        )
        self.assertEqual(
            messages[1]["content"],
            "Составь полный перечень рассказов Азимова.",
        )
        self.assertEqual(messages[3]["content"], "да")

    def test_title_matching_uses_output_limit(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=TitleMatchResult()
        )
        provider = OpenAIChatModelProvider(
            api_key="test-key",
            model="test-model",
            timeout=3,
            client=client,
        )

        provider.match_titles(["Солярис"], ["Solaris"])

        self.assertEqual(
            client.responses.parse.call_args.kwargs["max_output_tokens"],
            3000,
        )
