import tempfile

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from airport.models import (
    Country,
    City,
    Airport,
    Route,
    AirplaneType,
    Airplane,
    Seat,
    Airline,
    Flight,
    airplane_image_file_path
)

from airport.serializers import AirplaneListSerializer

AIRPLANE_URL = reverse("airport:airplane-list")


def image_upload_url(airplane_id):
    return reverse("airport:airplane-upload-image", args=[airplane_id])


def sample_airline(**kwargs):
    defaults = {
        "name": "Test airline basic"
    }
    defaults.update(kwargs)

    return Airline.objects.create(**defaults)


def sample_flight(**kwargs):
    airplane_type = AirplaneType.objects.create(name="Test type 1")
    airline = kwargs.pop("airline")
    airplane = Airplane.objects.create(
        name="Azure",
        airline=airline,
        airplane_type=airplane_type
    )
    for seat_row in range(1, 21):
        for seat_number in range(1, 7):
            Seat.objects.create(
                airplane=airplane,
                row=seat_row,
                number=seat_number,
            )

    country_source = Country.objects.create(name="Country 1")
    closest_big_city_source = City.objects.create(
        name="City 1",
        country=country_source
    )
    source = Airport.objects.create(
        name="Source airport",
        iata_code="SEA",
        closest_big_city=closest_big_city_source
    )
    country_destination = Country.objects.create(name="Country 2")
    closest_big_city_destination = City.objects.create(
        name="City 2",
        country=country_destination
    )
    destination = Airport.objects.create(
        name="Destination airport",
        iata_code="IAH",
        closest_big_city=closest_big_city_destination
    )
    route = Route.objects.create(
        source=source,
        destination=destination
    )

    defaults = {
        "departure_time": "2024-05-02 08:30:00",
        "estimated_arrival_time": "2024-05-02 12:50:00",
        "airplane": airplane,
        "route": route
    }

    defaults.update(kwargs)

    return Flight.objects.create(**defaults)


def sample_airplane_standard(**kwargs):
    airline = Airline.objects.create(name="Test airline 2")
    airplane_type = AirplaneType.objects.create(
        name="Test type 2"
    )

    defaults = {
        "name": "Test airplane name st_d",
        "airplane_type": airplane_type,
        "airline": airline
    }

    defaults.update(kwargs)

    airplane = Airplane.objects.create(
        name="Beige",
        airline=airline,
        airplane_type=airplane_type
    )

    for seat_row in range(1, 21):
        for seat_number in range(1, 7):
            Seat.objects.create(
                airplane=airplane,
                row=seat_row,
                number=seat_number
            )

    return airplane


def sample_airplane_unusual(**kwargs):
    airline = Airline.objects.create(name="Test airline 3")
    airplane_type = AirplaneType.objects.create(
        name="Test type 3"
    )

    defaults = {
        "name": "Test airpane name un_l",
        "airplane_type": airplane_type,
        "airline": airline
    }
    defaults.update(kwargs)

    airplane = Airplane.objects.create(
        name="Crimson", airline=airline, airplane_type=airplane_type
    )

    for seat_row in range(1, 21):
        num_seat_numbers = seat_row % 5 + 1
        seat_numbers = range(1, num_seat_numbers + 1)

        for seat_number in seat_numbers:
            Seat.objects.create(
                airplane=airplane,
                row=seat_row,
                number=seat_number
            )

    return airplane


class UnauthenticatedAirportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")

    def test_auth_required(self):
        resp = self.client.get(AIRPLANE_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )

        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_airplanes(self):
        sample_airplane_standard()

        airplane_type = AirplaneType.objects.create(
            name="Test type 4"
        )
        airline = Airline.objects.create(name="Test airline 4")

        data = {
            "name": "Test airplane name 2",
            "airplane_type": airplane_type,
            "airline": airline
        }
        airplane = Airplane.objects.create(**data)

        for seat_row in range(1, 21):
            num_seat_numbers = seat_row % 5 + 1
            seat_numbers = range(1, num_seat_numbers + 1)

            for seat_number in seat_numbers:
                Seat.objects.create(
                    airplane=airplane,
                    row=seat_row,
                    number=seat_number
                )

        resp = self.client.get(AIRPLANE_URL)

        airplanes = Airplane.objects.order_by("id")
        serializer = AirplaneListSerializer(airplanes, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for res_data, serializer_data in zip(resp.data, serializer.data):
            self.assertEqual(
                res_data["id"],
                serializer_data["id"]
            )
            self.assertEqual(
                res_data["name"],
                serializer_data["name"]
            )
            self.assertEqual(
                res_data["airplane_type"],
                serializer_data["airplane_type"]
            )
            self.assertEqual(
                res_data["total_seats"],
                serializer_data["total_seats"]
            )
            self.assertEqual(
                res_data["total_rows"],
                serializer_data["total_rows"]
            )
            self.assertEqual(
                res_data["image"],
                serializer_data["image"]
            )

    def test_create_airplane_forbidden(self):
        airline = Airline.objects.create(name="Test airline 5")
        airplane_type = AirplaneType.objects.create(
            name="Test type 5"
        )

        payload = {
            "name": "Test airplane name 3",
            "airplane_type": airplane_type.id,
            "airline": airline.id,
            "total_rows": 40,
            "total_seats": 200
        }

        resp = self.client.post(AIRPLANE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminAirplaneApiTests(TestCase):
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

    def test_create_airplane(self):
        airline = Airline.objects.create(name="Test airline 6")
        airplane_type = AirplaneType.objects.create(
            name="Test type 6"
        )

        payload = {
            "name": "Test airplane name 4",
            "airline": airline.id,
            "airplane_type": airplane_type.id,
            "total_rows": 40,
            "total_seats": 160
        }

        resp = self.client.post(AIRPLANE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        airplane = Airplane.objects.get(id=resp.data["id"])
        self.assertEqual(payload["name"], airplane.name)
        self.assertEqual(payload["total_rows"], airplane.total_rows)
        self.assertEqual(payload["total_seats"], airplane.total_seats)
        self.assertEqual(payload["airline"], airplane.airline.id)
        self.assertEqual(payload["airplane_type"], airplane.airplane_type.id)


class AirplaneImageUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            "testadmin@gmail.com",
            "testpass"
        )
        self.client.force_authenticate(self.user)
        self.airplane = sample_airplane_standard()
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_upload_image_to_airplane(self):
        """
        Test uploading an image to specific airline.
        """
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            resp = self.client.post(url, {"image": ntf}, format="multipart")

        self.airplane.refresh_from_db()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("image", resp.data)

        uploaded_image = self.airplane.image
        self.assertTrue(uploaded_image.file)

    def test_airplane_image_file_path(self):
        """
        Test the correctness of the path for uploading
        image file to specific airline.
        """
        filename = "test_image.jpg"
        result_path = airplane_image_file_path(self.airplane, filename)

        self.assertTrue(slugify(self.airplane.name) in result_path)

        uuid_part = result_path.split(
            slugify(self.airplane.name)
        )[1].split(".jpg")[0]

        self.assertEqual(len(uuid_part), 37)
        self.assertTrue(
            all(
                c.isdigit() or c.isalpha() or c in "-_" for c in uuid_part
            )
        )
        self.assertTrue(slugify(self.airplane.name) in result_path)
