from .schemas import (
    AuthorSearchResult,
    BookSearchFilters,
    BookSearchResult,
    BookSummaryQuery,
    BookSummaryResult,
    CatalogItemDetails,
    EntitySearchQuery,
    GetItemQuery,
    GenreSearchResult,
    ItemSuggestionQuery,
    ItemSuggestionResult,
    SeriesSearchResult,
)
from .services import (
    get_item as get_item_service,
    search_authors as search_authors_service,
    search_books as search_books_service,
    search_genres as search_genres_service,
    search_series as search_series_service,
    summarize_books as summarize_books_service,
    suggest_items as suggest_items_service,
)


def get_item(query: GetItemQuery) -> CatalogItemDetails:
    """Get one catalog entity by type and ID.

    Use a search tool first to discover the ID. Book details include authors,
    genres, series, and audio availability, but never audio file names or paths.
    """
    return get_item_service(query)


def summarize_books(query: BookSummaryQuery) -> BookSummaryResult:
    """Count books grouped by an author, genre, series, read state, or audio state.

    Optional filters are combined exactly as in `search_books`. Use this tool
    for aggregate questions without retrieving every matching book.
    """
    return summarize_books_service(query)


def suggest_items(query: ItemSuggestionQuery) -> ItemSuggestionResult:
    """Suggest catalog items for a possibly misspelled name or title.

    Suggestions are never applied automatically. Each candidate includes a
    similarity score; use its ID only after selecting the intended item.
    """
    return suggest_items_service(query)


def search_books(filters: BookSearchFilters) -> BookSearchResult:
    """Search the local audiobook catalog using combinable filters.

    Filters from different groups are combined with AND. Multiple author or
    genre IDs use the corresponding `authors_match` or `genres_match` mode.
    This tool is read-only and does not return audio file names or paths.
    """
    return search_books_service(filters)


def search_authors(query: EntitySearchQuery) -> AuthorSearchResult:
    """Find authors and their IDs by a full or partial name.

    The search is case-insensitive, accepts either first-last or last-first
    order and normalizes case, spacing, transliteration, and diacritics.
    Use returned IDs in `search_books`.
    """
    return search_authors_service(query)


def search_genres(query: EntitySearchQuery) -> GenreSearchResult:
    """Find genres and their IDs by a full or partial name.

    The search normalizes case, spacing, transliteration, and diacritics.
    Use returned IDs in `search_books`.
    """
    return search_genres_service(query)


def search_series(query: EntitySearchQuery) -> SeriesSearchResult:
    """Find book series and their IDs by a full or partial title.

    The search normalizes case, spacing, transliteration, and diacritics.
    Use returned IDs in `search_books`.
    """
    return search_series_service(query)
