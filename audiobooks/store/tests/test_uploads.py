import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import AudioFile, Author, Book


class SequentialAudioUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.regular_user = get_user_model().objects.create_user(
            email="audio-reader@example.com",
            username="audio-reader",
            password="test-password",
        )
        cls.admin = get_user_model().objects.create_superuser(
            email="audio-admin@example.com",
            username="audio-admin",
            password="test-password",
        )
        cls.author = Author.objects.create(first_name="Audio", last_name="Author")
        cls.book = Book.objects.create(title="Existing Audio Book")
        cls.book.authors.add(cls.author)

    def setUp(self):
        self.temporary_media = TemporaryDirectory()
        self.upload_temp = Path(self.temporary_media.name) / ".upload_tmp"
        self.upload_temp.mkdir()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temporary_media.name,
            FILE_UPLOAD_TEMP_DIR=self.upload_temp,
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_media.cleanup()

    def test_metadata_request_creates_book_without_audio_and_returns_urls(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("book_add"),
            {
                "title": "Sequential Book",
                "authors": [self.author.pk],
                "genres": [],
                "series": "",
                "sequential_audio_upload": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        book = Book.objects.get(title="Sequential Book")
        self.assertEqual(book.audio_files.count(), 0)
        self.assertEqual(
            response.json()["upload_url"],
            reverse("book_audio_upload", kwargs={"slug": book.slug}),
        )
        self.assertEqual(
            response.json()["recovery_url"],
            reverse("book_edit", kwargs={"slug": book.slug}),
        )
        self.assertEqual(
            response.json()["redirect_url"],
            reverse("book_detail", kwargs={"slug": book.slug}),
        )

    def test_complete_sequential_workflow_preserves_every_file(self):
        self.client.force_login(self.admin)
        metadata_response = self.client.post(
            reverse("book_add"),
            {
                "title": "Complete Upload Book",
                "authors": [self.author.pk],
                "genres": [],
                "series": "",
                "sequential_audio_upload": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        upload_url = metadata_response.json()["upload_url"]
        expected_files = {
            "chapter-01.mp3": b"first chapter",
            "chapter-02.mp3": b"second chapter",
            "chapter-03.mp3": b"third chapter",
        }

        for filename, content in expected_files.items():
            response = self.client.post(
                upload_url,
                {
                    "audio_file": SimpleUploadedFile(
                        filename,
                        content,
                        content_type="audio/mpeg",
                    )
                },
            )
            self.assertEqual(response.status_code, 201)

        book = Book.objects.get(title="Complete Upload Book")
        self.assertEqual(book.audio_files.count(), len(expected_files))
        for audio in book.audio_files.all():
            with audio.file.open("rb") as saved_file:
                self.assertEqual(
                    saved_file.read(),
                    expected_files[Path(audio.file.name).name],
                )

    def test_failed_next_file_does_not_remove_completed_uploads(self):
        self.client.force_login(self.admin)

        successful_response = self._upload("chapter-01.mp3", b"saved content")
        failed_response = self._upload("empty.mp3", b"")

        self.assertEqual(successful_response.status_code, 201)
        self.assertEqual(failed_response.status_code, 400)
        self.assertEqual(self.book.audio_files.count(), 1)
        with self.book.audio_files.get().file.open("rb") as saved_file:
            self.assertEqual(saved_file.read(), b"saved content")

    def test_superuser_can_upload_one_audio_file(self):
        self.client.force_login(self.admin)
        content = b"test audio content"

        response = self._upload("chapter-01.mp3", content)

        self.assertEqual(response.status_code, 201)
        audio = self.book.audio_files.get()
        self.assertEqual(response.json()["status"], "created")
        with audio.file.open("rb") as saved_file:
            self.assertEqual(saved_file.read(), content)

    def test_repeated_filename_is_idempotent(self):
        self.client.force_login(self.admin)

        first_response = self._upload("chapter one.mp3", b"first content")
        second_response = self._upload("chapter one.mp3", b"second content")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["status"], "already_exists")
        self.assertEqual(self.book.audio_files.count(), 1)
        with self.book.audio_files.get().file.open("rb") as saved_file:
            self.assertEqual(saved_file.read(), b"first content")

    def test_file_larger_than_memory_threshold_is_saved_and_temp_is_cleaned(self):
        self.client.force_login(self.admin)
        content = b"x" * (10 * 1024 * 1024 + 1)

        response = self._upload("large-chapter.mp3", content)

        self.assertEqual(response.status_code, 201)
        audio = self.book.audio_files.get()
        self.assertEqual(audio.file.size, len(content))
        self.assertEqual(list(self.upload_temp.iterdir()), [])

    def test_upload_requires_exactly_one_file(self):
        self.client.force_login(self.admin)
        url = reverse("book_audio_upload", kwargs={"slug": self.book.slug})

        missing_response = self.client.post(url)
        multiple_response = self.client.post(
            url,
            {
                "audio_file": [
                    SimpleUploadedFile("one.mp3", b"one", content_type="audio/mpeg"),
                    SimpleUploadedFile("two.mp3", b"two", content_type="audio/mpeg"),
                ]
            },
        )

        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(multiple_response.status_code, 400)
        self.assertEqual(self.book.audio_files.count(), 0)

    def test_empty_audio_file_is_rejected(self):
        self.client.force_login(self.admin)

        response = self._upload("empty.mp3", b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.book.audio_files.count(), 0)

    def test_audio_larger_than_storage_limit_is_rejected(self):
        self.client.force_login(self.admin)

        with override_settings(MAX_AUDIO_FILE_SIZE=2):
            response = self._upload("too-large.mp3", b"123")

        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.book.audio_files.count(), 0)

    def test_database_failure_removes_stored_sequential_upload(self):
        self.client.force_login(self.admin)

        def fail_after_file_is_stored(audio, *args, **kwargs):
            audio.file.save(audio.file.name, audio.file.file, save=False)
            raise OSError("simulated database failure")

        with patch.object(AudioFile, "save", fail_after_file_is_stored):
            response = self._upload("orphan.mp3", b"must be removed")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"error": "The audio file could not be saved."},
        )
        self.assertEqual(self.book.audio_files.count(), 0)
        remaining_files = [
            path
            for path in Path(self.temporary_media.name).rglob("*")
            if path.is_file()
        ]
        self.assertEqual(remaining_files, [])

    def test_unknown_book_is_not_created_implicitly(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("book_audio_upload", kwargs={"slug": "missing-book"}),
            {
                "audio_file": SimpleUploadedFile(
                    "chapter.mp3",
                    b"content",
                    content_type="audio/mpeg",
                )
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AudioFile.objects.count(), 0)

    def test_upload_requires_superuser(self):
        url = reverse("book_audio_upload", kwargs={"slug": self.book.slug})

        anonymous_response = self.client.post(url)
        self.client.force_login(self.regular_user)
        regular_response = self.client.post(url)

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertEqual(regular_response.status_code, 403)

    def test_edit_form_allows_recovery_upload(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("book_edit", kwargs={"slug": self.book.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="audio_files"')

    def test_edit_reports_audio_reconciliation_failure(self):
        self.client.force_login(self.admin)
        original_title = self.book.title

        with patch(
            "store.edit_views.reconcile_book_audio_paths",
            side_effect=OSError("storage failure"),
        ):
            response = self.client.post(
                reverse("book_edit", kwargs={"slug": self.book.slug}),
                {
                    "title": "Title that must be rolled back",
                    "authors": [self.author.pk],
                    "genres": [],
                    "series": "",
                    "sequential_audio_upload": "1",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Error processing audio files"})
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, original_title)

    def test_regular_multi_file_failure_removes_rolled_back_files(self):
        self.client.force_login(self.admin)
        real_save = AudioFile.save
        calls = 0

        def fail_after_second_file_is_stored(audio, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                audio.file.save(audio.file.name, audio.file.file, save=False)
                raise OSError("simulated database failure")
            return real_save(audio, *args, **kwargs)

        with patch.object(AudioFile, "save", fail_after_second_file_is_stored):
            response = self.client.post(
                reverse("book_add"),
                {
                    "title": "Rolled Back Upload",
                    "authors": [self.author.pk],
                    "genres": [],
                    "series": "",
                    "audio_files": [
                        SimpleUploadedFile("one.mp3", b"one"),
                        SimpleUploadedFile("two.mp3", b"two"),
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Book.objects.filter(title="Rolled Back Upload").exists())
        self.assertEqual(AudioFile.objects.count(), 0)
        remaining_files = [
            path
            for path in Path(self.temporary_media.name).rglob("*")
            if path.is_file()
        ]
        self.assertEqual(remaining_files, [])

    def test_create_failure_removes_newly_stored_cover(self):
        self.client.force_login(self.admin)
        real_save = Book.save
        failed_save_was_reached = False

        def fail_after_cover_is_stored(book, *args, **kwargs):
            nonlocal failed_save_was_reached
            if book.title == "Failed Cover Book":
                failed_save_was_reached = True
                book.image.save(book.image.name, book.image.file, save=False)
                raise OSError("simulated book save failure")
            return real_save(book, *args, **kwargs)

        with patch.object(Book, "save", fail_after_cover_is_stored):
            response = self.client.post(
                reverse("book_add"),
                {
                    "title": "Failed Cover Book",
                    "authors": [self.author.pk],
                    "genres": [],
                    "series": "",
                    "image": SimpleUploadedFile(
                        "cover.png",
                        base64.b64decode(
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                            "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                        ),
                        content_type="image/png",
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(failed_save_was_reached)
        self.assertFalse(Book.objects.filter(title="Failed Cover Book").exists())
        remaining_files = [
            path
            for path in Path(self.temporary_media.name).rglob("*")
            if path.is_file()
        ]
        self.assertEqual(remaining_files, [])

    def _upload(self, filename, content):
        return self.client.post(
            reverse("book_audio_upload", kwargs={"slug": self.book.slug}),
            {
                "audio_file": SimpleUploadedFile(
                    filename,
                    content,
                    content_type="audio/mpeg",
                )
            },
        )
