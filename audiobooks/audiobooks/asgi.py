"""
ASGI config for audiobooks project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'audiobooks.settings')

django_application = get_asgi_application()

from store.mcp.auth import MCPJWTAuthMiddleware
from store.mcp.server import mcp

mcp_application = mcp.http_app(path="/", stateless_http=True)
protected_mcp_application = MCPJWTAuthMiddleware(mcp_application)

application = Starlette(
    routes=[
        Mount("/mcp", app=protected_mcp_application),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_application.lifespan,
)
