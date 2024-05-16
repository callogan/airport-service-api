import json

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
    Crew,
    Flight,
    Order,
    Ticket,
)

from airport.serializers import OrderListSerializer

ORDER_URL = reverse("airport:order-list")


class UnauthenticatedOrderApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required_to_get_order_list(self):
        resp = self.client.get(ORDER_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_required_to_create(self):
        user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )

        payload = {
            "user": user.id
        }

        resp = self.client.post(ORDER_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedOrderApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser1@gmail.com",
            "testpass1"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    @classmethod
    def setUpTestData(cls):
        cls.airline = Airline.objects.create(name="Test airline")
        cls.airplane = Airplane.objects.create(
            name="Test airplane",
            airline=cls.airline,
            airplane_type=AirplaneType.objects.create(name="Test airplane type"),
        )
        for seat_row in range(1, 21):
            for seat_number in range(1, 16):
                Seat.objects.create(
                    airplane=cls.airplane,
                    row=seat_row,
                    number=seat_number,
                )
        cls.country_source = Country.objects.create(name="USA")
        cls.country_destination = Country.objects.create(name="Germany")
        cls.closest_big_city_source = City.objects.create(
            name="New York",
            country=cls.country_source
        )
        cls.closest_big_city_destination = City.objects.create(
            name="Berlin",
            country=cls.country_destination
        )
        cls.route = Route.objects.create(
            source=Airport.objects.create(
                name="John F. Kennedy International Airport",
                iata_code="JFK",
                closest_big_city=cls.closest_big_city_source
            ),
            destination=Airport.objects.create(
                name="Berlin Tegel 'Otto Lilienthal' Airport",
                iata_code="TXL",
                closest_big_city=cls.closest_big_city_destination
            )
        )

        cls.route.airlines.add(cls.airline.id)

        cls.crew = Crew.objects.create(
            first_name="Julie",
            last_name="Halliburton"
        )

        cls.flight = Flight.objects.create(
            airplane=cls.airplane,
            route=cls.route,
            departure_time="2024-05-02 13:00",
            estimated_arrival_time="2024-05-02 21:10"
        )
        cls.flight.crews.add(cls.crew.id)

        cls.flight.save()

    def test_list_orders(self):
        Order.objects.create(user=self.user)
        Order.objects.create(user=self.user)

        resp = self.client.get(ORDER_URL)

        orders = Order.objects.all()
        serializer = OrderListSerializer(orders, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], serializer.data)

    def test_filter_list_orders_by_current_user(self):
        user_2 = get_user_model().objects.create_user(
            "testuser2@gmail.com",
            "testpass2"
        )

        Order.objects.create(user=self.user)
        Order.objects.create(user=self.user)

        Order.objects.create(user=user_2)
        Order.objects.create(user=user_2)

        resp = self.client.get(ORDER_URL)

        orders = Order.objects.filter(user=self.user)
        serializer = OrderListSerializer(orders, many=True)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], serializer.data)

    def test_create_order(self):
        payload = {
            "tickets": [
                {
                    "seat_row": 1,
                    "seat_number": 1,
                    "flight": self.flight.id
                },
                {
                    "seat_row": 1,
                    "seat_number": 2,
                    "flight": self.flight.id
                }
            ]
        }
        payload = json.dumps(payload)
        resp = self.client.post(
            ORDER_URL, data=payload, content_type="application/json"
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_ticket_unique_constraint(self):
        order = Order.objects.create(user=self.user)
        existing_ticket = Ticket.objects.create(
            seat_row=1,
            seat_number=1,
            flight=self.flight,
            order=order
        )

        payload = {
            "tickets": [
                {
                    "seat_row": 1,
                    "seat_number": 1,
                    "flight": self.flight.id
                }
            ]
        }

        payload = json.dumps(payload)

        resp = self.client.post(
            ORDER_URL, data=payload, content_type="application/json"
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            f"Ticket with row {existing_ticket.seat_row} "
            f"and seat {existing_ticket.seat_number} "
            f"already exists for the specified flight.",
            resp.data["tickets"][0]["row"]
        )
