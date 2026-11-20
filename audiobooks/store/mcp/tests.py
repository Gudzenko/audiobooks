from django.test import SimpleTestCase, TestCase
from fastmcp import Client

from store.models import AudioFile, Author, Book, Genre, Series

from .schemas import (
    BookSearchFilters,
    BookSummaryFilters,
    BookSummaryQuery,
    EntitySearchQuery,
    GetItemQuery,
    ItemSuggestionQuery,
)
from .server import mcp
from .services import (
    get_item,
    search_authors,
    search_books,
    search_genres,
    search_series,
    summarize_books,
    suggest_items,
)
from .text_matching import normalize_text


class TextNormalizationTests(SimpleTestCase):
    def test_normalizes_cyrillic_yo_without_a_special_case(self):
        self.assertEqual(normalize_text("ВСЁ о книгах"), "vse o knigakh")

    def test_normalizes_polish_letters(self):
        self.assertEqual(normalize_text("Stanisław Łem"), "stanislaw lem")

    def test_normalizes_diacritics_from_other_languages(self):
        self.assertEqual(normalize_text("Gabriel García Márquez"), "gabriel garcia marquez")


class MCPServerSmokeTests(SimpleTestCase):
    async def test_server_exposes_search_books(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()

        self.assertEqual(
            [tool.name for tool in tools],
            [
                "search_books",
                "search_authors",
                "search_genres",
                "search_series",
                "get_item",
                "summarize_books",
                "suggest_items",
            ],
        )


class BookSearchServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asimov = Author.objects.create(first_name="Isaac", last_name="Asimov")
        cls.lem = Author.objects.create(first_name="Stanislaw", last_name="Lem")
        cls.fiction = Genre.objects.create(name="Science Fiction")
        cls.classics = Genre.objects.create(name="Classics")
        cls.foundation = Series.objects.create(title="Foundation")

        cls.first_book = Book.objects.create(
            title="Foundation",
            series=cls.foundation,
            is_read=True,
        )
        cls.first_book.authors.add(cls.asimov)
        cls.first_book.genres.add(cls.fiction, cls.classics)
        AudioFile.objects.create(book=cls.first_book, file="tests/foundation.mp3")

        cls.second_book = Book.objects.create(title="Solaris", is_read=False)
        cls.second_book.authors.add(cls.lem)
        cls.second_book.genres.add(cls.fiction, cls.classics)

        cls.collaboration = Book.objects.create(title="Shared Worlds", is_read=False)
        cls.collaboration.authors.add(cls.asimov, cls.lem)
        cls.collaboration.genres.add(cls.fiction)

    def test_combines_filters_with_and(self):
        result = search_books(
            BookSearchFilters(
                author_ids=[self.asimov.id],
                genre_ids=[self.fiction.id],
                series_ids=[self.foundation.id],
                is_read=True,
                has_audio=True,
            )
        )

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].title, "Foundation")
        self.assertTrue(result.items[0].has_audio)
        self.assertEqual(result.items[0].audio_files_count, 1)

    def test_all_author_matching_requires_every_author(self):
        result = search_books(
            BookSearchFilters(
                author_ids=[self.asimov.id, self.lem.id],
                authors_match="all",
            )
        )

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].title, "Shared Worlds")

    def test_all_genre_matching_requires_every_genre(self):
        result = search_books(
            BookSearchFilters(
                genre_ids=[self.fiction.id, self.classics.id],
                genres_match="all",
            )
        )

        self.assertEqual(result.total, 2)
        self.assertEqual([item.title for item in result.items], ["Foundation", "Solaris"])

    def test_text_filter_is_case_insensitive(self):
        result = search_books(BookSearchFilters(text="SOLAR"))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].title, "Solaris")

    def test_text_filter_handles_cyrillic_case_and_yo(self):
        russian_book = Book.objects.create(title="Всё о муми-троллях")
        russian_book.authors.add(self.lem)
        russian_book.genres.add(self.classics)

        result = search_books(BookSearchFilters(text="ВСЕ О МУМИ"))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].title, "Всё о муми-троллях")

    def test_normalized_text_combines_with_other_filters(self):
        russian_book = Book.objects.create(title="Солярис: возвращение")
        russian_book.authors.add(self.lem)
        russian_book.genres.add(self.fiction)

        result = search_books(
            BookSearchFilters(
                text="СОЛЯРИС",
                author_ids=[self.asimov.id],
            )
        )

        self.assertEqual(result.total, 0)

    def test_pagination_preserves_total(self):
        result = search_books(BookSearchFilters(limit=1, offset=1))

        self.assertEqual(result.total, 3)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.limit, 1)
        self.assertEqual(result.offset, 1)

    def test_can_filter_books_without_audio(self):
        result = search_books(BookSearchFilters(has_audio=False))

        self.assertEqual(result.total, 2)
        self.assertEqual(
            {item.title for item in result.items},
            {"Shared Worlds", "Solaris"},
        )


class EntitySearchServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name="Станислав", last_name="Лем")
        cls.other_author = Author.objects.create(first_name="Айзек", last_name="Азимов")
        cls.genre = Genre.objects.create(name="Всё для детей")
        cls.other_genre = Genre.objects.create(name="Научная фантастика")
        cls.series = Series.objects.create(title="Всё о муми-троллях")
        cls.other_series = Series.objects.create(title="Основание")

        book = Book.objects.create(title="Солярис", is_read=False)
        book.authors.add(cls.author)
        book.genres.add(cls.other_genre)

    def test_author_search_accepts_partial_name_and_reversed_order(self):
        by_partial_name = search_authors(EntitySearchQuery(text="СТАНИС"))
        by_reversed_name = search_authors(EntitySearchQuery(text="лем   станислав"))

        self.assertEqual(by_partial_name.items[0].id, self.author.id)
        self.assertEqual(by_reversed_name.items[0].id, self.author.id)
        self.assertEqual(by_partial_name.items[0].books_count, 1)

    def test_genre_search_treats_yo_and_e_as_equal(self):
        result = search_genres(EntitySearchQuery(text="все для детей"))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].id, self.genre.id)

    def test_series_search_treats_yo_and_e_as_equal(self):
        result = search_series(EntitySearchQuery(text="все о муми"))

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].id, self.series.id)

    def test_empty_query_lists_entities_with_pagination(self):
        result = search_authors(EntitySearchQuery(limit=1, offset=1))

        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.limit, 1)
        self.assertEqual(result.offset, 1)

    def test_discovered_author_id_can_filter_books(self):
        authors = search_authors(EntitySearchQuery(text="Станислав Лем"))
        books = search_books(
            BookSearchFilters(author_ids=[authors.items[0].id])
        )

        self.assertEqual(books.total, 1)
        self.assertEqual(books.items[0].title, "Солярис")


class GetItemServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(
            first_name="Станислав",
            last_name="Лем",
            description="Польский писатель-фантаст.",
        )
        cls.genre = Genre.objects.create(name="Научная фантастика")
        cls.series = Series.objects.create(title="Библиотека фантастики")
        cls.book = Book.objects.create(
            title="Солярис",
            series=cls.series,
            is_read=True,
        )
        cls.book.authors.add(cls.author)
        cls.book.genres.add(cls.genre)
        AudioFile.objects.create(book=cls.book, file="tests/solaris.mp3")

    def test_get_book_returns_relations_without_audio_paths(self):
        result = get_item(GetItemQuery(entity="book", id=self.book.id))

        self.assertEqual(result.entity, "book")
        self.assertEqual(result.title, "Солярис")
        self.assertEqual(result.authors[0].id, self.author.id)
        self.assertEqual(result.genres[0].id, self.genre.id)
        self.assertEqual(result.series.id, self.series.id)
        self.assertTrue(result.has_audio)
        self.assertEqual(result.audio_files_count, 1)
        self.assertNotIn("file", result.model_dump())

    def test_get_author_returns_description_and_books_count(self):
        result = get_item(GetItemQuery(entity="author", id=self.author.id))

        self.assertEqual(result.entity, "author")
        self.assertEqual(result.description, "Польский писатель-фантаст.")
        self.assertEqual(result.books_count, 1)

    def test_get_genre_and_series_return_books_count(self):
        genre = get_item(GetItemQuery(entity="genre", id=self.genre.id))
        series = get_item(GetItemQuery(entity="series", id=self.series.id))

        self.assertEqual(genre.books_count, 1)
        self.assertEqual(series.books_count, 1)

    def test_missing_item_has_clear_error(self):
        with self.assertRaisesMessage(ValueError, "Book with ID 999 was not found"):
            get_item(GetItemQuery(entity="book", id=999))


class BookSummaryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asimov = Author.objects.create(first_name="Isaac", last_name="Asimov")
        cls.lem = Author.objects.create(first_name="Stanislaw", last_name="Lem")
        cls.fiction = Genre.objects.create(name="Science Fiction")
        cls.classics = Genre.objects.create(name="Classics")
        cls.foundation = Series.objects.create(title="Foundation")

        foundation = Book.objects.create(
            title="Foundation",
            series=cls.foundation,
            is_read=True,
        )
        foundation.authors.add(cls.asimov)
        foundation.genres.add(cls.fiction, cls.classics)
        AudioFile.objects.create(book=foundation, file="tests/foundation.mp3")

        solaris = Book.objects.create(title="Solaris", is_read=False)
        solaris.authors.add(cls.lem)
        solaris.genres.add(cls.fiction, cls.classics)

        collaboration = Book.objects.create(title="Shared Worlds", is_read=False)
        collaboration.authors.add(cls.asimov, cls.lem)
        collaboration.genres.add(cls.fiction)

    def test_groups_filtered_books_by_genre(self):
        result = summarize_books(
            BookSummaryQuery(
                group_by="genre",
                filters=BookSummaryFilters(author_ids=[self.asimov.id]),
            )
        )

        self.assertEqual(result.total_books, 2)
        self.assertEqual(
            {group.value: group.count for group in result.groups},
            {"Classics": 1, "Science Fiction": 2},
        )

    def test_groups_books_by_audio_availability(self):
        result = summarize_books(BookSummaryQuery(group_by="has_audio"))

        self.assertEqual(result.total_books, 3)
        self.assertEqual(
            {group.value: group.count for group in result.groups},
            {True: 1, False: 2},
        )

    def test_groups_books_by_series_including_missing_series(self):
        result = summarize_books(BookSummaryQuery(group_by="series"))

        self.assertEqual(result.total_books, 3)
        self.assertEqual(
            {group.value: group.count for group in result.groups},
            {"Foundation": 1, "No series": 2},
        )

    def test_summary_respects_boolean_filter(self):
        result = summarize_books(
            BookSummaryQuery(
                group_by="author",
                filters=BookSummaryFilters(is_read=False),
            )
        )

        self.assertEqual(result.total_books, 2)
        self.assertEqual(
            {group.value: group.count for group in result.groups},
            {"Isaac Asimov": 1, "Stanislaw Lem": 2},
        )


class ItemSuggestionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name="Айзек", last_name="Азимов")
        cls.genre = Genre.objects.create(name="Научная фантастика")
        cls.series = Series.objects.create(title="Всё о муми-троллях")
        cls.book = Book.objects.create(title="Основание")

    def test_suggests_author_for_typo(self):
        result = suggest_items(
            ItemSuggestionQuery(entity="author", text="Азимав")
        )

        self.assertEqual(result.suggestions[0].id, self.author.id)
        self.assertGreaterEqual(result.suggestions[0].score, 60)

    def test_suggests_genre_for_typo(self):
        result = suggest_items(
            ItemSuggestionQuery(entity="genre", text="фантастка")
        )

        self.assertEqual(result.suggestions[0].id, self.genre.id)

    def test_suggests_series_with_yo_normalization(self):
        result = suggest_items(
            ItemSuggestionQuery(entity="series", text="все о муми тролях")
        )

        self.assertEqual(result.suggestions[0].id, self.series.id)

    def test_suggests_book_and_respects_minimum_score(self):
        match = suggest_items(ItemSuggestionQuery(entity="book", text="Основаниие"))
        no_match = suggest_items(
            ItemSuggestionQuery(entity="book", text="неизвестное", min_score=95)
        )

        self.assertEqual(match.suggestions[0].id, self.book.id)
        self.assertEqual(no_match.suggestions, [])
