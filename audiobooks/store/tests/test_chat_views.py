from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ChatPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="chat@example.com",
            username="chat-user",
            password="test-password",
        )

    def test_chat_page_requires_login(self):
        response = self.client.get(reverse("chat"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_authenticated_user_can_open_chat(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("chat"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("chat_message"))
        self.assertContains(response, "chat.js")
        self.assertNotContains(response, "Ask a question about the library.")

    def test_chat_link_is_only_visible_to_authenticated_users(self):
        anonymous_response = self.client.get(reverse("home"))
        self.assertNotContains(anonymous_response, reverse("chat"))

        self.client.force_login(self.user)
        authenticated_response = self.client.get(reverse("home"))
        self.assertContains(authenticated_response, reverse("chat"))
