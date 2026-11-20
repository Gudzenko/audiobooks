import re

from django.utils.text import slugify
from unidecode import unidecode


def custom_slugify(value):
    lowercase = unidecode(value).lower()
    with_underscores = re.sub(r'\s+', '_', lowercase)
    alphanumeric = re.sub(r'[^a-z0-9_]+', '', with_underscores)
    return slugify(alphanumeric)
