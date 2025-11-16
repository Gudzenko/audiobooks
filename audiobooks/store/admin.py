from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from .models import Genre, Author, Series, Book, AudioFile
from .utils import get_image_preview, export_authors_to_csv, export_books_to_csv


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
    actions = ['export_authors_to_file']

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'

    def export_authors_to_file(self, request, queryset):
        filepath, filename, count, authors_data = export_authors_to_csv()
        
        self.message_user(
            request,
            format_html(
                _('Successfully exported {} authors to file: <a href="/{}" target="_blank">{}</a>'),
                count,
                filepath,
                filename
            )
        )
    
    export_authors_to_file.short_description = _('Export all authors to CSV file')

    def changelist_view(self, request, extra_context=None):
        if 'action' in request.POST and request.POST['action'] == 'export_authors_to_file':
            if not request.POST.getlist('_selected_action'):
                self.export_authors_to_file(request, Author.objects.none())
                return HttpResponseRedirect(request.get_full_path())
        
        extra_context = extra_context or {}
        extra_context['show_export_button'] = True
        return super().changelist_view(request, extra_context=extra_context)


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
    actions = ['export_books_to_file']

    def image_preview(self, obj):
        return get_image_preview(obj, 'image')
    image_preview.short_description = 'Image'

    def audio_file_count(self, obj):
        return obj.audio_files.count()

    audio_file_count.short_description = 'Audio Files'

    def export_books_to_file(self, request, queryset):
        filepath, filename, count, books_data = export_books_to_csv()
        
        self.message_user(
            request,
            format_html(
                _('Successfully exported {} books to file: <a href="/{}" target="_blank">{}</a>'),
                count,
                filepath,
                filename
            )
        )
    
    export_books_to_file.short_description = _('Export all books to CSV file')

    def changelist_view(self, request, extra_context=None):
        if 'action' in request.POST and request.POST['action'] == 'export_books_to_file':
            if not request.POST.getlist('_selected_action'):
                self.export_books_to_file(request, Book.objects.none())
                return HttpResponseRedirect(request.get_full_path())
        
        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        css = {
            'all': ('store/css/admin_styles.css',)
        }


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ('book', 'file', 'created_at')
    search_fields = ('book__title',)
    list_filter = ('book', 'created_at')
