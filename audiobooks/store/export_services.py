import csv
from datetime import datetime
from pathlib import Path

from .models import Author, Book


def export_authors_to_csv():
    authors = Author.objects.all()
    data = [
        {'first_name': author.first_name, 'last_name': author.last_name}
        for author in authors
    ]
    return _write_csv(
        prefix='authors_list',
        fieldnames=['first_name', 'last_name'],
        data=data,
    )


def export_books_to_csv():
    data = []
    books = Book.objects.select_related('series').prefetch_related(
        'authors',
        'genres',
        'audio_files',
    )
    for book in books:
        authors = list(book.authors.all())
        data.append({
            'title': book.title,
            'book_slug': book.slug,
            'authors': ", ".join(str(author) for author in authors),
            'authors_slugs': ", ".join(author.slug for author in authors),
            'series': book.series.title if book.series else "",
            'genres': ", ".join(genre.name for genre in book.genres.all()),
            'audio_files_count': len(book.audio_files.all()),
            'is_read': book.is_read,
        })
    return _write_csv(
        prefix='books_list',
        fieldnames=[
            'title',
            'book_slug',
            'authors',
            'authors_slugs',
            'series',
            'genres',
            'audio_files_count',
            'is_read',
        ],
        data=data,
    )


def _write_csv(*, prefix, fieldnames, data):
    filename = f'{prefix}_{datetime.now():%Y%m%d_%H%M%S}.csv'
    path = Path('media') / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    return str(path), filename, len(data), data
