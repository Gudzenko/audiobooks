import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import DeleteView, FormView

from .forms import AuthorForm, BookForm, GenreForm, SeriesForm
from .models import AudioFile, Author, Book, Genre, Series
from .audio_services import reconcile_book_audio_paths
from .storage_paths import delete_file_safely


logger = logging.getLogger(__name__)


class GenericCreateOrEditView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    model = None
    form_class = None
    success_url = None
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'store/form_template.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self):
        slug = self.kwargs.get('slug')
        return get_object_or_404(self.model, slug=slug) if slug else None

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        if obj:
            for field in self.form_class.Meta.fields:
                value = getattr(obj, field, None)
                model_field = self.model._meta.get_field(field)
                initial[field] = value.all() if model_field.many_to_many else value
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        obj = self.get_object()
        if obj:
            kwargs['instance'] = obj
        return kwargs

    def form_valid(self, form):
        obj = self.get_object()
        if self.request.POST.get('clear_image') == 'true' and obj and obj.image:
            form.instance.image = None
        form.save()
        return redirect(reverse(self.success_url))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        context['model_name'] = self.model._meta.verbose_name
        context['redirect_url'] = self.success_url
        if context['object']:
            context['delete_url'] = f"{self.model._meta.model_name}_delete"
        context['image_fields_json'] = mark_safe(json.dumps(self.form_class.image_fields))

        if context['object']:
            context['form_title'] = f"{_('Form edit')} \"{str(context['object']).upper()}\""
        else:
            titles = {
                Book: _("Add new book"),
                Author: _("Add new author"),
                Series: _("Add new series"),
                Genre: _("Add new genre"),
            }
            context['form_title'] = titles.get(
                self.model,
                f"{_('Form add')} {context['model_name'].upper()}",
            )
        return context


class BookCreateOrEditView(GenericCreateOrEditView):
    model = Book
    form_class = BookForm
    success_url = 'book_list'

    def get_initial(self):
        initial = super().get_initial()
        related_slugs = (
            ('genres', Genre, self.kwargs.get('genre_slug'), True),
            ('authors', Author, self.kwargs.get('author_slug'), True),
            ('series', Series, self.kwargs.get('series_slug'), False),
        )
        for field, model, slug, multiple in related_slugs:
            if not slug:
                continue
            item = model.objects.filter(slug=slug).first()
            if item:
                initial[field] = [item.pk] if multiple else item.pk
        return initial

    def form_valid(self, form):
        book_id = form.instance.pk
        original_image_name = (
            Book.objects.only('image').get(pk=book_id).image.name
            if book_id
            else ''
        )
        request_files = []
        sequential_upload = (
            self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            and self.request.POST.get('sequential_audio_upload') == '1'
        )

        try:
            with transaction.atomic():
                result = super().form_valid(form)
                if book_id:
                    reconcile_book_audio_paths(Book.objects.get(pk=book_id))
                elif not sequential_upload:
                    for uploaded_file in self.request.FILES.getlist('audio_files'):
                        audio = AudioFile(book=form.instance, file=uploaded_file)
                        try:
                            audio.save()
                        finally:
                            if audio.file._committed and audio.file.name:
                                request_files.append(
                                    (audio.file.storage, audio.file.name)
                                )
        except Exception:
            logger.exception("Error handling audio files for book %s", form.instance.pk)
            for storage, name in reversed(request_files):
                delete_file_safely(storage, name)
            image = form.instance.image
            if (
                image
                and image._committed
                and image.name != original_image_name
            ):
                delete_file_safely(image.storage, image.name)
            if not book_id:
                form.instance.pk = None
                form.instance._state.adding = True
            error_message = _("Error processing audio files")
            if sequential_upload:
                return JsonResponse({'error': str(error_message)}, status=500)
            form.add_error(None, error_message)
            return self.form_invalid(form)

        if not sequential_upload:
            return result

        saved_book = Book.objects.get(pk=form.instance.pk)
        return JsonResponse({
            'upload_url': reverse(
                'book_audio_upload',
                kwargs={'slug': saved_book.slug},
            ),
            'redirect_url': reverse(
                'book_detail',
                kwargs={'slug': saved_book.slug},
            ),
            'recovery_url': reverse(
                'book_edit',
                kwargs={'slug': saved_book.slug},
            ),
        })


class AuthorCreateOrEditView(GenericCreateOrEditView):
    model = Author
    form_class = AuthorForm
    success_url = 'author_list'


class SeriesCreateOrEditView(GenericCreateOrEditView):
    model = Series
    form_class = SeriesForm
    success_url = 'series_list'


class GenreCreateOrEditView(GenericCreateOrEditView):
    model = Genre
    form_class = GenreForm
    success_url = 'genre_list'


class GenericDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = None
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    success_url = 'home'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model._meta.verbose_name
        context['redirect_url'] = self.success_url
        return context


class AuthorDeleteView(GenericDeleteView):
    model = Author
    success_url = reverse_lazy('author_list')


class SeriesDeleteView(GenericDeleteView):
    model = Series
    success_url = reverse_lazy('series_list')


class GenreDeleteView(GenericDeleteView):
    model = Genre
    success_url = reverse_lazy('genre_list')


class BookDeleteView(GenericDeleteView):
    model = Book
    success_url = reverse_lazy('book_list')
