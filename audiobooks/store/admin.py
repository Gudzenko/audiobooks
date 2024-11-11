from django.contrib import admin
from .models import Genre, Author, Series, Book, AudioFile
from .utils import get_image_preview


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'image_preview')
    search_fields = ('name',)

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'slug', 'image_preview')
    search_fields = ('last_name', 'first_name')

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'image_preview')
    search_fields = ('title',)

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'series', 'is_read', 'image_preview', 'audio_file_count')
    search_fields = ('title',)
    filter_horizontal = ('authors', 'genres')
    list_filter = ('is_read',)

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'

    def audio_file_count(self, obj):
        return obj.audio_files.count()

    audio_file_count.short_description = 'Audio Files'

    class Media:
        css = {
            'all': ('store/css/admin_styles.css',)
        }


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ('book', 'file', 'created_at')
    search_fields = ('book__title',)
    list_filter = ('book', 'created_at')
