from typing import Literal

from pydantic import BaseModel, Field


class BookFilterCriteria(BaseModel):
    text: str | None = Field(
        default=None,
        description="Case-insensitive text contained in the book title.",
    )
    author_ids: list[int] = Field(
        default_factory=list,
        description="Author IDs used to filter books.",
    )
    genre_ids: list[int] = Field(
        default_factory=list,
        description="Genre IDs used to filter books.",
    )
    series_ids: list[int] = Field(
        default_factory=list,
        description="Series IDs used to filter books.",
    )
    is_read: bool | None = Field(
        default=None,
        description="Filter by the library's read/unread flag.",
    )
    has_audio: bool | None = Field(
        default=None,
        description="Filter by whether at least one audio file is registered.",
    )
    authors_match: Literal["any", "all"] = Field(
        default="any",
        description="Whether a book must match any or all supplied author IDs.",
    )
    genres_match: Literal["any", "all"] = Field(
        default="any",
        description="Whether a book must match any or all supplied genre IDs.",
    )


class BookSearchFilters(BookFilterCriteria):
    sort: Literal["title_asc", "title_desc"] = Field(
        default="title_asc",
        description="Result ordering.",
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class BookSummaryFilters(BookFilterCriteria):
    pass


class BookSummaryQuery(BaseModel):
    group_by: Literal["author", "genre", "series", "is_read", "has_audio"]
    filters: BookSummaryFilters = Field(default_factory=BookSummaryFilters)


class BookSummaryGroup(BaseModel):
    id: int | None = None
    value: str | bool
    count: int


class BookSummaryResult(BaseModel):
    group_by: Literal["author", "genre", "series", "is_read", "has_audio"]
    groups: list[BookSummaryGroup]
    total_books: int


class CatalogReference(BaseModel):
    id: int
    name: str
    slug: str


class BookSearchItem(BaseModel):
    id: int
    title: str
    slug: str
    is_read: bool
    has_audio: bool
    audio_files_count: int
    authors: list[CatalogReference]
    genres: list[CatalogReference]
    series: CatalogReference | None


class BookSearchResult(BaseModel):
    items: list[BookSearchItem]
    total: int
    limit: int
    offset: int


class EntitySearchQuery(BaseModel):
    text: str = Field(
        default="",
        description="Partial name with case, spacing, transliteration, and diacritics normalized.",
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ItemSuggestionQuery(BaseModel):
    entity: Literal["book", "author", "genre", "series"]
    text: str = Field(min_length=2, description="Possibly misspelled name or title.")
    limit: int = Field(default=5, ge=1, le=20)
    min_score: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Minimum similarity score from 0 to 100.",
    )


class ItemSuggestion(BaseModel):
    id: int
    entity: Literal["book", "author", "genre", "series"]
    name: str
    score: int


class ItemSuggestionResult(BaseModel):
    query: str
    suggestions: list[ItemSuggestion]


class AuthorSearchItem(BaseModel):
    id: int
    name: str
    first_name: str
    last_name: str
    slug: str
    books_count: int


class GenreSearchItem(BaseModel):
    id: int
    name: str
    slug: str
    books_count: int


class SeriesSearchItem(BaseModel):
    id: int
    name: str
    slug: str
    books_count: int


class AuthorSearchResult(BaseModel):
    items: list[AuthorSearchItem]
    total: int
    limit: int
    offset: int


class GenreSearchResult(BaseModel):
    items: list[GenreSearchItem]
    total: int
    limit: int
    offset: int


class SeriesSearchResult(BaseModel):
    items: list[SeriesSearchItem]
    total: int
    limit: int
    offset: int


class GetItemQuery(BaseModel):
    entity: Literal["book", "author", "genre", "series"] = Field(
        description="Catalog entity type.",
    )
    id: int = Field(gt=0, description="Entity ID returned by a search tool.")


class AuthorDetails(AuthorSearchItem):
    entity: Literal["author"] = "author"
    description: str


class GenreDetails(GenreSearchItem):
    entity: Literal["genre"] = "genre"


class SeriesDetails(SeriesSearchItem):
    entity: Literal["series"] = "series"


class BookDetails(BookSearchItem):
    entity: Literal["book"] = "book"


CatalogItemDetails = BookDetails | AuthorDetails | GenreDetails | SeriesDetails
