import logging
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .utils import custom_slugify


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Model')


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(self.name) if self.name else ""
        if not self.slug:
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(f"{self.last_name} {self.first_name}") if self.last_name and self.first_name else ""
        if not self.slug:
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Series(models.Model):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = custom_slugify(self.title) if self.title else ""
        if not self.slug:
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Book(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='books', blank=True)
    genres = models.ManyToManyField(Genre, related_name='books', blank=True)
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name='books')
    slug = models.SlugField(max_length=200, unique=True, blank=True, editable=False)
    is_read = models.BooleanField(default=False, verbose_name="Is read")

    def save(self, *args, **kwargs):
        if self.title:
            author_slugs = "_".join([custom_slugify(author.slug) for author in self.authors.all()]) \
                if self.authors.exists() else "no_author"
            series_slug = self.series.slug if self.series else "no_series"
            self.slug = custom_slugify(f"{author_slugs}_{series_slug}_{self.title}")
            super().save(*args, **kwargs)

    def __str__(self):
        return self.title


@receiver(m2m_changed, sender=Book.authors.through)
def update_book_slug(sender, instance, action, **kwargs):
    if action == 'post_add' or action == 'post_remove' or action == 'post_clear':
        author_slugs = "_".join([custom_slugify(author.first_name + author.last_name) for author in instance.authors.all()])
        series_slug = custom_slugify(instance.series.title) if instance.series else "no_series"
        instance.slug = custom_slugify(f"{author_slugs}_{series_slug}_{instance.title}")
        instance.save()
