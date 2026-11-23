import io
import os
import wave

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from store.models import AudioFile, Author, Book, Genre, Series


class Command(BaseCommand):
    help = "Create a small, idempotent catalog for production-like smoke tests"

    @transaction.atomic
    def handle(self, *args, **options):
        if os.environ.get("SMOKE_DATA_ENABLED") != "True":
            raise CommandError(
                "Set SMOKE_DATA_ENABLED=True to create the smoke-test catalog."
            )

        self._create_admin()
        fiction, _ = Genre.objects.get_or_create(name="Smoke Science Fiction")
        mystery, _ = Genre.objects.get_or_create(name="Smoke Mystery")
        series, _ = Series.objects.get_or_create(title="Smoke Series")
        author, _ = Author.objects.get_or_create(
            first_name="Smoke",
            last_name="Author",
        )

        first = self._book(
            "Smoke Book One",
            author=author,
            genres=[fiction],
            series=series,
            is_read=True,
        )
        second = self._book(
            "Smoke Book Two",
            author=author,
            genres=[fiction, mystery],
            series=series,
            is_read=False,
        )
        self._book(
            "Smoke Book Without Audio",
            author=author,
            genres=[mystery],
            series=None,
            is_read=False,
        )

        self._audio(first, "sample-one.wav")
        self._audio(second, "sample-two.wav")
        self.stdout.write(self.style.SUCCESS("Smoke-test catalog is ready"))

    @staticmethod
    def _create_admin():
        email = os.environ.get("TEST_ADMIN_EMAIL", "smoke@example.com")
        username = os.environ.get("TEST_ADMIN_USERNAME", "smoke")
        password = os.environ.get("TEST_ADMIN_PASSWORD", "smoke")
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])

    @staticmethod
    def _book(title, *, author, genres, series, is_read):
        book = Book.objects.filter(title=title, series=series).first()
        if book is None:
            book = Book.objects.create(
                title=title,
                series=series,
                is_read=is_read,
            )
        book.authors.set([author])
        book.genres.set(genres)
        if book.is_read != is_read:
            book.is_read = is_read
            book.save(update_fields=["is_read"])
        return book

    @staticmethod
    def _audio(book, filename):
        if book.audio_files.filter(file__endswith=f"/{filename}").exists():
            return
        AudioFile.objects.create(
            book=book,
            file=ContentFile(_silent_wav(), name=filename),
        )


def _silent_wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 800)
    return output.getvalue()
