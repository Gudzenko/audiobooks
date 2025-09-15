import logging
import os
import zipfile
import json

from django.views.generic.edit import FormView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.contrib import messages
from django.templatetags.static import static
from django.views.generic import TemplateView, DetailView
from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from .forms import BookForm, AuthorForm, SeriesForm, GenreForm
from .models import Book, Author, Series, Genre, AudioFile
from django.contrib.messages import get_messages


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Views')


class HomeView(TemplateView):
    template_name = 'store/home.html'


class PaginatedListView(LoginRequiredMixin, TemplateView):
    template_name = 'store/tile_list.html'
    login_url = 'login'
    paginate_by = 18
    model = None
    image = ''
    title = ''
    title_url = ''
    add_item_name = ''
    show_unread_filter = False

    def get_items(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('query', '')
        unread_only = self.request.GET.get('unread_only', '') == '1' if self.show_unread_filter else False
        
        item_list = self.get_items()
        if query:
            item_list = [item for item in item_list if query.lower() in item['label'].lower()]
        
        if unread_only and hasattr(self, 'filter_unread'):
            item_list = self.filter_unread(item_list)
            
        paginator = Paginator(item_list, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['title'] = self.title
        context['title_url'] = self.title_url
        context['page_obj'] = page_obj
        context['query'] = query
        context['unread_only'] = unread_only
        context['show_unread_filter'] = self.show_unread_filter
        context['add_item_name'] = self.add_item_name
        return context


class BookListView(PaginatedListView):
    title = _('Books')
    title_url = 'book'
    image = static('store/images/default_book.png')
    add_item_name = _('Add new book')
    show_unread_filter = True

    def get_items(self):
        return [
            {
                'image': book.image.url if book.image else self.image,
                'label': book.title,
                'slug': book.slug,
                'book_obj': book,
            }
            for book in Book.objects.all()
        ]
    
    def filter_unread(self, item_list):
        return [item for item in item_list if not item['book_obj'].is_read]


class AuthorListView(PaginatedListView):
    title = _('Authors')
    title_url = 'author'
    image = static('store/images/default_author.png')
    add_item_name = _('Add new author')

    def get_items(self):
        return [
            {
                'image': author.image.url if author.image else self.image,
                'label': f"{author.first_name} {author.last_name}",
                'slug': author.slug,
            }
            for author in Author.objects.all()
        ]


class SeriesListView(PaginatedListView):
    title = _('Series')
    title_url = 'series'
    image = static('store/images/default_series.png')
    add_item_name = _('Add new series')

    def get_items(self):
        return [
            {
                'image': series.image.url if series.image else self.image,
                'label': series.title,
                'slug': series.slug,
            }
            for series in Series.objects.all()
        ]


class GenreListView(PaginatedListView):
    title = _('Genres')
    title_url = 'genre'
    image = static('store/images/default_genre.png')
    add_item_name = _('Add new genre')

    def get_items(self):
        return [
            {
                'image': genre.image.url if genre.image else self.image,
                'label': genre.name,
                'slug': genre.slug,
            }
            for genre in Genre.objects.all()
        ]


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = 'store/book_detail.html'
    context_object_name = 'book'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['authors'] = self.object.authors.all()
        context['series'] = self.object.series
        context['genres'] = self.object.genres.all()
        context['audio_files'] = self.object.audio_files.all().order_by('file')
        return context


class AuthorDetailView(LoginRequiredMixin, DetailView):
    model = Author
    template_name = 'store/author_detail.html'
    context_object_name = 'author'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = Book.objects.filter(authors=self.object)
        return context


class SeriesDetailView(LoginRequiredMixin, DetailView):
    model = Series
    template_name = 'store/series_detail.html'
    context_object_name = 'series'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = Book.objects.filter(series=self.object)
        return context


class GenreDetailView(LoginRequiredMixin, DetailView):
    model = Genre
    template_name = 'store/genre_detail.html'
    context_object_name = 'genre'
    login_url = 'login'
    paginate_by = 18

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('query', '')
        books = Book.objects.filter(genres=self.object)
        book_list = books
        if query:
            book_list = [book for book in books if query.lower() in book.title.lower()]

        paginator = Paginator(book_list, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['books'] = page_obj
        context['page_obj'] = page_obj
        context['query'] = query
        return context


class DownloadAllAudioView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, slug, *args, **kwargs):
        book = get_object_or_404(Book, slug=slug)
        audio_files = book.audio_files.all()

        response = HttpResponse(content_type='application/zip')
        zip_filename = f"{slug}.zip"
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

        with zipfile.ZipFile(response, 'w') as zip_file:
            for audio in audio_files:
                file_path = audio.file.path
                file_name = os.path.basename(file_path)
                zip_file.write(file_path, arcname=file_name)
        return response


class GenericCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    model = None
    form_class = None
    success_url = None
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'store/form_template.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(self.model, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        if obj:
            for field in self.form_class.Meta.fields:
                value = getattr(obj, field, None)
                model_field = self.model._meta.get_field(field)
                initial[field] = value.all() if model_field.many_to_many else value
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.model == Book:
            kwargs['is_edit_mode'] = self.get_object() is not None
        return kwargs

    def form_valid(self, form):
        obj = self.get_object()
        if self.request.POST.get('clear_image') == 'true' and obj and obj.image:
            obj.image.delete(save=False)
            obj.image = None

        if obj:
            if self.model == Book:
                form = self.form_class(self.request.POST, self.request.FILES, instance=obj, is_edit_mode=True)
            else:
                form = self.form_class(self.request.POST, self.request.FILES, instance=obj)
        else:
            if self.model == Book:
                form = self.form_class(self.request.POST, self.request.FILES, is_edit_mode=False)
            else:
                form = self.form_class(self.request.POST, self.request.FILES)

        if form.is_valid():
            saved_object = form.save()
            
            if not obj and self.model == Book:
                audio_files = self.request.FILES.getlist('audio_files')
                for audio_file in audio_files:
                    AudioFile.objects.create(book=saved_object, file=audio_file)
            
            return redirect(reverse(self.success_url))  
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(self.request, error)
            return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        context['model_name'] = self.model._meta.verbose_name
        context['redirect_url'] = self.success_url
        if context['object']:
            context['delete_url'] = f"{self.model._meta.model_name}_delete"
        context['image_fields_json'] = mark_safe(json.dumps(self.form_class.image_fields))

        if context['object']:
            context['form_title'] = f"{_('Form edit')} \"{str(context['object']).upper()}\""
        else:
            titles = {
                Book: _("Add new book"),
                Author: _("Add new author"),
                Series: _("Add new series"),
                Genre: _("Add new genre"),
            }

            context['form_title'] = titles.get(
                self.model,
                f"{_('Form add')} {context['model_name'].upper()}"
            )
        return context


class BookCreateOrEditView(GenericCreateOrEditView):
    model = Book
    form_class = BookForm
    success_url = 'book_list'

    def get_initial(self):
        initial = super().get_initial()
        genre_slug = self.kwargs.get('genre_slug')
        author_slug = self.kwargs.get('author_slug')
        series_slug = self.kwargs.get('series_slug')

        if genre_slug:
            genre = Genre.objects.filter(slug=genre_slug).first()
            if genre:
                initial['genres'] = [genre.pk]
        if author_slug:
            author = Author.objects.filter(slug=author_slug).first()
            if author:
                initial['authors'] = [author.pk]
        if series_slug:
            series = Series.objects.filter(slug=series_slug).first()
            if series:
                initial['series'] = series.pk

        return initial


class AuthorCreateOrEditView(GenericCreateOrEditView):
    model = Author
    form_class = AuthorForm
    success_url = 'author_list'


class SeriesCreateOrEditView(GenericCreateOrEditView):
    model = Series
    form_class = SeriesForm
    success_url = 'series_list'


class GenreCreateOrEditView(GenericCreateOrEditView):
    model = Genre
    form_class = GenreForm
    success_url = 'genre_list'


class GenericDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = None
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    success_url = 'home'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model._meta.verbose_name
        context['redirect_url'] = self.success_url
        return context


class AuthorDeleteView(GenericDeleteView):
    model = Author
    success_url = reverse_lazy('author_list')


class SeriesDeleteView(GenericDeleteView):
    model = Series
    success_url = reverse_lazy('series_list')


class GenreDeleteView(GenericDeleteView):
    model = Genre
    success_url = reverse_lazy('genre_list')


class BookDeleteView(GenericDeleteView):
    model = Book
    success_url = reverse_lazy("book_list")

    def form_valid(self, form):
        book = self.get_object()

        if book.image:
            if os.path.isfile(book.image.path):
                os.remove(book.image.path)

        audio_files = AudioFile.objects.filter(book=book)
        for audio in audio_files:
            if audio.file and os.path.isfile(audio.file.path):
                os.remove(audio.file.path)
            audio.delete()

        return super().form_valid(form)
