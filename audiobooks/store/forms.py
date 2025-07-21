from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Book, Author, Genre, Series


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class BookForm(forms.ModelForm):
    image_fields = ['image']
    audio_files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'accept': 'audio/*',
            'class': 'form-control'
        }),
        required=False,
        label=_('Book audiofiles'),
        help_text=_('Select multiple audio files to upload')
    )

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

    def __init__(self, *args, **kwargs):
        self.is_edit_mode = kwargs.pop('is_edit_mode', False)
        super().__init__(*args, **kwargs)
        
        if self.is_edit_mode:
            del self.fields['audio_files']


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
