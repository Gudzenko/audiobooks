from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from ..chat.factories import build_model_provider, build_web_search_provider


class ChatProviderFactoryTests(TestCase):
    @override_settings(CHAT_MODEL_PROVIDER="openai", OPENAI_API_KEY="")
    def test_openai_factory_requires_key(self):
        with self.assertRaises(ImproperlyConfigured):
            build_model_provider()

    @override_settings(
        CHAT_MODEL_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
        CHAT_PROVIDER_TIMEOUT=7,
        CHAT_PLAN_MAX_OUTPUT_TOKENS=1100,
        CHAT_CLARIFICATION_MAX_OUTPUT_TOKENS=400,
        CHAT_ANSWER_MAX_OUTPUT_TOKENS=1500,
        CHAT_LIST_MAX_OUTPUT_TOKENS=5500,
        CHAT_TITLE_MATCH_MAX_OUTPUT_TOKENS=2500,
    )
    @patch("store.chat.openai_provider.OpenAIChatModelProvider")
    def test_factory_selects_openai_adapter(self, provider_class):
        provider = build_model_provider()

        self.assertEqual(provider, provider_class.return_value)
        provider_class.assert_called_once_with(
            api_key="test-key",
            model="test-model",
            timeout=7,
            plan_max_output_tokens=1100,
            clarification_max_output_tokens=400,
            answer_max_output_tokens=1500,
            list_max_output_tokens=5500,
            title_match_max_output_tokens=2500,
        )

    @override_settings(WEB_SEARCH_PROVIDER="exa", EXA_API_KEY="")
    def test_exa_factory_requires_key(self):
        with self.assertRaises(ImproperlyConfigured):
            build_web_search_provider()

    @override_settings(
        WEB_SEARCH_PROVIDER="exa",
        EXA_API_KEY="test-key",
        CHAT_PROVIDER_TIMEOUT=7,
        CHAT_WEB_RESULT_LIMIT=3,
        CHAT_SITE_RESULT_LIMIT=25,
        CHAT_WEB_CONTENT_MAX_CHARS=75000,
        CHAT_WEB_CONTENT_TOTAL_MAX_CHARS=125000,
    )
    @patch("store.chat.exa_provider.ExaWebSearchProvider")
    def test_factory_selects_exa_adapter(self, provider_class):
        provider = build_web_search_provider()

        self.assertEqual(provider, provider_class.return_value)
        provider_class.assert_called_once_with(
            api_key="test-key",
            timeout=7,
            result_limit=3,
            site_result_limit=25,
            content_max_chars=75000,
            content_total_max_chars=125000,
        )
