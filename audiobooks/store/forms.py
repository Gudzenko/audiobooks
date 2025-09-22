from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from dal import autocomplete
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
            'authors': autocomplete.ModelSelect2Multiple(
                url='author-autocomplete',
                attrs={'data-minimum-input-length': 2}
            ),
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

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        authors = cleaned_data.get('authors')
        series = cleaned_data.get('series')
        
        if title:
            from .utils import custom_slugify
            
            author_slugs = "_".join([custom_slugify(author.slug) for author in authors]) \
                if authors else "no_author"
            series_slug = series.slug if series else "no_series"
            slug = custom_slugify(f"{author_slugs}_{series_slug}_{title}")
            
            if self.instance.pk:
                existing_book = Book.objects.filter(slug=slug).exclude(pk=self.instance.pk).first()
            else:
                existing_book = Book.objects.filter(slug=slug).first()
            
            if existing_book:
                raise ValidationError(_('Book with this combination already exists'))
        
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
            from .utils import custom_slugify
            slug = custom_slugify(f"{last_name} {first_name}")
            
            if self.instance.pk:
                existing_author = Author.objects.filter(slug=slug).exclude(pk=self.instance.pk).first()
            else:
                existing_author = Author.objects.filter(slug=slug).first()
            
            if existing_author:
                raise ValidationError(_('Author with this name already exists'))
        
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
            from .utils import custom_slugify
            slug = custom_slugify(name)
            
            if self.instance.pk:
                existing_genre = Genre.objects.filter(slug=slug).exclude(pk=self.instance.pk).first()
            else:
                existing_genre = Genre.objects.filter(slug=slug).first()
            
            if existing_genre:
                raise ValidationError(_('Genre with this name already exists'))
        
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
            from .utils import custom_slugify
            slug = custom_slugify(title)
            
            if self.instance.pk:
                existing_series = Series.objects.filter(slug=slug).exclude(pk=self.instance.pk).first()
            else:
                existing_series = Series.objects.filter(slug=slug).first()
            
            if existing_series:
                raise ValidationError(_('Series with this name already exists'))
        
        return cleaned_data
