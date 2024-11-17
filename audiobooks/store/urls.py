from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/<slug:slug>/', views.BookDetailView.as_view(), name='book_detail'),
    path('book/<slug:slug>/download-all/', views.DownloadAllAudioView.as_view(), name='download_all_audio'),
    path('authors/', views.AuthorListView.as_view(), name='author_list'),
    path('authors/<slug:slug>/', views.AuthorDetailView.as_view(), name='author_detail'),
    path('series/', views.SeriesListView.as_view(), name='series_list'),
    path('series/<slug:slug>/', views.SeriesDetailView.as_view(), name='series_detail'),
    path('genres/', views.GenreListView.as_view(), name='genre_list'),
    path('genres/<slug:slug>/', views.GenreDetailView.as_view(), name='genre_detail'),
]
