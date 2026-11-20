import logging
import mimetypes
import os
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from .models import AudioFile, Book
from .storage_paths import delete_file_safely


logger = logging.getLogger(__name__)


class DownloadAllAudioView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, slug, *args, **kwargs):
        book = get_object_or_404(Book, slug=slug)
        response = HttpResponse(content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{slug}.zip"'

        with zipfile.ZipFile(response, 'w') as zip_file:
            for audio in book.audio_files.all():
                file_path = audio.file.path
                zip_file.write(file_path, arcname=os.path.basename(file_path))
        return response


class AudioFileView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, pk, *args, **kwargs):
        audio = get_object_or_404(AudioFile, pk=pk)
        relative_path = PurePosixPath(audio.file.name)
        if (
            not relative_path.parts
            or relative_path.parts[0] != 'audio'
            or '..' in relative_path.parts
        ):
            raise Http404

        content_type = (
            mimetypes.guess_type(audio.file.name)[0]
            or 'application/octet-stream'
        )
        if settings.DEBUG:
            return FileResponse(audio.file.open('rb'), content_type=content_type)

        internal_path = PurePosixPath(*relative_path.parts[1:]).as_posix()
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = (
            f'/_protected_audio/{quote(internal_path, safe="/")}'
        )
        return response


class BookAudioUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, slug, *args, **kwargs):
        book = get_object_or_404(Book, slug=slug)
        uploaded_files = request.FILES.getlist('audio_file')
        if len(uploaded_files) != 1:
            return JsonResponse(
                {'error': 'Exactly one audio file is required.'},
                status=400,
            )

        uploaded_file = uploaded_files[0]
        if uploaded_file.size <= 0:
            return JsonResponse({'error': 'The audio file is empty.'}, status=400)
        if uploaded_file.size > settings.MAX_AUDIO_FILE_SIZE:
            return JsonResponse(
                {'error': 'The audio file exceeds the 4 GB storage limit.'},
                status=413,
            )

        audio = AudioFile(book=book)
        file_field = AudioFile._meta.get_field('file')
        expected_name = file_field.generate_filename(audio, uploaded_file.name)
        existing_audio = AudioFile.objects.filter(
            book=book,
            file=expected_name,
        ).first()
        if existing_audio:
            return JsonResponse({
                'id': existing_audio.pk,
                'status': 'already_exists',
            })

        audio.file = uploaded_file
        try:
            audio.save()
        except Exception:
            if audio.file._committed and audio.file.name:
                delete_file_safely(audio.file.storage, audio.file.name)
            logger.exception("Could not save uploaded audio for book %s", book.pk)
            return JsonResponse(
                {'error': 'The audio file could not be saved.'},
                status=500,
            )
        return JsonResponse({'id': audio.pk, 'status': 'created'}, status=201)
