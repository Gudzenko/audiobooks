import os
import sqlite3
import time
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, TransactionTestCase, override_settings

from ..models import Author, Book, Genre, Series


class SeedTestDataCommandTests(TestCase):
    def test_command_is_idempotent_and_creates_local_admin(self):
        call_command("seed_test_data", verbosity=0)
        first_counts = self._catalog_counts()

        call_command("seed_test_data", verbosity=0)

        self.assertEqual(self._catalog_counts(), first_counts)
        self.assertEqual(first_counts, (4, 6, 4, 3))
        admin = get_user_model().objects.get(email="admin@example.com")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("admin"))

    @staticmethod
    def _catalog_counts():
        return (
            Author.objects.count(),
            Book.objects.count(),
            Genre.objects.count(),
            Series.objects.count(),
        )


class BackupDatabaseCommandTests(TransactionTestCase):
    def test_command_creates_valid_sqlite_backup(self):
        Author.objects.create(first_name="Backup", last_name="Author")

        with TemporaryDirectory() as directory:
            call_command("backup_database", output_dir=Path(directory), verbosity=0)
            backups = list(Path(directory).glob("db-*.sqlite3"))

            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as backup:
                self.assertEqual(
                    backup.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    backup.execute("SELECT COUNT(*) FROM store_author").fetchone()[0],
                    1,
                )


class CleanupUploadTempCommandTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.media_root = Path(self.media_directory.name)
        self.upload_temp = self.media_root / ".upload_tmp"
        self.upload_temp.mkdir()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_root,
            FILE_UPLOAD_TEMP_DIR=self.upload_temp,
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.media_directory.cleanup()

    def test_removes_only_files_older_than_default_age(self):
        old_file = self._create_file("old.upload", b"old", age_hours=25)
        fresh_file = self._create_file("fresh.upload", b"fresh", age_hours=23)
        output = StringIO()

        call_command("cleanup_upload_temp", stdout=output)

        self.assertFalse(old_file.exists())
        self.assertTrue(fresh_file.exists())
        self.assertIn("Removed 1 stale upload file(s), 3 byte(s).", output.getvalue())

    def test_dry_run_reports_without_deleting(self):
        old_file = self._create_file("old.upload", b"content", age_hours=48)
        output = StringIO()

        call_command("cleanup_upload_temp", dry_run=True, stdout=output)

        self.assertTrue(old_file.exists())
        self.assertIn(
            "Would remove 1 stale upload file(s), 7 byte(s).",
            output.getvalue(),
        )

    def test_custom_age_is_respected_for_nested_files(self):
        nested_directory = self.upload_temp / "nested"
        nested_directory.mkdir()
        stale_file = self._create_file(
            "nested/stale.upload",
            b"stale",
            age_hours=3,
        )

        call_command("cleanup_upload_temp", older_than_hours=2, verbosity=0)

        self.assertFalse(stale_file.exists())
        self.assertTrue(nested_directory.exists())

    def test_rejects_temp_directory_outside_media_root(self):
        with TemporaryDirectory() as outside_directory:
            with override_settings(FILE_UPLOAD_TEMP_DIR=outside_directory):
                with self.assertRaisesMessage(
                    CommandError,
                    "must be a dedicated directory inside MEDIA_ROOT",
                ):
                    call_command("cleanup_upload_temp", verbosity=0)

    def test_rejects_media_root_itself(self):
        with override_settings(FILE_UPLOAD_TEMP_DIR=self.media_root):
            with self.assertRaisesMessage(
                CommandError,
                "must be a dedicated directory inside MEDIA_ROOT",
            ):
                call_command("cleanup_upload_temp", verbosity=0)

    def test_rejects_missing_temp_configuration(self):
        with override_settings(FILE_UPLOAD_TEMP_DIR=None):
            with self.assertRaisesMessage(CommandError, "is not configured"):
                call_command("cleanup_upload_temp", verbosity=0)

    def test_rejects_non_positive_age(self):
        with self.assertRaisesMessage(CommandError, "must be greater than zero"):
            call_command(
                "cleanup_upload_temp",
                older_than_hours=0,
                verbosity=0,
            )

    def _create_file(self, relative_path, content, age_hours):
        path = self.upload_temp / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = time.time() - age_hours * 60 * 60
        os.utime(path, (timestamp, timestamp))
        return path
