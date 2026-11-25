import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from ..chat.rate_limit import (
    ChatRateLimitExceeded,
    ChatRequestInProgress,
    limit_chat_requests,
)


class ChatRateLimitTests(SimpleTestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.settings_override = override_settings(
            CHAT_RATE_LIMIT_DIR=self.temp_directory.name,
            CHAT_REQUESTS_PER_MINUTE=2,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_rejects_parallel_request_for_same_user(self):
        with limit_chat_requests(1):
            with self.assertRaises(ChatRequestInProgress):
                with limit_chat_requests(1):
                    pass

    def test_releases_active_request_after_completion(self):
        with limit_chat_requests(1):
            pass

        with limit_chat_requests(1):
            pass

    def test_limits_requests_within_one_minute(self):
        with limit_chat_requests(1):
            pass
        with limit_chat_requests(1):
            pass

        with self.assertRaises(ChatRateLimitExceeded):
            with limit_chat_requests(1):
                pass

    def test_state_contains_no_message_content(self):
        with limit_chat_requests(1):
            pass

        state = Path(self.temp_directory.name, "user-1.json").read_text()
        self.assertNotIn("message", state)
