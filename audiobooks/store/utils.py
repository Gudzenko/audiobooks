from django.utils.text import slugify
from unidecode import unidecode
import re


def custom_slugify(value):
    to_lower = unidecode(value).lower()
    replace_space = re.sub(r'\s+', '_', to_lower)
    remove_symbols = re.sub(r'[^a-z0-9_]+', '', replace_space)
    return slugify(remove_symbols)
