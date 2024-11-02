from django.contrib import admin
from .models import Genre, Author, Series, Book


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'slug')
    search_fields = ('last_name', 'first_name')


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug')
    search_fields = ('title',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'series', 'is_read')
    search_fields = ('title',)
    filter_horizontal = ('authors', 'genres')
    list_filter = ('is_read',)
