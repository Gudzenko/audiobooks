from urllib.parse import urlsplit, urlunsplit

from django.urls import reverse
from django.utils.translation import gettext as _

from .schemas import ChatLink, ChatResultItem, ChatSection


def build_local_section(books) -> ChatSection:
    return ChatSection(
        title=_("Local catalog"),
        items=[
            ChatResultItem(
                title=book.title,
                subtitle=", ".join(author.name for author in book.authors),
                status=_("In local catalog"),
                links=[
                    ChatLink(
                        label=_("Open book"),
                        url=reverse("book_detail", kwargs={"slug": book.slug}),
                    )
                ],
            )
            for book in books
        ],
    )


def build_external_section(
    results,
    *,
    is_demo: bool,
    compared: bool = False,
    compact: bool = False,
) -> ChatSection:
    return ChatSection(
        title=_("Web results"),
        items=[
            ChatResultItem(
                title=item.title,
                subtitle="" if compact else item.subtitle,
                status="" if compared else _("Not compared"),
                links=[
                    ChatLink(
                        label=_("Open source"),
                        url=str(item.url),
                        is_demo=is_demo,
                    )
                ],
            )
            for item in results
        ],
    )


def build_site_inventory_section(
    extracted_items,
    results,
    *,
    is_demo: bool,
) -> ChatSection:
    extracted_items = verified_site_inventory_items(extracted_items, results)
    exact_results, fallback_results = _result_url_indexes(results)
    items = []
    for item in extracted_items:
        result = _find_source_result(
            item.source_url,
            exact_results,
            fallback_results,
        )
        items.append(
            ChatResultItem(
                title=item.name,
                links=[
                    ChatLink(
                        label=_("Open source"),
                        url=str(result.url),
                        is_demo=is_demo,
                    )
                ],
            )
        )
    return ChatSection(
        title=_("Sources"),
        items=items,
    )


def verified_site_inventory_items(extracted_items, results):
    exact_results, fallback_results = _result_url_indexes(results)
    verified = []
    for item in extracted_items:
        result = _find_source_result(
            item.source_url,
            exact_results,
            fallback_results,
        )
        if result is None:
            continue
        verified.append(item)
    return verified


def _result_url_indexes(results):
    exact_results = {}
    fallback_candidates = {}
    for result in results:
        exact_key = _source_url_key(str(result.url), include_query=True)
        fallback_key = _source_url_key(str(result.url), include_query=False)
        if exact_key:
            exact_results.setdefault(exact_key, result)
        if fallback_key:
            fallback_candidates.setdefault(fallback_key, []).append(result)
    fallback_results = {
        key: candidates[0]
        for key, candidates in fallback_candidates.items()
        if len(candidates) == 1
    }
    return exact_results, fallback_results


def _find_source_result(source_url, exact_results, fallback_results):
    exact_key = _source_url_key(source_url, include_query=True)
    if exact_key in exact_results:
        return exact_results[exact_key]
    fallback_key = _source_url_key(source_url, include_query=False)
    return fallback_results.get(fallback_key)


def _source_url_key(value, *, include_query):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    hostname = parsed.hostname.casefold()
    if port and not (
        (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    path = parsed.path.rstrip("/") or "/"
    query = parsed.query if include_query else ""
    return urlunsplit((parsed.scheme.casefold(), hostname, path, query, ""))
