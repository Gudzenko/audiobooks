import json

from asgiref.sync import sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from starlette.types import ASGIApp, Receive, Scope, Send


UNAUTHORIZED_BODY = json.dumps(
    {"error": "A valid access token for an active user is required."}
).encode("utf-8")


class MCPJWTAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.authentication = JWTAuthentication()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _extract_bearer_token(scope)
        if token is None:
            await _send_unauthorized(send)
            return

        try:
            validated_token = self.authentication.get_validated_token(token)
            user = await sync_to_async(
                self.authentication.get_user,
                thread_sensitive=True,
            )(validated_token)
        except (AuthenticationFailed, InvalidToken):
            await _send_unauthorized(send)
            return

        scope["user"] = user
        await self.app(scope, receive, send)


def _extract_bearer_token(scope: Scope) -> str | None:
    authorization = dict(scope.get("headers", [])).get(b"authorization", b"")
    scheme, separator, token = authorization.partition(b" ")
    if separator != b" " or scheme.lower() != b"bearer" or not token:
        return None
    try:
        return token.decode("utf-8")
    except UnicodeDecodeError:
        return None


async def _send_unauthorized(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(UNAUTHORIZED_BODY)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": UNAUTHORIZED_BODY})
