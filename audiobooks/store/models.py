import logging
import os
import shutil
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver
from .utils import custom_slugify, delete_old_image, genre_image_upload_path, author_image_upload_path, \
    series_image_upload_path, book_image_upload_path, audio_file_upload_path


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Model')


class Genre(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)
    image = models.ImageField(upload_to=genre_image_upload_path, blank=True, null=True)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(self.name) if self.name else ""
        if not self.slug:
            return
        delete_old_image(self)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.name


class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)
    image = models.ImageField(upload_to=author_image_upload_path, blank=True, null=True)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(f"{self.last_name} {self.first_name}") if self.last_name and self.first_name else ""
        if not self.slug:
            return
        delete_old_image(self)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Series(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)
    image = models.ImageField(upload_to=series_image_upload_path, blank=True, null=True)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(self.title) if self.title else ""
        if not self.slug:
            return
        delete_old_image(self)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.title


class Book(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='books', blank=True)
    genres = models.ManyToManyField(Genre, related_name='books', blank=True)
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name='books')
    slug = models.SlugField(max_length=200, unique=True, blank=True, editable=False)
    is_read = models.BooleanField(default=False, verbose_name="Is read")
    image = models.ImageField(upload_to=book_image_upload_path, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.title:
            raise ValidationError("Book title is required")
        if not self.pk:
            import uuid
            self.slug = f"temp_{uuid.uuid4().hex[:8]}"
            super().save(*args, **kwargs)
            return

        if self.title:
            author_slugs = "_".join([custom_slugify(author.slug) for author in self.authors.all()]) \
                if self.authors.exists() else "no_author"
            series_slug = self.series.slug if self.series else "no_series"
            self.slug = custom_slugify(f"{author_slugs}_{series_slug}_{self.title}")
            if Book.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                raise ValidationError(f"Book with slug '{self.slug}' already exists")

            delete_old_image(self)
            super().save(*args, **kwargs)

    def move_to_new_path(self):
        old_path = self.file.path
        new_path = audio_file_upload_path(self, os.path.basename(old_path))
        if old_path != new_path:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            self.file.name = new_path.replace('media/', '')
            self.save()

    def __str__(self):
        return self.title


@receiver(m2m_changed, sender=Book.authors.through)
def update_book_slug(sender, instance, action, **kwargs):
    if action == 'post_add' or action == 'post_remove' or action == 'post_clear':
        author_slugs = "_".join([custom_slugify(author.first_name + author.last_name) for author in instance.authors.all()])
        series_slug = custom_slugify(instance.series.title) if instance.series else "no_series"
        instance.slug = custom_slugify(f"{author_slugs}_{series_slug}_{instance.title}")
        instance.save()

    for audio_file in instance.audio_files.all():
        audio_file.move_to_new_path()


class AudioFile(models.Model):
    book = models.ForeignKey(Book, related_name="audio_files", on_delete=models.CASCADE)
    file = models.FileField(upload_to=audio_file_upload_path, max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            old_file = AudioFile.objects.get(pk=self.pk).file
            if old_file and old_file != self.file:
                old_file.delete(save=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return os.path.basename(self.file.name)


@receiver(pre_delete, sender=AudioFile)
def delete_file_on_instance_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
