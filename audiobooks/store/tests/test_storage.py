from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from ..audio_services import reconcile_book_audio_paths
from ..models import AudioFile, Author, Book


class BookDeletionTests(TestCase):
    def setUp(self):
        self.temporary_media = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temporary_media.name)
        self.settings_override.enable()
        self.admin = get_user_model().objects.create_superuser(
            email="delete-admin@example.com",
            username="delete-admin",
            password="test-password",
        )
        self.book = Book.objects.create(
            title="Delete Book",
            image=SimpleUploadedFile("cover.jpg", b"cover"),
        )
        self.audio = AudioFile.objects.create(
            book=self.book,
            file=SimpleUploadedFile("chapter.mp3", b"audio"),
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_media.cleanup()

    def test_deleting_book_removes_database_records_and_files(self):
        book_id = self.book.pk
        audio_id = self.audio.pk
        image_path = Path(self.book.image.path)
        audio_path = Path(self.audio.file.path)
        self.client.force_login(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("book_delete", kwargs={"slug": self.book.slug})
            )

        self.assertRedirects(response, reverse("book_list"))
        self.assertFalse(Book.objects.filter(pk=book_id).exists())
        self.assertFalse(AudioFile.objects.filter(pk=audio_id).exists())
        self.assertFalse(image_path.exists())
        self.assertFalse(audio_path.exists())

    def test_clearing_image_updates_database_and_deletes_file_after_save(self):
        image_path = Path(self.book.image.path)
        self.client.force_login(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("book_edit", kwargs={"slug": self.book.slug}),
                {
                    "title": self.book.title,
                    "authors": [],
                    "genres": [],
                    "series": "",
                    "clear_image": "true",
                },
            )

        self.assertRedirects(response, reverse("book_list"))
        self.book.refresh_from_db()
        self.assertFalse(self.book.image)
        self.assertFalse(image_path.exists())


class AudioFileStorageTests(TestCase):
    def setUp(self):
        self.temporary_media = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temporary_media.name)
        self.settings_override.enable()
        self.book = Book.objects.create(title="Storage Book")
        self.audio = AudioFile.objects.create(
            book=self.book,
            file=SimpleUploadedFile("old.mp3", b"old"),
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_media.cleanup()

    def test_direct_delete_removes_file_once(self):
        audio_id = self.audio.pk
        path = Path(self.audio.file.path)

        with self.captureOnCommitCallbacks(execute=True):
            self.audio.delete()

        self.assertFalse(AudioFile.objects.filter(pk=audio_id).exists())
        self.assertFalse(path.exists())

    def test_rolled_back_delete_keeps_record_and_file(self):
        audio_id = self.audio.pk
        path = Path(self.audio.file.path)

        with self.assertRaisesRegex(RuntimeError, "rollback deletion"):
            with transaction.atomic():
                self.audio.delete()
                raise RuntimeError("rollback deletion")

        self.assertTrue(AudioFile.objects.filter(pk=audio_id).exists())
        self.assertTrue(path.exists())

    def test_file_delete_failure_does_not_change_committed_database_result(self):
        audio_id = self.audio.pk

        with patch.object(
            self.audio.file.storage,
            "delete",
            side_effect=OSError("storage unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                self.audio.delete()

        self.assertFalse(AudioFile.objects.filter(pk=audio_id).exists())

    def test_replacing_file_removes_old_file_after_successful_save(self):
        old_path = Path(self.audio.file.path)
        self.audio.file = SimpleUploadedFile("new.mp3", b"new")

        with self.captureOnCommitCallbacks(execute=True):
            self.audio.save()

        self.assertFalse(old_path.exists())
        self.assertEqual(Path(self.audio.file.path).read_bytes(), b"new")

    def test_failed_replacement_does_not_remove_old_file(self):
        old_path = Path(self.audio.file.path)
        self.audio.file = SimpleUploadedFile("new.mp3", b"new")

        with patch("django.db.models.base.Model.save", side_effect=OSError("db failure")):
            with self.assertRaisesRegex(OSError, "db failure"):
                self.audio.save()

        self.assertTrue(old_path.exists())
        self.assertEqual(old_path.read_bytes(), b"old")


class AudioFileMoveTests(TestCase):
    def setUp(self):
        self.temporary_media = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temporary_media.name,
        )
        self.settings_override.enable()
        self.author = Author.objects.create(first_name="Move", last_name="Author")
        self.book = Book.objects.create(title="Original Book")
        self.book.authors.add(self.author)
        self.audio_files = [
            AudioFile.objects.create(
                book=self.book,
                file=SimpleUploadedFile(filename, content),
            )
            for filename, content in (
                ("chapter-01.mp3", b"first"),
                ("chapter-02.mp3", b"second"),
            )
        ]

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_media.cleanup()

    def test_slug_change_moves_files_and_updates_database(self):
        old_paths = self._rename_book()

        reconcile_book_audio_paths(self.book)

        for audio, old_path, expected_content in zip(
            self.audio_files,
            old_paths,
            (b"first", b"second"),
        ):
            audio.refresh_from_db()
            self.assertIn(self.book.slug, audio.file.name)
            self.assertFalse(old_path.exists())
            self.assertEqual(Path(audio.file.path).read_bytes(), expected_content)

    def test_partial_move_failure_restores_files_and_database_paths(self):
        old_paths = self._rename_book()
        old_names = [audio.file.name for audio in self.audio_files]
        real_move = __import__("shutil").move
        calls = 0

        def fail_on_second_move(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated storage failure")
            return real_move(source, destination)

        with patch("store.audio_services.shutil.move", side_effect=fail_on_second_move):
            with self.assertRaisesRegex(OSError, "simulated storage failure"):
                reconcile_book_audio_paths(self.book)

        for audio, old_name, old_path in zip(
            self.audio_files,
            old_names,
            old_paths,
        ):
            audio.refresh_from_db()
            self.assertEqual(audio.file.name, old_name)
            self.assertTrue(old_path.exists())

        reconcile_book_audio_paths(self.book)
        for audio, old_path in zip(self.audio_files, old_paths):
            audio.refresh_from_db()
            self.assertIn(self.book.slug, audio.file.name)
            self.assertFalse(old_path.exists())

    def test_existing_destination_prevents_any_move(self):
        old_paths = self._rename_book()
        first_audio = self.audio_files[0]
        destination = (
            Path(self.temporary_media.name)
            / "audio"
            / self.author.slug
            / "no_series"
            / self.book.slug
            / Path(first_audio.file.name).name
        )
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"existing")

        with self.assertRaises(FileExistsError):
            reconcile_book_audio_paths(self.book)

        self.assertEqual(destination.read_bytes(), b"existing")
        self.assertTrue(all(path.exists() for path in old_paths))

    def test_database_update_failure_restores_moved_file(self):
        old_paths = self._rename_book()
        old_names = [audio.file.name for audio in self.audio_files]

        with patch(
            "django.db.models.query.QuerySet.update",
            side_effect=OSError("database update failure"),
        ):
            with self.assertRaisesRegex(OSError, "database update failure"):
                reconcile_book_audio_paths(self.book)

        for audio, old_name, old_path in zip(
            self.audio_files,
            old_names,
            old_paths,
        ):
            audio.refresh_from_db()
            self.assertEqual(audio.file.name, old_name)
            self.assertTrue(old_path.exists())

    def _rename_book(self):
        old_paths = [Path(audio.file.path) for audio in self.audio_files]
        self.book.title = "Renamed Book"
        self.book.save()
        return old_paths
