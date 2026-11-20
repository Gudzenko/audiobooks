from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import AudioFile, Author, Book, Genre, Series


class StoreSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="reader@example.com",
            username="reader",
            password="test-password",
        )
        cls.author = Author.objects.create(first_name="Test", last_name="Author")
        cls.genre = Genre.objects.create(name="Test Genre")
        cls.series = Series.objects.create(title="Test Series")
        cls.book = Book.objects.create(
            title="Test Book",
            series=cls.series,
            is_read=False,
        )
        cls.book.authors.add(cls.author)
        cls.book.genres.add(cls.genre)

    def test_home_is_available(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

    def test_catalog_lists_require_login(self):
        for url_name in ("book_list", "author_list", "genre_list", "series_list"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_authenticated_catalog_pages_are_available(self):
        self.client.force_login(self.user)
        urls = (
            reverse("book_list"),
            reverse("author_list"),
            reverse("genre_list"),
            reverse("series_list"),
            reverse("book_detail", kwargs={"slug": self.book.slug}),
            reverse("author_detail", kwargs={"slug": self.author.slug}),
            reverse("genre_detail", kwargs={"slug": self.genre.slug}),
            reverse("series_detail", kwargs={"slug": self.series.slug}),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_book_relations_are_preserved(self):
        self.assertEqual(list(self.book.authors.all()), [self.author])
        self.assertEqual(list(self.book.genres.all()), [self.genre])
        self.assertEqual(self.book.series, self.series)
        self.assertFalse(self.book.is_read)

    def test_book_slug_contains_catalog_information(self):
        self.assertIn(self.author.slug, self.book.slug)
        self.assertIn(self.series.slug, self.book.slug)
        self.assertTrue(self.book.slug.endswith("test_book"))


class AudioFileAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="listener@example.com",
            username="listener",
            password="test-password",
        )
        cls.book = Book.objects.create(title="Audio Book")
        cls.audio = AudioFile.objects.create(
            book=cls.book,
            file="audio/author/series/book/chapter.mp3",
        )

    def test_audio_requires_login(self):
        response = self.client.get(reverse("audio_file", kwargs={"pk": self.audio.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    @override_settings(DEBUG=False)
    def test_authenticated_audio_is_delegated_to_nginx(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("audio_file", kwargs={"pk": self.audio.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["X-Accel-Redirect"],
            "/_protected_audio/author/series/book/chapter.mp3",
        )

    def test_unknown_audio_returns_not_found(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("audio_file", kwargs={"pk": 999999}))

        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=True)
    def test_direct_audio_path_is_blocked_in_development(self):
        response = self.client.get("/media/audio/author/series/book/chapter.mp3")

        self.assertEqual(response.status_code, 404)

    def test_book_page_does_not_preload_audio_files(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("book_detail", kwargs={"slug": self.book.slug})
        )

        self.assertContains(response, '<audio controls preload="none"', html=False)


class CatalogFilteringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="catalog@example.com",
            username="catalog",
            password="test-password",
        )
        cls.author = Author.objects.create(first_name="Isaac", last_name="Asimov")
        cls.other_author = Author.objects.create(first_name="Agatha", last_name="Christie")
        cls.genre = Genre.objects.create(name="Science Fiction")
        cls.other_genre = Genre.objects.create(name="Mystery")

        cls.unread_book = Book.objects.create(title="Foundation", is_read=False)
        cls.unread_book.authors.add(cls.author)
        cls.unread_book.genres.add(cls.genre)

        cls.read_book = Book.objects.create(title="Murder on the Orient Express", is_read=True)
        cls.read_book.authors.add(cls.other_author)
        cls.read_book.genres.add(cls.other_genre)

    def setUp(self):
        self.client.force_login(self.user)

    def test_book_list_filters_by_title_query(self):
        response = self.client.get(reverse("book_list"), {"query": "foundation"})

        self.assertContains(response, self.unread_book.title)
        self.assertNotContains(response, self.read_book.title)

    def test_book_list_filters_unread_books(self):
        response = self.client.get(reverse("book_list"), {"unread_only": "1"})

        self.assertContains(response, self.unread_book.title)
        self.assertNotContains(response, self.read_book.title)

    def test_author_list_filters_by_full_name(self):
        response = self.client.get(reverse("author_list"), {"query": "asimov"})

        self.assertContains(response, "Isaac Asimov")
        self.assertNotContains(response, "Agatha Christie")

    def test_genre_detail_filters_its_books_by_title(self):
        response = self.client.get(
            reverse("genre_detail", kwargs={"slug": self.genre.slug}),
            {"query": "foundation"},
        )

        self.assertContains(response, self.unread_book.title)
        self.assertNotContains(response, self.read_book.title)


class CatalogPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.regular_user = get_user_model().objects.create_user(
            email="regular@example.com",
            username="regular",
            password="test-password",
        )
        cls.admin = get_user_model().objects.create_superuser(
            email="admin-tests@example.com",
            username="admin-tests",
            password="test-password",
        )

    def test_regular_user_cannot_open_create_forms(self):
        self.client.force_login(self.regular_user)

        for url_name in ("book_add", "author_add", "genre_add", "series_add"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 403)

    def test_superuser_can_open_create_forms(self):
        self.client.force_login(self.admin)

        for url_name in ("book_add", "author_add", "genre_add", "series_add"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_catalog_export_api_requires_superuser(self):
        url = reverse("api_authors_list")

        anonymous_response = self.client.get(url)
        self.client.force_login(self.regular_user)
        regular_response = self.client.get(url)

        self.assertIn(anonymous_response.status_code, (401, 403))
        self.assertEqual(regular_response.status_code, 403)


class CatalogAutocompleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name="Regex", last_name="Author")
        cls.genre = Genre.objects.create(name="Science Fiction")
        cls.series = Series.objects.create(title="Test Series")

    def test_partial_queries_return_matching_items(self):
        cases = (
            ("author-autocomplete", "Regex", self.author.pk),
            ("genre-autocomplete", "Science", self.genre.pk),
            ("series-autocomplete", "Test", self.series.pk),
        )
        for url_name, query, expected_id in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    str(expected_id),
                    [item["id"] for item in response.json()["results"]],
                )

    def test_regex_characters_are_treated_as_plain_text(self):
        for url_name in (
            "author-autocomplete",
            "genre-autocomplete",
            "series-autocomplete",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), {"q": "[("})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["results"], [])
