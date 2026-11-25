from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .catalog_provider import LocalCatalogProvider
from .contracts import ChatModelProvider, WebSearchProvider
from .mock_providers import MockChatModelProvider, MockWebSearchProvider
from .services import ChatOrchestrator


def build_chat_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        model=build_model_provider(),
        catalog=LocalCatalogProvider(),
        web_search=build_web_search_provider(),
    )


def build_model_provider() -> ChatModelProvider:
    if settings.CHAT_MODEL_PROVIDER == "mock":
        return MockChatModelProvider()
    if settings.CHAT_MODEL_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ImproperlyConfigured(
                "OPENAI_API_KEY is required when CHAT_MODEL_PROVIDER=openai."
            )
        from .openai_provider import OpenAIChatModelProvider

        return OpenAIChatModelProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            timeout=settings.CHAT_PROVIDER_TIMEOUT,
            plan_max_output_tokens=settings.CHAT_PLAN_MAX_OUTPUT_TOKENS,
            clarification_max_output_tokens=(
                settings.CHAT_CLARIFICATION_MAX_OUTPUT_TOKENS
            ),
            answer_max_output_tokens=settings.CHAT_ANSWER_MAX_OUTPUT_TOKENS,
            list_max_output_tokens=settings.CHAT_LIST_MAX_OUTPUT_TOKENS,
            title_match_max_output_tokens=(
                settings.CHAT_TITLE_MATCH_MAX_OUTPUT_TOKENS
            ),
        )
    raise ImproperlyConfigured(
        f"Unsupported CHAT_MODEL_PROVIDER: {settings.CHAT_MODEL_PROVIDER}."
    )


def build_web_search_provider() -> WebSearchProvider:
    if settings.WEB_SEARCH_PROVIDER == "mock":
        return MockWebSearchProvider()
    if settings.WEB_SEARCH_PROVIDER == "exa":
        if not settings.EXA_API_KEY:
            raise ImproperlyConfigured(
                "EXA_API_KEY is required when WEB_SEARCH_PROVIDER=exa."
            )
        from .exa_provider import ExaWebSearchProvider

        return ExaWebSearchProvider(
            api_key=settings.EXA_API_KEY,
            timeout=settings.CHAT_PROVIDER_TIMEOUT,
            result_limit=settings.CHAT_WEB_RESULT_LIMIT,
            site_result_limit=settings.CHAT_SITE_RESULT_LIMIT,
            content_max_chars=settings.CHAT_WEB_CONTENT_MAX_CHARS,
            content_total_max_chars=settings.CHAT_WEB_CONTENT_TOTAL_MAX_CHARS,
        )
    raise ImproperlyConfigured(
        f"Unsupported WEB_SEARCH_PROVIDER: {settings.WEB_SEARCH_PROVIDER}."
    )
