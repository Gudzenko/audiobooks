from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils.translation import gettext as _

from store.mcp.text_matching import normalize_text

from .answer_context import build_answer_context
from .catalog_comparison import compare_external_list, compare_site_inventory
from .constants import MAX_WEB_LIST_ITEMS
from .contracts import (
    CatalogFilterAmbiguous,
    CatalogProvider,
    ChatModelProvider,
    WebSearchProvider,
    WebSearchUnavailable,
)
from .response_formatters import (
    format_external_list,
    format_list_comparison,
    format_site_comparison,
    format_site_inventory,
)
from .response_sections import (
    build_external_section,
    build_local_section,
    build_site_inventory_section,
    verified_site_inventory_items,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    TitleMatchResult,
)


class ChatOrchestrator:
    def __init__(self, *, model, catalog, web_search):
        self.model: ChatModelProvider = model
        self.catalog: CatalogProvider = catalog
        self.web_search: WebSearchProvider = web_search

    def reply(self, chat_request: ChatRequest) -> ChatResponse:
        plan = self.model.create_plan(chat_request)
        if plan.action == "clarification":
            return ChatResponse(kind="clarification", message=plan.clarification)

        catalog_result = self._search_catalog(chat_request, plan)
        if isinstance(catalog_result, ChatResponse):
            return catalog_result
        local_books, local_section, catalog_warnings = catalog_result

        if plan.action == "catalog":
            answer = self.model.create_answer(
                chat_request,
                build_answer_context(local_books=local_books),
            )
            response_warnings = [
                *catalog_warnings,
                *self._model_output_warnings(answer),
            ]
            return ChatResponse(
                kind="partial" if response_warnings else "answer",
                message=answer.text,
                sections=[local_section],
                warnings=response_warnings,
            )

        try:
            web_response = self.web_search.search(
                query=plan.web_query,
                objective=plan.web_objective,
                site_url=plan.site_url,
                mode=plan.web_mode,
            )
        except WebSearchUnavailable:
            return self._web_failure(
                chat_request, local_books, local_section, catalog_warnings
            )

        if plan.web_mode == "site_inventory":
            return self._site_inventory_response(
                chat_request,
                plan,
                local_books,
                local_section,
                catalog_warnings,
                web_response,
            )
        if plan.web_mode == "complete_list":
            return self._complete_list_response(
                chat_request,
                local_books,
                local_section,
                catalog_warnings,
                web_response,
            )
        return self._standard_web_response(
            chat_request,
            local_books,
            local_section,
            catalog_warnings,
            web_response,
        )

    def _search_catalog(self, chat_request, plan):
        if plan.action == "web":
            return [], None, []
        try:
            catalog_result = async_to_sync(self.catalog.search_books)(
                plan.catalog_filters,
                limit=settings.CHAT_CATALOG_RESULT_LIMIT,
            )
        except CatalogFilterAmbiguous as error:
            clarification = self.model.create_catalog_clarification(
                chat_request,
                error,
            )
            return ChatResponse(
                kind="clarification",
                message=clarification.text,
                warnings=self._model_output_warnings(clarification),
            )
        warnings = []
        if catalog_result.truncated:
            warnings.append(
                _(
                    "The local catalog contains %(total)d matching books. "
                    "Only the first %(limit)d are shown. Refine the request by "
                    "author, series, genre, or combine several filters."
                )
                % {
                    "total": catalog_result.total,
                    "limit": settings.CHAT_CATALOG_RESULT_LIMIT,
                }
            )
        return (
            catalog_result.items,
            build_local_section(catalog_result.items),
            warnings,
        )

    def _web_failure(
        self, chat_request, local_books, local_section, catalog_warnings
    ):
        answer = self.model.create_answer(
            chat_request,
            build_answer_context(
                local_books=local_books,
                web_search_unavailable=True,
            ),
        )
        return ChatResponse(
            kind="partial",
            message=answer.text,
            sections=[local_section] if local_section else [],
            warnings=[
                *catalog_warnings,
                self._web_failure_warning(),
                *self._model_output_warnings(answer),
            ],
        )

    def _site_inventory_response(
        self,
        chat_request,
        plan,
        local_books,
        local_section,
        catalog_warnings,
        web_response,
    ):
        extraction = self.model.extract_web_list(
            chat_request,
            web_response.results,
            mode="site_inventory",
        )
        verified_items = verified_site_inventory_items(
            extraction.items,
            web_response.results,
        )
        omitted_items = len(extraction.items) - len(verified_items)
        response_warnings = [
            *catalog_warnings,
            *self._external_list_warnings(extraction),
            *self._unverified_site_items_warnings(omitted_items),
            *self._web_content_warnings(web_response),
        ]
        source_section = build_site_inventory_section(
            verified_items,
            web_response.results,
            is_demo=self.web_search.is_demo,
        )
        if local_section:
            title_matches = self._match_titles(verified_items, local_books)
            comparison = compare_site_inventory(
                verified_items,
                local_books,
                title_matches.matches,
            )
            message = format_site_comparison(
                comparison,
                extraction.limitations,
                plan.site_url,
            )
            sections = [local_section, source_section]
        else:
            message = format_site_inventory(
                verified_items,
                extraction.limitations,
                plan.site_url,
            )
            sections = [source_section]
        return ChatResponse(
            kind=self._coverage_kind(extraction.coverage, response_warnings),
            message=message,
            sections=sections,
            warnings=response_warnings,
        )

    def _complete_list_response(
        self,
        chat_request,
        local_books,
        local_section,
        catalog_warnings,
        web_response,
    ):
        extraction = self.model.extract_web_list(
            chat_request,
            web_response.results,
            mode="complete_list",
        )
        response_warnings = [
            *catalog_warnings,
            *self._external_list_warnings(extraction),
            *self._web_content_warnings(web_response),
        ]
        external_section = build_external_section(
            web_response.results,
            is_demo=self.web_search.is_demo,
            compared=True,
            compact=True,
        )
        if local_section is None:
            message = format_external_list(
                extraction.items,
                extraction.limitations,
            )
        else:
            title_matches = self._match_titles(extraction.items, local_books)
            comparison = compare_external_list(
                extraction.items,
                local_books,
                title_matches.matches,
            )
            message = format_list_comparison(
                comparison,
                extraction.limitations,
            )
        return ChatResponse(
            kind=self._coverage_kind(extraction.coverage, response_warnings),
            message=message,
            sections=self._sections(local_section, external_section),
            warnings=response_warnings,
        )

    def _standard_web_response(
        self,
        chat_request,
        local_books,
        local_section,
        catalog_warnings,
        web_response,
    ):
        external_section = build_external_section(
            web_response.results,
            is_demo=self.web_search.is_demo,
        )
        answer = self.model.create_answer(
            chat_request,
            build_answer_context(
                local_books=local_books,
                web_response=web_response,
            ),
        )
        response_warnings = [
            *catalog_warnings,
            *self._model_output_warnings(answer),
            *self._web_content_warnings(web_response),
            *(
                [
                    _(
                        "External results are demonstration data. "
                        "No website was contacted."
                    )
                ]
                if self.web_search.is_demo
                else []
            ),
        ]
        return ChatResponse(
            kind="partial" if response_warnings else "answer",
            message=answer.text,
            sections=self._sections(local_section, external_section),
            warnings=response_warnings,
        )

    @staticmethod
    def _model_output_warnings(result):
        if not result.truncated:
            return []
        return [
            _(
                "The answer reached the configured size limit. "
                "Refine the request to get a more complete result."
            )
        ]

    def _web_failure_warning(self) -> str:
        if self.web_search.is_demo:
            return _(
                "This is a simulated external-service failure. The result is "
                "partial and external data was not checked."
            )
        return _(
            "Web search is temporarily unavailable. The result is partial and "
            "external data was not checked."
        )

    @staticmethod
    def _external_list_warnings(extraction):
        if not extraction.truncated:
            return []
        return [
            _(
                "The external source returned too many items. Only the first "
                "%(limit)d are shown. Refine the request by author, series, "
                "genre, or combine several filters."
            )
            % {"limit": MAX_WEB_LIST_ITEMS}
        ]

    @staticmethod
    def _web_content_warnings(web_response):
        if not web_response.full_content_unavailable:
            return []
        return [
            _(
                "Some external source content was unavailable or limited. "
                "The result may be incomplete."
            )
        ]

    @staticmethod
    def _unverified_site_items_warnings(omitted_items):
        if not omitted_items:
            return []
        return [
            _(
                "Some items extracted from the site were omitted because their "
                "source links did not match the web search results."
            )
        ]

    @staticmethod
    def _coverage_kind(coverage, warnings=()):
        return "answer" if coverage == "complete" and not warnings else "partial"

    def _match_titles(self, external_items, local_books):
        if not external_items or not local_books:
            return TitleMatchResult()
        local_by_normalized = {
            normalize_text(book.title): book.title
            for book in local_books
        }
        exactly_matched_local = set()
        unresolved_external_names = []
        for item in external_items:
            candidate_names = [item.name, *item.alternative_names]
            exact_local_key = next(
                (
                    normalize_text(name)
                    for name in candidate_names
                    if normalize_text(name) in local_by_normalized
                ),
                None,
            )
            if exact_local_key:
                exactly_matched_local.add(exact_local_key)
            else:
                unresolved_external_names.append(item.name)

        unmatched_local_titles = [
            title
            for key, title in local_by_normalized.items()
            if key not in exactly_matched_local
        ]
        if not unresolved_external_names or not unmatched_local_titles:
            return TitleMatchResult()
        external_names = list(
            dict.fromkeys(unresolved_external_names)
        )
        return self.model.match_titles(
            external_names,
            unmatched_local_titles,
        )

    @staticmethod
    def _sections(local_section, external_section):
        return (
            [local_section, external_section]
            if local_section
            else [external_section]
        )
