from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Book, Author, Genre, Series


class BookForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Book
        fields = ['title', 'authors', 'genres', 'series', 'is_read', 'image']
        labels = {
            'title': _('Book title'),
            'authors': _('Authors'),
            'genres': _('Book genres'),
            'series': _('Book series'),
            'is_read': _('Book is read'),
            'image': _('Book image'),
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Book placeholder title')}),
            'authors': forms.CheckboxSelectMultiple(),
            'genres': forms.CheckboxSelectMultiple(),
            'series': forms.Select(attrs={'class': 'form-select'}),
            'is_read': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class AuthorForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Author
        fields = ['first_name', 'last_name', 'description', 'image']
        labels = {
            'first_name': _('Author firstname'),
            'last_name': _('Author lastname'),
            'description': _('Author description'),
            'image': _('Author image'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Author placeholder firstname')}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Author placeholder lastname')}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Author placeholder description')}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class GenreForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Genre
        fields = ['name', 'image']
        labels = {
            'name': _('Genre name'),
            'image': _('Genre image'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Genre placeholder name')}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class SeriesForm(forms.ModelForm):
    image_fields = ['image']

    class Meta:
        model = Series
        fields = ['title', 'image']
        labels = {
            'title': _('Series name'),
            'image': _('Series image'),
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Series placeholder name')}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
