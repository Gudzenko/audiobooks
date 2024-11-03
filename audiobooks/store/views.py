from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, DetailView
from .models import Book, Author, Series, Genre


class HomeView(TemplateView):
    template_name = 'store/home.html'


class BookListView(LoginRequiredMixin, TemplateView):
    template_name = 'store/tile_list.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = [
            {
                'image': 'store/images/default_book.png',
                'label': book.title,
                'slug': book.slug,
            }
            for book in Book.objects.all()
        ]
        context['title'] = 'Книги'
        context['title_url'] = 'book'
        return context


class AuthorListView(LoginRequiredMixin, TemplateView):
    template_name = 'store/tile_list.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = [
            {
                'image': 'store/images/default_author.png',
                'label': f"{author.first_name} {author.last_name}",
                'slug': author.slug,
            }
            for author in Author.objects.all()
        ]
        context['title'] = 'Авторы'
        context['title_url'] = 'author'
        return context


class SeriesListView(LoginRequiredMixin, TemplateView):
    template_name = 'store/tile_list.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = [
            {
                'image': 'store/images/default_series.png',
                'label': series.title,
                'slug': series.slug,
            }
            for series in Series.objects.all()
        ]
        context['title'] = 'Серии'
        context['title_url'] = 'series'
        return context


class GenreListView(LoginRequiredMixin, TemplateView):
    template_name = 'store/tile_list.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = [
            {
                'image': 'store/images/default_genre.png',
                'label': genre.name,
                'slug': genre.slug,
            }
            for genre in Genre.objects.all()
        ]
        context['title'] = 'Жанры'
        context['title_url'] = 'genre'
        return context


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = Book.objects.filter(genres=self.object)
        return context
