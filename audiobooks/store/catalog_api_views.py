import logging

from dal import autocomplete
from django.db.models import CharField, Value
from django.db.models.functions import Concat
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Author, Genre, Series
from .export_services import export_authors_to_csv, export_books_to_csv


logger = logging.getLogger(__name__)


class AuthorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Author.objects.all().order_by('last_name', 'first_name')
        if self.q and len(self.q) >= 2:
            queryset = queryset.annotate(
                full_name=Concat(
                    'first_name',
                    Value(' '),
                    'last_name',
                    output_field=CharField(),
                )
            ).filter(full_name__icontains=self.q)
        return queryset

    def get_result_label(self, item):
        return f"{item.first_name} {item.last_name}"


class GenreAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Genre.objects.all().order_by('name')
        return queryset.filter(name__icontains=self.q) if self.q else queryset

    def get_result_label(self, item):
        return item.name


class SeriesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Series.objects.all().order_by('title')
        return queryset.filter(title__icontains=self.q) if self.q else queryset

    def get_result_label(self, item):
        return item.title


class AuthorsListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        filepath, _, count, authors = export_authors_to_csv()
        logger.info("Authors list saved to %s", filepath)
        return Response(
            {'count': count, 'file': filepath, 'authors': authors},
            status=status.HTTP_200_OK,
        )


class BooksListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        filepath, _, count, books = export_books_to_csv()
        logger.info("Books list saved to %s", filepath)
        return Response(
            {'count': count, 'file': filepath, 'books': books},
            status=status.HTTP_200_OK,
        )
