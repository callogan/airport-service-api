from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
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


def allocate_url(ticket_id):
    return reverse("airport:ticket-allocate-seat", args=[ticket_id])


class AuthenticatedTicketApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser_basic@gmail.com",
            "testpass"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    @classmethod
    def setUpTestData(cls):
        cls.client = APIClient()
        cls.user = get_user_model().objects.create_user(
            "testuser_for_order@gmail.com",
            "testpass"
        )
        cls.airline = Airline.objects.create(name="Test airline")
        cls.airplane = Airplane.objects.create(
            name="Test airplane",
            airline=cls.airline,
            airplane_type=AirplaneType.objects.create(name="Test airplane type"),
        )
        for seat_row in range(1, 21):
            for seat_number in range(1, 7):
                Seat.objects.create(
                    airplane=cls.airplane,
                    row=seat_row,
                    number=seat_number,
                )
        country_source = Country.objects.create(name="USA")
        country_destination = Country.objects.create(name="Germany")
        closest_big_city_source = City.objects.create(
            name="New York",
            country=country_source
        )
        closest_big_city_destination = City.objects.create(
            name="Berlin",
            country=country_destination
        )
        airport = Airport.objects.create(
            name="John F. Kennedy International Airport",
            iata_code="JFK",
            closest_big_city=closest_big_city_source
        )
        cls.route = Route.objects.create(
            source=airport,
            destination=Airport.objects.create(
                name="Berlin Tegel 'Otto Lilienthal' Airport",
                iata_code="TXL",
                closest_big_city=closest_big_city_destination
            )
        )
        cls.route.airlines.add(cls.airline.id)
        cls.flight = Flight.objects.create(
            airplane=cls.airplane,
            route=cls.route,
            departure_time=datetime(2024, 5, 2, 12, 30, 0),
            estimated_arrival_time=datetime(2024, 5, 2, 20, 40, 0),
        )

        crew = Crew.objects.create(
            first_name="John",
            last_name="Doe"
        )
        cls.flight.crews.add(crew.id)
        cls.flight.save()

        cls.order = Order.objects.create(user=cls.user)

        cls.ticket_allocated = Ticket(
            seat_number=1,
            seat_row=1,
            flight=cls.flight,
            order=cls.order
        )
        cls.ticket_allocated.save()

        cls.ticket_not_allocated = Ticket(
            flight=cls.flight,
            order=cls.order,
            ticket_type="check-in-pending"
        )
        cls.ticket_not_allocated.save()

    def test_validate_seat_for_ticket_not_exist(self):
        seat_row = 18
        seat_number = 21
        message = f"Seat {seat_number} does not exist " \
                  f"in row {seat_row} in the specified airplane."

        with self.assertRaisesMessage(ValidationError, message):
            self.ticket_allocated.validate_ticket(
                seat_row,
                seat_number,
                self.flight,
                ValidationError
            )

    def test_validate_row_for_ticket_not_exist(self):
        seat_row = 35
        seat_number = 5
        message = f"Row {seat_row} does not exist " \
                  f"in the specified airplane."

        with self.assertRaisesMessage(ValidationError, message):
            self.ticket_allocated.validate_ticket(
                seat_row,
                seat_number,
                self.flight,
                ValidationError
            )

    def test_validate_ticket_with_valid_row_and_seat(self):
        seat_row = 18
        seat_number = 5

        self.assertIsNone(
            self.ticket_allocated.validate_ticket(
                seat_row,
                seat_number,
                self.flight,
                ValidationError
            )
        )

    def test_allocate_seat_for_ticket(self):
        payload = {
            "seat_row": 1,
            "seat_number": 2
        }

        resp = self.client.patch(
            allocate_url(self.ticket_not_allocated.id),
            data=payload
        )

        self.ticket_not_allocated.refresh_from_db()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            payload["seat_row"],
            self.ticket_not_allocated.seat_row
        )
        self.assertEqual(
            payload["seat_number"],
            self.ticket_not_allocated.seat_number
        )
