from django.utils.text import slugify
from django.utils.html import format_html
from unidecode import unidecode
import re
import os


def custom_slugify(value):
    to_lower = unidecode(value).lower()
    replace_space = re.sub(r'\s+', '_', to_lower)
    remove_symbols = re.sub(r'[^a-z0-9_]+', '', replace_space)
    return slugify(remove_symbols)


def genre_image_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1]
    return f"media/genres/{instance.slug}{extension}"


def author_image_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1]
    return f"media/authors/{instance.slug}{extension}"


def series_image_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1]
    return f"media/series/{instance.slug}{extension}"


def delete_old_image(instance, field_name='image'):
    if instance.pk:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
        old_image = getattr(old_instance, field_name)
        new_image = getattr(instance, field_name)
        if old_image and old_image != new_image:
            old_image.delete(save=False)


def get_image_preview(obj, field_name='image', width=50):
    image = getattr(obj, field_name)
    if image:
        return format_html('<img src="{}" style="width: {}px; height: auto;" />', image.url, width)
    return "-"
