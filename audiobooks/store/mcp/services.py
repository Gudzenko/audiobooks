"""Stable service API used by MCP tools and tests."""

from .book_services import search_books, summarize_books
from .catalog_services import (
    get_item,
    search_authors,
    search_genres,
    search_series,
    suggest_items,
)

__all__ = [
    "get_item",
    "search_authors",
    "search_books",
    "search_genres",
    "search_series",
    "summarize_books",
    "suggest_items",
]
