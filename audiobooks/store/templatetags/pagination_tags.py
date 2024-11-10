from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag
def pagination(page_obj, query):
    return render_to_string('store/_pagination.html', {'page_obj': page_obj, 'query': query})
