from fastmcp import FastMCP


mcp = FastMCP(
    name="Audiobooks Library",
    instructions="Read-only access to the audiobooks catalog.",
)

from .tools import (
    get_item,
    search_authors,
    search_books,
    search_genres,
    search_series,
    summarize_books,
    suggest_items,
)

for tool in (
    search_books,
    search_authors,
    search_genres,
    search_series,
    get_item,
    summarize_books,
    suggest_items,
):
    mcp.tool(tool)
