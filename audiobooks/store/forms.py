from django import forms
from .models import Book, Author, Genre, Series


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'authors', 'genres', 'series', 'is_read', 'image']
        widgets = {
            'authors': forms.CheckboxSelectMultiple,
            'genres': forms.CheckboxSelectMultiple,
        }
        labels = {
            'title': 'Название книги',
            'authors': 'Авторы',
            'genres': 'Жанры',
            'series': 'Серия',
            'is_read': 'Прочитано',
            'image': 'Обложка книги',
        }


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['first_name', 'last_name', 'description', 'image']
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'description': 'Описание',
            'image': 'Фото автора',
        }


class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name', 'image']
        labels = {
            'name': 'Название жанра',
            'image': 'Фото жанра',
        }


class SeriesForm(forms.ModelForm):
    class Meta:
        model = Series
        fields = ['title', 'image']
        labels = {
            'title': 'Название серии',
            'image': 'Фото серии',
        }
