import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken
from starlette.testclient import TestClient

from audiobooks.asgi import application
from store.models import Author, Book


BASE_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
}


class MCPHTTPIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="mcp@example.com",
            username="mcp-user",
            password="test-password",
        )
        self.access_token = str(AccessToken.for_user(self.user))
        self.author = Author.objects.create(first_name="Isaac", last_name="Asimov")
        self.book = Book.objects.create(title="Foundation")
        self.book.authors.add(self.author)
        self.client_context = TestClient(application)
        self.client = self.client_context.__enter__()
        self.addCleanup(self.client_context.__exit__, None, None, None)

    def test_initialize_returns_server_information(self):
        result = self._post_mcp(
            method="initialize",
            params={
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "integration-test", "version": "1"},
            },
        )

        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertEqual(result["serverInfo"]["name"], "Audiobooks Library")
        self.assertIn("tools", result["capabilities"])

    def test_tools_list_exposes_registered_tools(self):
        result = self._post_mcp(method="tools/list", params={})

        self.assertEqual(
            [tool["name"] for tool in result["tools"]],
            [
                "search_books",
                "search_authors",
                "search_genres",
                "search_series",
                "get_item",
                "summarize_books",
                "suggest_items",
            ],
        )

    def test_tools_call_reads_from_django_database(self):
        result = self._post_mcp(
            method="tools/call",
            params={
                "name": "search_books",
                "arguments": {
                    "filters": {"author_ids": [self.author.id]},
                },
            },
        )

        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["total"], 1)
        self.assertEqual(
            result["structuredContent"]["items"][0]["title"],
            "Foundation",
        )

    def test_missing_token_is_rejected(self):
        response = self._raw_post(headers=BASE_MCP_HEADERS)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_invalid_token_is_rejected(self):
        response = self._raw_post(
            headers={**BASE_MCP_HEADERS, "Authorization": "Bearer wrong-token"}
        )

        self.assertEqual(response.status_code, 401)

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self._raw_post(
            headers={
                **BASE_MCP_HEADERS,
                "Authorization": f"Bearer {self.access_token}",
            }
        )

        self.assertEqual(response.status_code, 401)

    def _post_mcp(self, *, method, params):
        response = self.client.post(
            "/mcp/",
            headers=self._authenticated_headers(),
            json=self._payload(method=method, params=params),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream")

        data_line = next(
            line for line in response.text.splitlines() if line.startswith("data: ")
        )
        payload = json.loads(data_line.removeprefix("data: "))
        self.assertNotIn("error", payload)
        return payload["result"]

    def _raw_post(self, *, headers):
        return self.client.post(
            "/mcp/",
            headers=headers,
            json=self._payload(method="tools/list", params={}),
        )

    def _authenticated_headers(self):
        return {
            **BASE_MCP_HEADERS,
            "Authorization": f"Bearer {self.access_token}",
        }

    @staticmethod
    def _payload(*, method, params):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
