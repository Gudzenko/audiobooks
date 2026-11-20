from django.http import Http404


def block_direct_audio_access(request, path):
    raise Http404
