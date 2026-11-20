from django.db.models import Count

from store.models import Author, Book, Genre, Series

from .book_services import get_book
from .schemas import (
    AuthorDetails,
    AuthorSearchItem,
    AuthorSearchResult,
    BookDetails,
    CatalogItemDetails,
    EntitySearchQuery,
    GetItemQuery,
    GenreDetails,
    GenreSearchItem,
    GenreSearchResult,
    ItemSuggestion,
    ItemSuggestionQuery,
    ItemSuggestionResult,
    SeriesDetails,
    SeriesSearchItem,
    SeriesSearchResult,
)
from .text_matching import normalize_text, text_similarity


def search_authors(query: EntitySearchQuery) -> AuthorSearchResult:
    authors = Author.objects.annotate(books_count=Count("books", distinct=True))
    matches = [
        author
        for author in authors
        if _matches_text(
            query.text,
            str(author),
            f"{author.last_name} {author.first_name}",
        )
    ]
    page = matches[query.offset:query.offset + query.limit]
    return AuthorSearchResult(
        items=[_serialize_author(author) for author in page],
        total=len(matches),
        limit=query.limit,
        offset=query.offset,
    )


def search_genres(query: EntitySearchQuery) -> GenreSearchResult:
    genres = Genre.objects.annotate(books_count=Count("books", distinct=True))
    matches = [genre for genre in genres if _matches_text(query.text, genre.name)]
    page = matches[query.offset:query.offset + query.limit]
    return GenreSearchResult(
        items=[_serialize_genre(genre) for genre in page],
        total=len(matches),
        limit=query.limit,
        offset=query.offset,
    )


def search_series(query: EntitySearchQuery) -> SeriesSearchResult:
    series = Series.objects.annotate(
        books_count=Count("books", distinct=True)
    ).order_by("title")
    matches = [item for item in series if _matches_text(query.text, item.title)]
    page = matches[query.offset:query.offset + query.limit]
    return SeriesSearchResult(
        items=[_serialize_series(item) for item in page],
        total=len(matches),
        limit=query.limit,
        offset=query.offset,
    )


def get_item(query: GetItemQuery) -> CatalogItemDetails:
    if query.entity == "book":
        book = get_book(query.id)
        if book is None:
            raise ValueError(f"Book with ID {query.id} was not found.")
        return BookDetails(**book.model_dump())

    model = {"author": Author, "genre": Genre, "series": Series}[query.entity]
    item = (
        model.objects.annotate(books_count=Count("books", distinct=True))
        .filter(pk=query.id)
        .first()
    )
    if item is None:
        raise ValueError(f"{query.entity.capitalize()} with ID {query.id} was not found.")

    if query.entity == "author":
        return AuthorDetails(
            **_serialize_author(item).model_dump(),
            description=item.description,
        )
    if query.entity == "genre":
        return GenreDetails(**_serialize_genre(item).model_dump())
    return SeriesDetails(**_serialize_series(item).model_dump())


def suggest_items(query: ItemSuggestionQuery) -> ItemSuggestionResult:
    candidates = _suggestion_candidates(query.entity)
    suggestions = []
    for item_id, name, comparison_values in candidates:
        score = round(text_similarity(query.text, *comparison_values) * 100)
        if score >= query.min_score:
            suggestions.append(
                ItemSuggestion(
                    id=item_id,
                    entity=query.entity,
                    name=name,
                    score=score,
                )
            )
    suggestions.sort(key=lambda item: (-item.score, item.name.casefold(), item.id))
    return ItemSuggestionResult(
        query=query.text,
        suggestions=suggestions[:query.limit],
    )


def _matches_text(query: str, *values: str) -> bool:
    normalized_query = normalize_text(query)
    return not normalized_query or any(
        normalized_query in normalize_text(value)
        for value in values
    )


def _suggestion_candidates(entity):
    if entity == "book":
        return [(item.id, item.title, (item.title,)) for item in Book.objects.all()]
    if entity == "author":
        return [
            (
                item.id,
                str(item),
                (str(item), f"{item.last_name} {item.first_name}"),
            )
            for item in Author.objects.all()
        ]
    if entity == "genre":
        return [(item.id, item.name, (item.name,)) for item in Genre.objects.all()]
    return [(item.id, item.title, (item.title,)) for item in Series.objects.all()]


def _serialize_author(author: Author) -> AuthorSearchItem:
    return AuthorSearchItem(
        id=author.id,
        name=str(author),
        first_name=author.first_name,
        last_name=author.last_name,
        slug=author.slug,
        books_count=author.books_count,
    )


def _serialize_genre(genre: Genre) -> GenreSearchItem:
    return GenreSearchItem(
        id=genre.id,
        name=genre.name,
        slug=genre.slug,
        books_count=genre.books_count,
    )


def _serialize_series(series: Series) -> SeriesSearchItem:
    return SeriesSearchItem(
        id=series.id,
        name=series.title,
        slug=series.slug,
        books_count=series.books_count,
    )
