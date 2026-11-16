"""Denied HTML stays useful without exposing local DEBUG routing details."""
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.middleware import PrivateResponsesMiddleware
from .models import Event


@override_settings(DEBUG=True)
class PrivateNotFoundTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="error-owner")
        cls.other = get_user_model().objects.create_user(username="error-other")
        cls.event = Event.objects.create(owner=cls.owner, title="Secret foreign event", brief="Private context")

    def test_foreign_private_routes_keep_404_without_debug_details_or_inline_styles(self):
        self.client.force_login(self.other)
        for route in ("events:detail", "events:constraints", "events:preparation", "event_registration:manage"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=[self.event.pk]))
                self.assertContains(response, "No podemos abrir esta página", status_code=404)
                self.assertNotContains(response, "Secret foreign event", status_code=404)
                self.assertNotContains(response, "URL patterns", status_code=404)
                self.assertNotContains(response, "<style", status_code=404)
                self.assertNotContains(response, "style=", status_code=404)
                self.assertNotIn("unsafe-inline", response["Content-Security-Policy"])
                self.assertIn("no-store", response["Cache-Control"])

    def test_anonymous_unknown_url_is_generic_and_has_safe_return_link(self):
        response = self.client.get("/missing-page-for-qa/")
        self.assertContains(response, 'href="/"', status_code=404)
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertNotContains(response, "Request Method", status_code=404)


class JSONErrorTests(SimpleTestCase):
    def test_json_404_contract_is_not_replaced_by_html(self):
        original = JsonResponse({"error":"missing"}, status=404)
        response = PrivateResponsesMiddleware(lambda request: original)(RequestFactory().get("/api/missing/"))
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.content,b'{"error": "missing"}')
        self.assertEqual(response["Content-Type"],"application/json")
