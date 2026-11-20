import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Remove stale files from the configured upload temporary directory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-hours",
            type=float,
            default=24,
            help="Remove files older than this many hours (default: 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report stale files without deleting them.",
        )

    def handle(self, *args, **options):
        older_than_hours = options["older_than_hours"]
        if older_than_hours <= 0:
            raise CommandError("--older-than-hours must be greater than zero.")

        temp_dir = self._validated_temp_directory()
        if not temp_dir.exists():
            self.stdout.write(f"Temporary upload directory does not exist: {temp_dir}")
            return
        if not temp_dir.is_dir():
            raise CommandError(f"Temporary upload path is not a directory: {temp_dir}")

        cutoff = time.time() - older_than_hours * 60 * 60
        stale_files = []
        total_size = 0
        for path in temp_dir.rglob("*"):
            if not path.is_file() and not path.is_symlink():
                continue
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue
            if stat.st_mtime >= cutoff:
                continue
            stale_files.append(path)
            total_size += stat.st_size

        if not options["dry_run"]:
            for path in stale_files:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue

        action = "Would remove" if options["dry_run"] else "Removed"
        self.stdout.write(
            f"{action} {len(stale_files)} stale upload file(s), "
            f"{total_size} byte(s)."
        )

    @staticmethod
    def _validated_temp_directory():
        configured_temp_dir = settings.FILE_UPLOAD_TEMP_DIR
        if not configured_temp_dir:
            raise CommandError("FILE_UPLOAD_TEMP_DIR is not configured.")

        temp_dir = Path(configured_temp_dir).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if temp_dir == media_root or not temp_dir.is_relative_to(media_root):
            raise CommandError(
                "FILE_UPLOAD_TEMP_DIR must be a dedicated directory inside MEDIA_ROOT."
            )
        return temp_dir
