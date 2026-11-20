import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import Author, Book, Genre, Series


class Command(BaseCommand):
    help = "Create an idempotent local development catalog and administrator"

    @transaction.atomic
    def handle(self, *args, **options):
        self._create_admin()

        fiction = self._genre("Science Fiction")
        classics = self._genre("Classics")
        mystery = self._genre("Mystery")
        fantasy = self._genre("Fantasy")

        foundation = self._series("Foundation")
        earthsea = self._series("Earthsea")
        poirot = self._series("Hercule Poirot")

        asimov = self._author("Isaac", "Asimov")
        lem = self._author("Stanislaw", "Lem")
        le_guin = self._author("Ursula", "Le Guin")
        christie = self._author("Agatha", "Christie")

        self._book("Foundation", [asimov], [fiction, classics], foundation, True)
        self._book("Foundation and Empire", [asimov], [fiction], foundation, False)
        self._book("Solaris", [lem], [fiction, classics], None, True)
        self._book("The Cyberiad", [lem], [fiction], None, False)
        self._book("A Wizard of Earthsea", [le_guin], [fantasy, classics], earthsea, False)
        self._book("Murder on the Orient Express", [christie], [mystery, classics], poirot, True)

        self.stdout.write(self.style.SUCCESS("Local test catalog is ready"))

    def _create_admin(self):
        email = os.environ.get("TEST_ADMIN_EMAIL", "admin@example.com")
        username = os.environ.get("TEST_ADMIN_USERNAME", "admin")
        password = os.environ.get("TEST_ADMIN_PASSWORD", "admin")
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
    def _author(first_name, last_name):
        author, _ = Author.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
        )
        return author

    @staticmethod
    def _genre(name):
        genre, _ = Genre.objects.get_or_create(name=name)
        return genre

    @staticmethod
    def _series(title):
        series, _ = Series.objects.get_or_create(title=title)
        return series

    @staticmethod
    def _book(title, authors, genres, series, is_read):
        book = Book.objects.filter(title=title, series=series).first()
        if book is None:
            book = Book.objects.create(title=title, series=series, is_read=is_read)
        book.authors.set(authors)
        book.genres.set(genres)
        if book.is_read != is_read:
            book.is_read = is_read
            book.save(update_fields=["is_read"])
        return book
