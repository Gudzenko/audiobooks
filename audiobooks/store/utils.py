from django.conf import settings
from django.utils.text import slugify
from django.utils.html import format_html
from unidecode import unidecode
import shutil
import re
import os
import csv
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


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


def book_image_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1]
    return f"media/books/{instance.slug}{extension}"


def audio_file_upload_path(instance, filename):
    author_slugs = "_".join([custom_slugify(author.slug) for author in instance.book.authors.all()]) \
        if instance.book.authors.exists() else "no_author"
    series_slug = instance.book.series.slug if instance.book.series else "no_series"
    book_slug = instance.book.slug
    return f"audio/{author_slugs}/{series_slug}/{book_slug}/{filename}"


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


def export_authors_to_csv():
    from .models import Author
    
    authors = Author.objects.all()
    
    authors_data = [
        {
            'first_name': author.first_name,
            'last_name': author.last_name
        }
        for author in authors
    ]
    
    filename = f'authors_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    filepath = os.path.join('media', filename)
    
    os.makedirs('media', exist_ok=True)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['first_name', 'last_name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for author_data in authors_data:
            writer.writerow(author_data)
    
    return filepath, filename, len(authors_data), authors_data


def export_books_to_csv():
    from .models import Book
    
    books = Book.objects.all()
    
    books_data = []
    for book in books:
        authors = ", ".join([f"{author.first_name} {author.last_name}" for author in book.authors.all()])
        authors_slugs = ", ".join([author.slug for author in book.authors.all()])
        genres = ", ".join([genre.name for genre in book.genres.all()])
        series = book.series.title if book.series else ""
        audio_count = book.audio_files.count()
        
        books_data.append({
            'title': book.title,
            'book_slug': book.slug,
            'authors': authors,
            'authors_slugs': authors_slugs,
            'series': series,
            'genres': genres,
            'audio_files_count': audio_count,
            'is_read': book.is_read
        })
    
    filename = f'books_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    filepath = os.path.join('media', filename)
    
    os.makedirs('media', exist_ok=True)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'book_slug', 'authors', 'authors_slugs', 'series', 'genres', 'audio_files_count', 'is_read']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for book_data in books_data:
            writer.writerow(book_data)
    
    return filepath, filename, len(books_data), books_data


def handle_book_slug_change(book, old_slug):
    if not should_move_files(book, old_slug):
        return
    
    audio_files_data = get_audio_files_to_move(book)
    if not audio_files_data:
        return
    
    new_paths = build_new_paths(book, audio_files_data)
    move_audio_files(audio_files_data, new_paths)
    update_database_references(audio_files_data, new_paths)
    cleanup_old_directories(old_slug)


def should_move_files(book, old_slug):
    return old_slug != book.slug


def get_audio_files_to_move(book):
    audio_files = book.audio_files.all()
    
    files_data = []
    for af in audio_files:
        files_data.append({
            'id': af.pk,
            'object': af,
            'old_path': af.file.path,
            'filename': os.path.basename(af.file.path)
        })
    
    return files_data


def build_new_paths(book, audio_files_data):
    author_slugs = "_".join([custom_slugify(author.slug) for author in book.authors.all()]) \
        if book.authors.exists() else "no_author"
    series_slug = book.series.slug if book.series else "no_series"
    
    new_paths = {}
    for file_data in audio_files_data:
        new_relative = f"audio/{author_slugs}/{series_slug}/{book.slug}/{file_data['filename']}"
        new_absolute = os.path.join(settings.MEDIA_ROOT, new_relative)
        new_paths[file_data['id']] = {
            'relative': new_relative,
            'absolute': new_absolute
        }
    
    return new_paths


def move_audio_files(audio_files_data, new_paths):
    for file_data in audio_files_data:
        old_path = file_data['old_path']
        new_path = new_paths[file_data['id']]['absolute']
        
        if not os.path.exists(old_path):
            logger.warning(f"File not found: {old_path}")
            continue
        
        if old_path == new_path:
            continue
        
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        
        try:
            shutil.move(old_path, new_path)
        except Exception as e:
            logger.error(f"Error moving file {file_data['filename']}: {str(e)}")
            raise


def update_database_references(audio_files_data, new_paths):
    for file_data in audio_files_data:
        audio_file = file_data['object']
        new_relative_path = new_paths[file_data['id']]['relative']
        
        try:
            audio_file.file.name = new_relative_path
            audio_file.save(update_fields=['file'])
        except Exception as e:
            logger.error(f"Error updating database for {file_data['filename']}: {str(e)}")
            raise


def cleanup_old_directories(old_slug):
    old_slug_parts = old_slug.split('_')
    if len(old_slug_parts) < 3:
        logger.warning(f"Cannot determine folder structure from slug: {old_slug}")
        return
    
    old_series_slug = old_slug_parts[-2]
    old_author_slugs = "_".join(old_slug_parts[:-2])
    
    old_book_dir = os.path.join(settings.MEDIA_ROOT, 'audio', old_author_slugs, old_series_slug, old_slug)
    old_series_dir = os.path.join(settings.MEDIA_ROOT, 'audio', old_author_slugs, old_series_slug)
    old_author_dir = os.path.join(settings.MEDIA_ROOT, 'audio', old_author_slugs)
    
    try:
        if os.path.exists(old_book_dir) and not os.listdir(old_book_dir):
            os.rmdir(old_book_dir)
        
        if os.path.exists(old_series_dir) and not os.listdir(old_series_dir):
            os.rmdir(old_series_dir)
        
        if os.path.exists(old_author_dir) and not os.listdir(old_author_dir):
            os.rmdir(old_author_dir)
            
    except OSError as e:
        logger.warning(f"Could not remove directory: {str(e)}")
