from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
    AirlineRating,
    Flight,
)

from airport.serializers import AirlineListSerializer

AIRLINE_URL = reverse("airport:airline-list")
AIRLINE_RATING_URL = reverse("airport:airlinerating-list")
FLIGHT_URL = reverse("airport:flight-list")


def sample_airline(**kwargs):
    defaults = {
        "name": "Test airline basic"
    }
    defaults.update(kwargs)

    return Airline.objects.create(**defaults)


def sample_flight(**kwargs):
    airplane_type = AirplaneType.objects.create(name="Test type")
    airline = kwargs.pop("airline")
    airplane = Airplane.objects.create(
        name="Azure", airline=airline, airplane_type=airplane_type
    )
    for seat_row in range(1, 21):
        for seat_number in range(1, 7):
            Seat.objects.create(
                airplane=airplane,
                row=seat_row,
                number=seat_number
            )
    country_source = Country.objects.create(name="Country 1")
    closest_big_city_source = City.objects.create(
        name="City 1",
        country=country_source
    )
    source = Airport.objects.create(
        name="Source airport",
        iata_code="JFK",
        closest_big_city=closest_big_city_source
    )
    country_destination = Country.objects.create(name="Country 2")
    closest_big_city_destination = City.objects.create(
        name="City 2",
        country=country_destination
    )
    destination = Airport.objects.create(
        name="Destination airport",
        iata_code="SFO",
        closest_big_city=closest_big_city_destination
    )
    route = Route.objects.create(
        source=source,
        destination=destination
    )

    initial_data = {
        "departure_time": "2024-05-03 11:00:00",
        "estimated_arrival_time": "2024-05-03 17:45:00",
        "airplane": airplane,
        "route": route
    }
    initial_data.update(kwargs)

    return Flight.objects.create(**initial_data)


