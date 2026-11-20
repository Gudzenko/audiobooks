from django.db.models import Count, Q, QuerySet, Subquery

from store.models import Author, Book, Genre, Series

from .schemas import (
    BookFilterCriteria,
    BookSearchFilters,
    BookSearchItem,
    BookSearchResult,
    BookSummaryGroup,
    BookSummaryQuery,
    BookSummaryResult,
    CatalogReference,
)
from .text_matching import normalize_text


def search_books(filters: BookSearchFilters) -> BookSearchResult:
    queryset = _build_book_queryset(filters, sort=filters.sort)
    total = queryset.count()
    books = queryset[filters.offset:filters.offset + filters.limit]
    return BookSearchResult(
        items=[_serialize_book(book) for book in books],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


def summarize_books(query: BookSummaryQuery) -> BookSummaryResult:
    books = _build_book_queryset(query.filters)
    total_books = books.count()
    book_ids = Subquery(books.values("id"))

    if query.group_by == "author":
        groups = _related_summary_groups(
            Author.objects.filter(books__id__in=book_ids).order_by(
                "last_name", "first_name"
            ),
            book_ids,
            value=lambda item: str(item),
        )
    elif query.group_by == "genre":
        groups = _related_summary_groups(
            Genre.objects.filter(books__id__in=book_ids).order_by("name"),
            book_ids,
            value=lambda item: item.name,
        )
    elif query.group_by == "series":
        groups = _related_summary_groups(
            Series.objects.filter(books__id__in=book_ids).order_by("title"),
            book_ids,
            value=lambda item: item.title,
        )
        without_series = books.filter(series__isnull=True).count()
        if without_series:
            groups.append(BookSummaryGroup(value="No series", count=without_series))
    elif query.group_by == "is_read":
        groups = _boolean_summary_groups(books, field="is_read")
    else:
        groups = [
            BookSummaryGroup(
                value=True,
                count=books.filter(audio_files_count__gt=0).count(),
            ),
            BookSummaryGroup(
                value=False,
                count=books.filter(audio_files_count=0).count(),
            ),
        ]

    return BookSummaryResult(
        group_by=query.group_by,
        groups=[group for group in groups if group.count > 0],
        total_books=total_books,
    )


def get_book(book_id: int) -> BookSearchItem | None:
    book = _base_book_queryset().filter(pk=book_id).first()
    return _serialize_book(book) if book else None


def _serialize_book(book: Book) -> BookSearchItem:
    return BookSearchItem(
        id=book.id,
        title=book.title,
        slug=book.slug,
        is_read=book.is_read,
        has_audio=book.audio_files_count > 0,
        audio_files_count=book.audio_files_count,
        authors=[
            CatalogReference(id=author.id, name=str(author), slug=author.slug)
            for author in book.authors.all()
        ],
        genres=[
            CatalogReference(id=genre.id, name=genre.name, slug=genre.slug)
            for genre in book.genres.all()
        ],
        series=(
            CatalogReference(
                id=book.series.id,
                name=book.series.title,
                slug=book.series.slug,
            )
            if book.series
            else None
        ),
    )


def _base_book_queryset() -> QuerySet[Book]:
    return (
        Book.objects.select_related("series")
        .prefetch_related("authors", "genres")
        .annotate(audio_files_count=Count("audio_files", distinct=True))
    )


def _build_book_queryset(
    filters: BookFilterCriteria,
    *,
    sort: str | None = None,
) -> QuerySet[Book]:
    queryset = _base_book_queryset()
    if filters.text:
        normalized_query = normalize_text(filters.text)
        if normalized_query:
            queryset = queryset.filter(
                id__in=_matching_book_ids(normalized_query)
            )
    if filters.is_read is not None:
        queryset = queryset.filter(is_read=filters.is_read)
    if filters.series_ids:
        queryset = queryset.filter(series_id__in=filters.series_ids)
    if filters.has_audio is True:
        queryset = queryset.filter(audio_files_count__gt=0)
    elif filters.has_audio is False:
        queryset = queryset.filter(audio_files_count=0)

    queryset = _filter_many_to_many(
        queryset,
        field="authors",
        ids=filters.author_ids,
        match=filters.authors_match,
    )
    queryset = _filter_many_to_many(
        queryset,
        field="genres",
        ids=filters.genre_ids,
        match=filters.genres_match,
    )
    if sort:
        ordering = "title" if sort == "title_asc" else "-title"
        queryset = queryset.order_by(ordering, "id")
    else:
        queryset = queryset.order_by()
    return queryset.distinct()


def _matching_book_ids(query: str) -> list[int]:
    return [
        book_id
        for book_id, title in Book.objects.values_list("id", "title")
        if query in normalize_text(title)
    ]


def _filter_many_to_many(queryset, *, field, ids, match):
    unique_ids = list(dict.fromkeys(ids))
    if not unique_ids:
        return queryset
    if match == "any":
        return queryset.filter(**{f"{field}__id__in": unique_ids})
    for item_id in unique_ids:
        queryset = queryset.filter(**{f"{field}__id": item_id})
    return queryset


def _related_summary_groups(queryset, book_ids, *, value):
    items = queryset.annotate(
        matching_books=Count(
            "books",
            filter=Q(books__id__in=book_ids),
            distinct=True,
        )
    )
    return [
        BookSummaryGroup(id=item.id, value=value(item), count=item.matching_books)
        for item in items
    ]


def _boolean_summary_groups(queryset, *, field):
    return [
        BookSummaryGroup(value=value, count=queryset.filter(**{field: value}).count())
        for value in (True, False)
    ]
