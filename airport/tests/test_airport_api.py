from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from airport.models import Airport, Country, City
from airport.serializers import AirportListSerializer

AIRPORT_URL = reverse("airport:airport-list")


def sample_airport(**kwargs):
    name = kwargs.get("name")
    iata_code = kwargs.get("iata_code")
    closest_big_city = kwargs.get("closest_big_city")

    defaults = {
        "name": name,
        "iata_code": iata_code,
        "closest_big_city": closest_big_city
    }
    defaults.update(kwargs)

    return Airport.objects.create(**defaults)


class UnauthenticatedAirportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")

    def test_auth_required(self):
        resp = self.client.get(AIRPORT_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass",
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_airports(self):
        country_source = Country.objects.create(name="USA")
        closest_big_city = City.objects.create(
            name="New York",
            country=country_source
        )
        sample_airport(
            name="John F. Kennedy International Airport",
            iata_code="JFK",
            closest_big_city=closest_big_city
        )

        country_source = Country.objects.create(name="Germany")
        closest_big_city = City.objects.create(
            name="Berlin",
            country=country_source
        )
        sample_airport(
            name="Berlin Tegel 'Otto Lilienthal' Airport",
            iata_code="TXL",
            closest_big_city=closest_big_city
        )

        resp = self.client.get(AIRPORT_URL)

        airports = Airport.objects.order_by("id")
        serializer = AirportListSerializer(airports, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for resp_data, serializer_data in zip(resp.data, serializer.data):
            self.assertEqual(
                resp_data["id"],
                serializer_data["id"]
            )
            self.assertEqual(
                resp_data["name"],
                serializer_data["name"]
            )
            self.assertEqual(
                resp_data["closest_big_city"],
                serializer_data["closest_big_city"]
            )
            self.assertEqual(
                resp_data["iata_code"],
                serializer_data["iata_code"]
            )

    def test_create_airport_forbidden(self):
        country_source = Country.objects.create(name="Country 1")
        closest_big_city = City.objects.create(
            name="City 1",
            country=country_source
        )

        payload = {
            "name": "Test airport 1",
            "iata_code": "YUL",
            "closest_big_city": closest_big_city,
        }

        resp = self.client.post(AIRPORT_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminAirportApiTests(TestCase):
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

    def test_create_airport(self):
        country_source = Country.objects.create(name="Country 2")
        closest_big_city = City.objects.create(
            name="City 2",
            country=country_source
        )

        payload = {
            "name": "Test airport 2",
            "iata_code": "WAW",
            "closest_big_city": closest_big_city.id
        }

        resp = self.client.post(AIRPORT_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        airport = Airport.objects.get(id=resp.data["id"])

        self.assertEqual(
            payload["name"],
            airport.name
        )
        self.assertEqual(
            payload["closest_big_city"],
            airport.closest_big_city.id
        )
        self.assertEqual(
            payload["iata_code"],
            airport.iata_code
        )
