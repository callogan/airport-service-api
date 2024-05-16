from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from airport.models import AirplaneType
from airport.serializers import AirplaneTypeSerializer

AIRPLANE_TYPE_URL = reverse("airport:airplanetype-list")


def sample_airplane_type(**kwargs):
    defaults = {
        "name": "Test airplane type basic",
    }
    defaults.update(kwargs)

    return AirplaneType.objects.create(**defaults)


class UnauthenticatedAirplaneTypeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")
        resp = self.client.get(AIRPLANE_TYPE_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirplaneTypeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass",
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_airplane_types(self):
        sample_airplane_type()
        sample_airplane_type(name="Test airplane type 2")

        resp = self.client.get(AIRPLANE_TYPE_URL)

        airplane_types = AirplaneType.objects.order_by("id")
        serializer = AirplaneTypeSerializer(airplane_types, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, serializer.data)

    def test_create_airplane_type_forbidden(self):
        payload = {
            "name": "Test airplane type 3",
        }

        resp = self.client.post(AIRPLANE_TYPE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminAirplaneTypeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testadmin@gmail.com",
            "testpass",
            is_staff=True
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_airplane_type(self):
        payload = {
            "name": "Test airplane type 4",
        }

        resp = self.client.post(AIRPLANE_TYPE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        airplane_type = AirplaneType.objects.get(id=resp.data["id"])
        self.assertEqual(payload["name"], getattr(airplane_type, "name"))
