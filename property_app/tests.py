from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse

class LocationAutocompleteAPITests(SimpleTestCase):
    def setUp(self):
        self.url = reverse("location_autocomplete")

    @patch("property_app.api_views.semantic_location_search")
    def test_valid_query_returns_locations(self, mock_search):
        mock_search.return_value = [
            SimpleNamespace(
                id=5,
                name="Umeda",
                city="Umeda",
                state="Osaka",
                country="Japan",
                distance=0.0,
            )
        ]

        response = self.client.get(
            self.url,
            {"q": "Umeda", "limit": "3"},
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["query"], "Umeda")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Umeda")
        self.assertEqual(data["results"][0]["distance"], 0.0)

        mock_search.assert_called_once_with("Umeda", limit=3)

    @patch("property_app.api_views.semantic_location_search")
    def test_default_limit(self, mock_search):
        mock_search.return_value = []
        response = self.client.get(self.url, {"q": "Tokyo"})

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once_with("Tokyo", limit=5)

    def test_invalid_parameters_return_400(self):
        invalid_requests = [
            {},
            {"q": ""},
            {"q": "a"},
            {"q": "12345"},
            {"q": "Tokyo", "limit": "0"},
            {"q": "Tokyo", "limit": "11"},
            {"q": "Tokyo", "limit": "abc"},
        ]
        for parameters in invalid_requests:
            with self.subTest(parameters=parameters):
                response = self.client.get(
                    self.url,
                    parameters,
                )
                self.assertEqual(response.status_code, 400)

    def test_post_method_is_not_allowed(self):
        response = self.client.post(
            self.url,
            {"q": "Tokyo"},
        )

        self.assertEqual(response.status_code, 405)