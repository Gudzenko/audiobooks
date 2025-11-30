from django import template
from django.templatetags.static import static

register = template.Library()


@register.inclusion_tag('store/_book_grid.html', takes_context=True)
def book_grid(context, books):
    return {
        'books': books,
        'user': context['user'],
        'default_image': static('store/images/default_book.png'),
    }
