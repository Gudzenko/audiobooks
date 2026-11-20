from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.templatetags.static import static
from django.views.generic import TemplateView, DetailView
from django.utils.translation import gettext_lazy as _

from .models import Author, Book, Genre, Series

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
