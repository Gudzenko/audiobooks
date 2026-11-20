import os
import logging

from django.db import transaction
from django.utils.html import format_html

from .text_utils import custom_slugify


logger = logging.getLogger(__name__)


def genre_image_upload_path(instance, filename):
    return f"media/genres/{instance.slug}{os.path.splitext(filename)[1]}"


def author_image_upload_path(instance, filename):
    return f"media/authors/{instance.slug}{os.path.splitext(filename)[1]}"


def series_image_upload_path(instance, filename):
    return f"media/series/{instance.slug}{os.path.splitext(filename)[1]}"


def book_image_upload_path(instance, filename):
    return f"media/books/{instance.slug}{os.path.splitext(filename)[1]}"


def audio_file_upload_path(instance, filename):
    book = instance.book
    author_slugs = (
        "_".join(custom_slugify(author.slug) for author in book.authors.all())
        if book.authors.exists()
        else "no_author"
    )
    series_slug = book.series.slug if book.series else "no_series"
    return f"audio/{author_slugs}/{series_slug}/{book.slug}/{filename}"


def delete_old_image(instance, field_name='image'):
    if not instance.pk:
        return
    old_image = getattr(instance.__class__.objects.get(pk=instance.pk), field_name)
    new_image = getattr(instance, field_name)
    if old_image and old_image != new_image:
        delete_file_after_commit(old_image.storage, old_image.name)


def delete_file_after_commit(storage, name):
    if not name:
        return

    transaction.on_commit(lambda: delete_file_safely(storage, name))


def delete_file_safely(storage, name):
    if not name:
        return
    try:
        storage.delete(name)
    except Exception:
        logger.exception("Could not delete file: %s", name)


def get_image_preview(obj, field_name='image', width=50):
    image = getattr(obj, field_name)
    if not image:
        return "-"
    return format_html(
        '<img src="{}" style="width: {}px; height: auto;" />',
        image.url,
        width,
    )