class UnauthenticatedAirlineApiTests(TestCase):
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
        resp = self.client.get(AIRLINE_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirlineApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_airlines(self):
        sample_airline()
        sample_airline(name="Test airline 2")

        resp = self.client.get(AIRLINE_URL)

        airlines = Airline.objects.order_by("id")
        serializer = AirlineListSerializer(airlines, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], serializer.data)

    def test_create_airline_forbidden(self):
        payload = {
            "name": "Test airline 3"
        }
        resp = self.client.post(AIRLINE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminAirlineApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testadmin@gmail.com",
            "testpass",
            is_staff=True
        )
        self.airline = sample_airline()
        self.flight = sample_flight(airline=self.airline)
        self.flight.save()
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_airline(self):
        payload = {
            "name": "Test airline 4",
            "headquarters": "New York City",
            "web_site_address": "http://www.luxuryairline.com",
            "iata_code": "DL",
            "url_logo": "https://depositary.com/Test_luxury_airline_logo.svg"
        }
        resp = self.client.post(AIRLINE_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        airline = Airline.objects.get(id=resp.data["id"])
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(airline, key))

    def test_create_airline_rating(self):
        airline = Airline.objects.create(
            name="Test airline 5",
            headquarters='Philadelphia',
            web_site_address="http://www.affordableairline.com",
            iata_code='1234',
            url_logo="https://depositary.com/Test_affordable_airline_logo.svg"
        )

        payload = {
            "airline_id": airline.id,
            "airline_name": airline.name,
            "boarding_deplaining_rating": 4,
            "crew_rating": 5,
            "services_rating": 3,
            "entertainment_rating": 4,
            "wi_fi_rating": 2,
        }

        resp = self.client.post(AIRLINE_RATING_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        airline_rating = AirlineRating.objects.get(id=resp.data["id"])

        for key in (
                "airline_id",
                "boarding_deplaining_rating",
                "crew_rating",
                "services_rating",
                "entertainment_rating",
                "wi_fi_rating"
        ):
            self.assertEqual(payload[key], getattr(airline_rating, key))

    def test_average_ratings_calculation(self):
        airline = Airline.objects.create(name="Test airline 6")

        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=2,
            crew_rating=4,
            services_rating=3,
            entertainment_rating=5,
            wi_fi_rating=4
        )

        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=3,
            crew_rating=5,
            services_rating=4,
            entertainment_rating=4,
            wi_fi_rating=1
        )

        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=4,
            crew_rating=3,
            services_rating=2,
            entertainment_rating=3,
            wi_fi_rating=4
        )

        url = reverse(
            "airport:airline-detail",
            kwargs={"pk": airline.id}
        )
        resp = self.client.get(url)
        data = resp.json()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(data["average_boarding_deplaining_rating"], 3.0)
        self.assertEqual(data["average_crew_rating"], 4.0)
        self.assertEqual(data["average_services_rating"], 3.0)
        self.assertEqual(data["average_entertainment_rating"], 4.0)
        self.assertEqual(data["average_wi_fi_rating"], 3.0)

    def test_overall_rating_calculation(self):
        airline = Airline.objects.create(name="Test airline 7")

        rating_1 = AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=2,
            crew_rating=4,
            services_rating=3,
            entertainment_rating=5,
            wi_fi_rating=3
        )

        rating_2 = AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=5,
            crew_rating=4,
            services_rating=3,
            entertainment_rating=5,
            wi_fi_rating=5
        )

        url = reverse(
            "airport:airline-detail",
            kwargs={"pk": airline.id}
        )
        resp = self.client.get(url)
        data = resp.json()

        avg_boarding_deplaining = (
            rating_1.boarding_deplaining_rating +
            rating_2.boarding_deplaining_rating
        ) / 2
        avg_crew = (
            rating_1.crew_rating +
            rating_2.crew_rating
        ) / 2
        avg_services = (
            rating_1.services_rating +
            rating_2.services_rating
        ) / 2
        avg_entertainment = (
            rating_1.entertainment_rating +
            rating_2.entertainment_rating
        ) / 2
        avg_wi_fi = (
            rating_1.wi_fi_rating +
            rating_2.wi_fi_rating
        ) / 2

        WEIGHTS = {
            "avg_boarding_deplaining": 0.05,
            "avg_crew": 0.2,
            "avg_services": 0.15,
            "avg_entertainment": 0.1,
            "avg_wi_fi": 0.05
        }

        overall_rating = (
            avg_boarding_deplaining * WEIGHTS["avg_boarding_deplaining"] +
            avg_crew * WEIGHTS["avg_crew"] +
            avg_services * WEIGHTS["avg_services"] +
            avg_entertainment * WEIGHTS["avg_entertainment"] +
            avg_wi_fi * WEIGHTS["avg_wi_fi"]
        ) / (
            WEIGHTS["avg_boarding_deplaining"] +
            WEIGHTS["avg_crew"] +
            WEIGHTS["avg_services"] +
            WEIGHTS["avg_entertainment"] +
            WEIGHTS["avg_wi_fi"]
        )

        expected_rating = round(overall_rating, 1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(data["overall_rating"], expected_rating)

    def test_ratings_update(self):
        airline = Airline.objects.create(name="Test airline 8")

        # creating 2 rating objects for initial average ratings calculation
        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=4,
            crew_rating=3,
            services_rating=5,
            entertainment_rating=2,
            wi_fi_rating=3
        )

        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=5,
            crew_rating=5,
            services_rating=4,
            entertainment_rating=4,
            wi_fi_rating=5
        )

        url = reverse(
            "airport:airline-detail",
            kwargs={"pk": airline.id}
        )
        response = self.client.get(url)
        data = response.json()

        avg_boarding_deplaining_old = data["average_boarding_deplaining_rating"]
        avg_crew_old = data["average_crew_rating"]
        avg_services_old = data["average_services_rating"]
        avg_entertainment_old = data["average_entertainment_rating"]
        avg_wi_fi_old = data["average_wi_fi_rating"]
        overall_rating_old = data["overall_rating"]

        # creating new rating object to recalculate average ratings values
        AirlineRating.objects.create(
            airline=airline,
            boarding_deplaining_rating=3,
            crew_rating=3,
            services_rating=2,
            entertainment_rating=4,
            wi_fi_rating=1
        )

        resp = self.client.get(url)
        data = resp.json()

        avg_boarding_deplaining_new = data["average_boarding_deplaining_rating"]
        avg_crew_new = data["average_crew_rating"]
        avg_services_new = data["average_services_rating"]
        avg_entertainment_new = data["average_entertainment_rating"]
        avg_wi_fi_new = data["average_wi_fi_rating"]
        overall_rating_new = data["overall_rating"]

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            avg_boarding_deplaining_old,
            avg_boarding_deplaining_new
        )
        self.assertNotEqual(avg_crew_old, avg_crew_new)
        self.assertNotEqual(avg_services_old, avg_services_new)
        self.assertNotEqual(avg_entertainment_old, avg_entertainment_new)
        self.assertNotEqual(avg_wi_fi_old, avg_wi_fi_new)
        self.assertNotEqual(overall_rating_old, overall_rating_new)
