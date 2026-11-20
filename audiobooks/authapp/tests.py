from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationSmokeTests(TestCase):
    def setUp(self):
        self.password = "test-password"
        self.user = get_user_model().objects.create_user(
            email="reader@example.com",
            username="reader",
            password=self.password,
        )

    def test_login_page_is_available(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_user_can_authenticate_by_email(self):
        user = authenticate(email=self.user.email, password=self.password)

        self.assertEqual(user, self.user)

    def test_user_can_authenticate_by_username(self):
        user = authenticate(username=self.user.username, password=self.password)

        self.assertEqual(user, self.user)

    def test_profile_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("profile"))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("profile")}',
        )

    def test_authenticated_profile_is_available(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.user)

    def test_jwt_token_can_be_issued(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": self.user.email, "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
