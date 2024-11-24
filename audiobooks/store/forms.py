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
    image_fields = ['image']

    class Meta:
        model = Author
        fields = ['first_name', 'last_name', 'description', 'image']
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'description': 'Описание',
            'image': 'Фото автора',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите фамилию'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Введите описание'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class GenreForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Genre
        fields = ['name', 'image']
        labels = {
            'name': 'Название жанра',
            'image': 'Фото жанра',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите название жанра'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class SeriesForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Series
        fields = ['title', 'image']
        labels = {
            'title': 'Название серии',
            'image': 'Фото серии',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите название серии'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
