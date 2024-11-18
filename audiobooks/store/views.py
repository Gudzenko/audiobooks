import logging
import os
import zipfile
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.contrib import messages
from django.templatetags.static import static
from django.views.generic import TemplateView, DetailView
from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from .forms import BookForm, AuthorForm, SeriesForm, GenreForm
from .models import Book, Author, Series, Genre, AudioFile


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

    def get_items(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get('query', '')
        item_list = self.get_items()
        if query:
            item_list = [item for item in item_list if query.lower() in item['label'].lower()]

        paginator = Paginator(item_list, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['title'] = self.title
        context['title_url'] = self.title_url
        context['page_obj'] = page_obj
        context['query'] = query
        context['add_item_name'] = self.add_item_name
        return context


class BookListView(PaginatedListView):
    title = 'Книги'
    title_url = 'book'
    image = static('store/images/default_book.png')
    add_item_name = 'Добавить книгу'

    def get_items(self):
        return [
            {
                'image': book.image.url if book.image else self.image,
                'label': book.title,
                'slug': book.slug,
            }
            for book in Book.objects.all()
        ]


class AuthorListView(PaginatedListView):
    title = 'Авторы'
    title_url = 'author'
    image = static('store/images/default_author.png')
    add_item_name = 'Добавить автора'

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
    title = 'Серии'
    title_url = 'series'
    image = static('store/images/default_series.png')
    add_item_name = 'Добавить серию'

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
    title = 'Жанры'
    title_url = 'genre'
    image = static('store/images/default_genre.png')
    add_item_name = 'Добавить жанр'

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


class BookCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'store/book_form.html'
    form_class = BookForm

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(Book, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        genre_slug = self.kwargs.get('genre_slug')
        author_slug = self.kwargs.get('author_slug')
        series_slug = self.kwargs.get('series_slug')

        if genre_slug:
            genre = get_object_or_404(Genre, slug=genre_slug)
            initial['genres'] = [genre]
        if author_slug:
            author = get_object_or_404(Author, slug=author_slug)
            initial['authors'] = [author]
        if series_slug:
            series = get_object_or_404(Series, slug=series_slug)
            initial['series'] = series

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        book = form.save()

        files = self.request.FILES.getlist('audio_files')
        for file in files:
            AudioFile.objects.create(book=book, file=file)

        messages.success(self.request, 'Книга успешно сохранена!')
        return redirect('book_detail', slug=book.slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['book'] = self.get_object()
        context['previous_page'] = self.request.GET.get('next', reverse('home'))
        return context


class AuthorCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'store/author_form.html'
    form_class = AuthorForm
    success_url = reverse_lazy('author_list')

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(Author, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        if obj:
            initial['first_name'] = obj.first_name
            initial['last_name'] = obj.last_name
            initial['description'] = obj.description
            initial['image'] = obj.image
        return initial

    def form_valid(self, form):
        obj = self.get_object()
        if obj:
            form = AuthorForm(self.request.POST, self.request.FILES, instance=obj)
        else:
            form = AuthorForm(self.request.POST, self.request.FILES)

        if form.is_valid():
            form.save()
            messages.success(self.request, 'Автор успешно сохранён!')
            return redirect(self.success_url)

        messages.error(self.request, 'Ошибка при сохранении автора.')
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context


class SeriesCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'store/series_form.html'
    form_class = SeriesForm
    success_url = reverse_lazy('series_list')

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(Series, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        if obj:
            initial['title'] = obj.title
            initial['image'] = obj.image
        return initial

    def form_valid(self, form):
        obj = self.get_object()
        if obj:
            form = SeriesForm(self.request.POST, self.request.FILES, instance=obj)
        else:
            form = SeriesForm(self.request.POST, self.request.FILES)

        if form.is_valid():
            form.save()
            messages.success(self.request, 'Серия успешно сохранена!')
            return redirect(self.success_url)

        messages.error(self.request, 'Ошибка при сохранении серии.')
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context


class GenreCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'store/genre_form.html'
    form_class = GenreForm
    success_url = reverse_lazy('genre_list')

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(Genre, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        if obj:
            initial['name'] = obj.name
            initial['image'] = obj.image
        return initial

    def form_valid(self, form):
        obj = self.get_object()
        if obj:
            form = GenreForm(self.request.POST, self.request.FILES, instance=obj)
        else:
            form = GenreForm(self.request.POST, self.request.FILES)

        if form.is_valid():
            form.save()
            messages.success(self.request, 'Жанр успешно сохранён!')
            return redirect(self.success_url)

        messages.error(self.request, 'Ошибка при сохранении жанра.')
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context


