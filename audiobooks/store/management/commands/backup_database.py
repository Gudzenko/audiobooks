import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Create and verify a consistent backup of the SQLite database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=Path,
            default=Path(settings.BASE_DIR) / "backups",
            help="Directory in which the backup file will be created",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("backup_database currently supports SQLite only")

        output_dir = options["output_dir"].resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = output_dir / f"db-{timestamp}.sqlite3"

        connection.ensure_connection()
        source = connection.connection
        try:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)
                integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.Error as error:
            backup_path.unlink(missing_ok=True)
            raise CommandError(f"Database backup failed: {error}") from error

        if integrity != "ok":
            backup_path.unlink(missing_ok=True)
            raise CommandError(f"Backup integrity check failed: {integrity}")

        self.stdout.write(self.style.SUCCESS(str(backup_path)))
