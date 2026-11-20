import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .text_utils import custom_slugify


logger = logging.getLogger(__name__)


def reconcile_book_audio_paths(book):
    audio_files = list(book.audio_files.all())
    if not audio_files:
        return
    move_audio_files(_build_move_plan(book, audio_files))


def _build_move_plan(book, audio_files):
    author_slugs = (
        "_".join(custom_slugify(author.slug) for author in book.authors.all())
        if book.authors.exists()
        else "no_author"
    )
    series_slug = book.series.slug if book.series else "no_series"
    plan = []
    target_paths = set()

    for audio in audio_files:
        old_path = Path(audio.file.path)
        relative_path = (
            Path('audio')
            / author_slugs
            / series_slug
            / book.slug
            / old_path.name
        )
        new_path = Path(settings.MEDIA_ROOT) / relative_path
        if old_path == new_path:
            continue
        if not old_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {old_path}")
        if new_path in target_paths or new_path.exists():
            raise FileExistsError(f"Audio destination already exists: {new_path}")
        target_paths.add(new_path)
        plan.append({
            'audio': audio,
            'old_path': old_path,
            'new_path': new_path,
            'new_relative_path': relative_path.as_posix(),
        })
    return plan


def move_audio_files(move_plan):
    moved_files = []
    try:
        with transaction.atomic():
            for item in move_plan:
                item['new_path'].parent.mkdir(parents=True, exist_ok=True)
                shutil.move(item['old_path'], item['new_path'])
                moved_files.append(item)
                updated = item['audio'].__class__.objects.filter(
                    pk=item['audio'].pk
                ).update(file=item['new_relative_path'])
                if updated != 1:
                    raise RuntimeError(
                        f"Audio record disappeared during move: {item['audio'].pk}"
                    )
    except Exception:
        rollback_errors = _rollback_audio_moves(moved_files)
        if rollback_errors:
            details = '; '.join(str(error) for error in rollback_errors)
            raise RuntimeError(
                f"Audio move failed and rollback was incomplete: {details}"
            )
        raise

    _remove_empty_parents(
        (item['old_path'].parent for item in move_plan),
        stop_at=Path(settings.MEDIA_ROOT) / 'audio',
    )


def _rollback_audio_moves(moved_files):
    errors = []
    for item in reversed(moved_files):
        try:
            item['old_path'].parent.mkdir(parents=True, exist_ok=True)
            shutil.move(item['new_path'], item['old_path'])
        except Exception as error:
            logger.exception("Could not roll back audio file %s", item['new_path'])
            errors.append(error)
    _remove_empty_parents(
        (item['new_path'].parent for item in moved_files),
        stop_at=Path(settings.MEDIA_ROOT) / 'audio',
    )
    return errors


def _remove_empty_parents(directories, *, stop_at):
    stop_at = stop_at.resolve()
    for directory in directories:
        current = directory.resolve()
        while current != stop_at and stop_at in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
