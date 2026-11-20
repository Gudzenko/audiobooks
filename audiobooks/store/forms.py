from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from dal import autocomplete
from .models import Book, Author, Genre, Series
from .text_utils import custom_slugify


def validate_unique_slug(model, slug, instance, error_message):
    queryset = model.objects.filter(slug=slug)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise ValidationError(error_message)


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
            'authors': autocomplete.ModelSelect2Multiple(
                url='author-autocomplete',
                attrs={'data-minimum-input-length': 2}
            ),
            'genres': autocomplete.ModelSelect2Multiple(
                url='genre-autocomplete'
            ),
            'series': autocomplete.ModelSelect2(
                url='series-autocomplete'
            ),
            'is_read': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        authors = cleaned_data.get('authors')
        series = cleaned_data.get('series')
        
        if title and authors is not None:
            author_slugs = "_".join([custom_slugify(author.slug) for author in authors]) \
                if authors else "no_author"
            series_slug = series.slug if series else "no_series"
            new_slug = custom_slugify(f"{author_slugs}_{series_slug}_{title}")
            if self.instance.slug != new_slug:
                validate_unique_slug(
                    Book,
                    new_slug,
                    self.instance,
                    _('Book with this combination already exists'),
                )
    
        return cleaned_data


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
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': _('Author placeholder description'),
                    'style': 'resize: none;',
                }
            ),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        
        if first_name and last_name:
            slug = custom_slugify(f"{last_name} {first_name}")
            validate_unique_slug(
                Author,
                slug,
                self.instance,
                _('Author with this name already exists'),
            )
        
        return cleaned_data


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

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        if name:
            slug = custom_slugify(name)
            validate_unique_slug(
                Genre,
                slug,
                self.instance,
                _('Genre with this name already exists'),
            )
        
        return cleaned_data


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

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        if title:
            slug = custom_slugify(title)
            validate_unique_slug(
                Series,
                slug,
                self.instance,
                _('Series with this name already exists'),
            )
        
        return cleaned_data
