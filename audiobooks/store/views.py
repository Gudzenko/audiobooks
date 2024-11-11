import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.templatetags.static import static
from django.views.generic import TemplateView, DetailView
from .models import Book, Author, Series, Genre


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
        return context


class BookListView(PaginatedListView):
    title = 'Книги'
    title_url = 'book'
    image = static('store/images/default_book.png')

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
