import logging
from urllib.parse import urlparse

from exa_py import Exa

from .contracts import WebSearchUnavailable
from .formatting import make_source_excerpt
from .modes import WebSearchMode
from .schemas import WebSearchItem, WebSearchResponse


logger = logging.getLogger(__name__)


class _WebContentUnavailable(Exception):
    pass


class ExaWebSearchProvider:
    is_demo = False

    def __init__(
        self,
        *,
        api_key: str,
        timeout: float,
        result_limit: int,
        site_result_limit: int = 12,
        content_max_chars: int = 10_000,
        content_total_max_chars: int = 24_000,
        client=None,
    ):
        self.result_limit = result_limit
        self.site_result_limit = site_result_limit
        self.content_max_chars = content_max_chars
        self.content_total_max_chars = content_total_max_chars
        self.timeout = timeout
        self.client = client or Exa(api_key=api_key, timeout=timeout)

    def search(
        self,
        *,
        query: str,
        objective: str,
        site_url: str | None = None,
        mode: WebSearchMode = "lookup",
    ) -> WebSearchResponse:
        options = {
            "type": "auto",
            "num_results": self.result_limit,
            "contents": {"highlights": True},
        }
        if site_url:
            domain_filter = self._domain_filter(site_url)
            if domain_filter:
                options["include_domains"] = [domain_filter]

        if mode == "complete_list":
            options["contents"] = {"highlights": True}
        elif mode == "site_inventory":
            options["num_results"] = self.site_result_limit

        try:
            response = self.client.search(query, objective=objective, **options)
        except Exception as error:
            raise WebSearchUnavailable from error

        results = [self._map_result(result) for result in response.results]
        full_content_unavailable = (
            mode == "site_inventory"
            and len(results) >= self.site_result_limit
        )
        if mode == "complete_list":
            try:
                results, full_content_unavailable = self._load_full_contents(
                    results
                )
            except _WebContentUnavailable:
                full_content_unavailable = True
                logger.warning(
                    "Could not load full web page contents; using search "
                    "excerpts instead",
                    exc_info=True,
                )
        results, content_truncated = self._limit_result_contents(results)
        full_content_unavailable = (
            full_content_unavailable or content_truncated
        )
        return WebSearchResponse(
            results=results,
            full_content_unavailable=full_content_unavailable,
        )

    @staticmethod
    def _domain_filter(site_url: str) -> str:
        parsed = urlparse(site_url)
        if not parsed.hostname:
            return ""
        path = parsed.path.rstrip("/")
        return f"{parsed.hostname}{path}"

    def _load_full_contents(
        self,
        results: list[WebSearchItem],
    ) -> tuple[list[WebSearchItem], bool]:
        if not results:
            return results, False

        requested_urls = [str(item.url) for item in results]
        per_page_limit = min(
            self.content_max_chars,
            max(1, self.content_total_max_chars // len(requested_urls)),
        )
        try:
            response = self.client.get_contents(
                requested_urls,
                text={"max_characters": per_page_limit},
                timeout=max(self.timeout, 60),
            )
        except Exception as error:
            raise _WebContentUnavailable from error
        statuses = {
            str(status.id): status.status
            for status in getattr(response, "statuses", [])
        }
        full_text_by_url = {}
        content_truncated = False
        for item in response.results:
            url = str(item.url)
            text = getattr(item, "text", None)
            if (
                not text
                or (statuses and statuses.get(url) != "success")
            ):
                continue
            content_truncated = content_truncated or len(text) >= per_page_limit
            full_text_by_url[url] = text
        incomplete = bool(statuses) and any(
            statuses.get(url) != "success" for url in requested_urls
        )
        incomplete = incomplete or any(
            url not in full_text_by_url for url in requested_urls
        )
        incomplete = incomplete or content_truncated
        for item in results:
            item.content = full_text_by_url.get(str(item.url), item.content)
        return results, incomplete

    def _limit_result_contents(
        self,
        results: list[WebSearchItem],
    ) -> tuple[list[WebSearchItem], bool]:
        remaining_chars = self.content_total_max_chars
        truncated = False
        for item in results:
            if len(item.content) > remaining_chars:
                item.content = item.content[:remaining_chars]
                truncated = True
            remaining_chars -= len(item.content)
            if remaining_chars <= 0:
                remaining_chars = 0
        return results, truncated

    @staticmethod
    def _map_result(result) -> WebSearchItem:
        highlights = getattr(result, "highlights", None) or []
        content = " ".join(highlights).strip()
        return WebSearchItem(
            title=result.title or result.url,
            subtitle=make_source_excerpt(content),
            content=content,
            url=result.url,
        )
