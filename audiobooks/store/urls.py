from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/<slug:slug>/', views.BookDetailView.as_view(), name='book_detail'),
    path('book/<slug:slug>/download-all/', views.DownloadAllAudioView.as_view(), name='download_all_audio'),
    path('book/add/', views.BookCreateOrEditView.as_view(), name='book_add'),
    path('book/<slug:slug>/edit/', views.BookCreateOrEditView.as_view(), name='book_edit'),
    path('book/add/genre/<slug:genre_slug>/', views.BookCreateOrEditView.as_view(), name='book_add_genre'),
    path('book/add/author/<slug:author_slug>/', views.BookCreateOrEditView.as_view(), name='book_add_author'),
    path('book/add/series/<slug:series_slug>/', views.BookCreateOrEditView.as_view(), name='book_add_series'),
    path('authors/', views.AuthorListView.as_view(), name='author_list'),
    path('authors/<slug:slug>/', views.AuthorDetailView.as_view(), name='author_detail'),
    path('author/add/', views.AuthorCreateOrEditView.as_view(), name='author_add'),
    path('author/<slug:slug>/edit/', views.AuthorCreateOrEditView.as_view(), name='author_edit'),
    path('series/', views.SeriesListView.as_view(), name='series_list'),
    path('series/add/', views.SeriesCreateOrEditView.as_view(), name='series_add'),
    path('series/<slug:slug>/', views.SeriesDetailView.as_view(), name='series_detail'),
    path('series/<slug:slug>/edit/', views.SeriesCreateOrEditView.as_view(), name='series_edit'),
    path('genres/', views.GenreListView.as_view(), name='genre_list'),
    path('genre/add/', views.GenreCreateOrEditView.as_view(), name='genre_add'),
    path('genre/<slug:slug>/', views.GenreDetailView.as_view(), name='genre_detail'),
    path('genre/<slug:slug>/edit/', views.GenreCreateOrEditView.as_view(), name='genre_edit'),
]
