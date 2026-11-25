from dataclasses import dataclass

from store.mcp.text_matching import normalize_text


@dataclass(frozen=True)
class ListComparison:
    matched: list[str]
    missing: list[str]
    unmatched_local: list[str]


@dataclass(frozen=True)
class SiteComparison:
    matched: list[tuple[str, str]]
    site_only: list[str]
    local_only: list[str]


def compare_external_list(
    external_items,
    local_books,
    title_matches=(),
) -> ListComparison:
    external_items = _unique_external_items(external_items)
    local_by_title = {
        normalize_text(book.title): book.title
        for book in local_books
    }
    external_name_to_item = _external_name_index(external_items)
    suggested_matches = _validated_match_map(
        title_matches,
        external_name_to_item,
        local_by_title,
    )
    matched = []
    missing = []
    matched_local_titles = set()

    for item in external_items:
        candidate_names = [item.name, *item.alternative_names]
        local_title = suggested_matches.get(normalize_text(item.name)) or next(
            (
                local_by_title[normalize_text(name)]
                for name in candidate_names
                if normalize_text(name) in local_by_title
            ),
            None,
        )
        local_key = normalize_text(local_title) if local_title else ""
        if local_title and local_key not in matched_local_titles:
            matched.append(item.name)
            matched_local_titles.add(local_key)
        else:
            missing.append(item.name)

    unmatched_local = [
        book.title
        for book in local_books
        if normalize_text(book.title) not in matched_local_titles
    ]
    return ListComparison(matched, missing, unmatched_local)


def compare_site_inventory(
    external_items,
    local_books,
    title_matches,
) -> SiteComparison:
    external_items = _unique_external_items(external_items)
    external_name_to_item = _external_name_index(external_items)
    local_by_normalized = {
        normalize_text(book.title): book.title
        for book in local_books
    }
    matched = []
    used_external = set()
    used_local = set()

    suggested_matches = _validated_match_map(
        title_matches,
        external_name_to_item,
        local_by_normalized,
    )

    for item in external_items:
        external_key = normalize_text(item.name)
        candidate_names = [item.name, *item.alternative_names]
        local_title = suggested_matches.get(external_key) or next(
            (
                local_by_normalized[normalize_text(name)]
                for name in candidate_names
                if normalize_text(name) in local_by_normalized
            ),
            None,
        )
        local_key = normalize_text(local_title) if local_title else ""
        if not local_title or local_key in used_local:
            continue
        matched.append((item.name, local_title))
        used_external.add(external_key)
        used_local.add(local_key)

    site_only = [
        item.name
        for item in external_items
        if normalize_text(item.name) not in used_external
    ]
    local_only = [
        book.title
        for book in local_books
        if normalize_text(book.title) not in used_local
    ]
    return SiteComparison(matched, site_only, local_only)


def _unique_external_items(external_items):
    unique = []
    seen_names = set()
    for item in external_items:
        key = normalize_text(item.name)
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        unique.append(item)
    return unique


def _external_name_index(external_items):
    return {
        normalize_text(name): item
        for item in external_items
        for name in [item.name, *item.alternative_names]
        if normalize_text(name)
    }


def _validated_match_map(title_matches, external_name_to_item, local_by_title):
    matches = {}
    used_local = set()
    for match in title_matches:
        external_item = external_name_to_item.get(
            normalize_text(match.external_name)
        )
        local_key = normalize_text(match.local_title)
        if not external_item or local_key not in local_by_title:
            continue
        external_key = normalize_text(external_item.name)
        if external_key in matches or local_key in used_local:
            continue
        matches[external_key] = local_by_title[local_key]
        used_local.add(local_key)
    return matches
