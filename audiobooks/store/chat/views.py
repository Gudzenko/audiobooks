import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView
from pydantic import ValidationError

from .contracts import ChatModelUnavailable
from .constants import (
    CLIENT_CHAT_HISTORY_TOTAL_CHARS,
    MAX_CHAT_HISTORY_ITEMS,
)
from .factories import build_chat_orchestrator
from .rate_limit import (
    ChatRateLimitExceeded,
    ChatRequestInProgress,
    limit_chat_requests,
)
from .schemas import ChatRequest


logger = logging.getLogger(__name__)


class ChatPageView(LoginRequiredMixin, TemplateView):
    template_name = "store/chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chat_history_item_limit"] = MAX_CHAT_HISTORY_ITEMS
        context["chat_history_character_limit"] = (
            CLIENT_CHAT_HISTORY_TOTAL_CHARS
        )
        return context


class ChatMessageView(View):
    http_method_names = ["post"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": _("Authentication required.")}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.content_type != "application/json":
            return JsonResponse(
                {"error": _("Content-Type must be application/json.")},
                status=415,
            )

        try:
            payload = json.loads(request.body)
            chat_request = ChatRequest.model_validate(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
            return JsonResponse(
                {"error": _("Invalid chat request.")},
                status=400,
            )

        try:
            with limit_chat_requests(request.user.pk):
                response = build_chat_orchestrator().reply(chat_request)
        except ChatRateLimitExceeded:
            return JsonResponse(
                {
                    "kind": "error",
                    "error": _(
                        "Too many chat requests. Please wait a minute and try again."
                    ),
                },
                status=429,
            )
        except ChatRequestInProgress:
            return JsonResponse(
                {
                    "kind": "error",
                    "error": _(
                        "Another chat request is already running. Please wait for it "
                        "to finish."
                    ),
                },
                status=429,
            )
        except ChatModelUnavailable:
            logger.exception("Chat model failed while processing a chat request")
            return JsonResponse(
                {
                    "kind": "error",
                    "error": _("The chat model is temporarily unavailable."),
                },
                status=503,
            )
        except Exception:
            logger.exception("Chat service failed while processing a request")
            return JsonResponse(
                {
                    "kind": "error",
                    "error": _("The chat service is temporarily unavailable."),
                },
                status=503,
            )
        return JsonResponse(response.model_dump(mode="json"))
