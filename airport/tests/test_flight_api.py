from datetime import datetime

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

from airport.serializers import (
    FlightDetailSerializer,
    FlightListSerializer,
)

FLIGHT_URL = reverse("airport:flight-list")


def detail_url(flight_id):
    return reverse("airport:flight-detail", args=[flight_id])


class UnauthenticatedFlightApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

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
                    number=seat_number
                )
        cls.country_source = Country.objects.create(name="USA")
        cls.country_destination = Country.objects.create(name="Germany")
        cls.closest_big_city_source = City.objects.create(
            name="New York", country=cls.country_source
        )
        cls.closest_big_city_destination = City.objects.create(
            name="Berlin", country=cls.country_destination
        )
        cls.route_1 = Route.objects.create(
            source=Airport.objects.create(
                name="John F. Kennedy International Airport",
                iata_code="JFK",
                closest_big_city=cls.closest_big_city_source
            ),
            destination=Airport.objects.create(
                name="Berlin Tegel 'Otto Lilienthal' Airport",
                iata_code="TXL",
                closest_big_city=cls.closest_big_city_destination,
            )
        )
        cls.route_1.airlines.add(cls.airline.id)
        cls.country_source = Country.objects.create(name="Portugal")
        cls.country_destination = Country.objects.create(name="Poland")
        cls.closest_big_city_source = City.objects.create(
            name="Lisbon", country=cls.country_source
        )
        cls.closest_big_city_destination = City.objects.create(
            name="Warsaw", country=cls.country_destination
        )
        cls.route_2 = Route.objects.create(
            source=Airport.objects.create(
                name="Humberto Delgado Airport",
                iata_code="LIS",
                closest_big_city=cls.closest_big_city_source
            ),
            destination=Airport.objects.create(
                name="Warsaw Chopin Airport",
                iata_code="WAW",
                closest_big_city=cls.closest_big_city_destination,
            )
        )

        cls.route_2.airlines.add(cls.airline.id)

        cls.crew_1 = Crew.objects.create(
            first_name="Julie",
            last_name="Halliburton"
        )
        cls.crew_2 = Crew.objects.create(
            first_name="Jacob",
            last_name="McMullen"
        )

        cls.flight_1 = Flight.objects.create(
            airplane=cls.airplane,
            route=cls.route_1,
            departure_time="2024-05-02 07:00",
            estimated_arrival_time="2024-05-02 15:10"
        )
        cls.flight_1.crews.add(cls.crew_1.id)

        cls.flight_1.save()

        cls.flight_2 = Flight.objects.create(
            airplane=cls.airplane,
            route=cls.route_2,
            departure_time="2024-05-03 08:00",
            estimated_arrival_time="2024-05-03 12:00"
        )
        cls.flight_2.crews.add(cls.crew_2.id)
        cls.flight_2.save()

    def test_retrieve_flight_detail(self):
        url = detail_url(self.flight_1.id)
        resp = self.client.get(url)

        serializer = FlightDetailSerializer(self.flight_1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        for key in resp.data:
            if key != "airplane":
                self.assertEqual(resp.data[key], serializer.data[key])
            else:
                self.assertListEqual(
                    list(resp.data[key]),
                    list(serializer.data[key])
                )

    def test_list_flights(self):
        resp = self.client.get(FLIGHT_URL)
        flights = Flight.objects.all()
        serializer = FlightListSerializer(flights, many=True)

        for flight, serialized_flight in zip(flights, serializer.data):
            tickets_available = flight.tickets_available

            serialized_flight["tickets_available"] = tickets_available

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], serializer.data)

    def test_filter_flights_by_source_exist(self):
        target_source = self.flight_1.route.source

        route = Route.objects.create(
            source=target_source,
            destination=self.route_2.destination
        )

        route.airlines.add(self.airline.id)

        Flight.objects.create(
            airplane=self.airplane,
            route=route,
            departure_time="2022-07-04 09:00",
            estimated_arrival_time="2022-07-05 13:00"
        )

        resp = self.client.get(
            FLIGHT_URL,
            {"airport_from": target_source.name}
        )

        self.assertEqual(len(resp.data["results"]), 2)
        for flight in resp.data["results"]:
            self.assertEqual(flight["route_source"], str(target_source))

    def test_filter_flights_by_source_absent(self):
        target_source_name = "San Francisco International Airport"

        resp = self.client.get(FLIGHT_URL, {"airport_from": target_source_name})

        self.assertEqual(len(resp.data["results"]), 0)

    def test_filter_flights_by_destination_exist(self):
        target_destination = self.flight_2.route.destination

        route = Route.objects.create(
            source=self.route_1.source,
            destination=target_destination,
        )

        Flight.objects.create(
            airplane=self.airplane,
            route=route,
            departure_time="2024-05-04 10:00",
            estimated_arrival_time="2024-05-04 14:00"
        )

        resp = self.client.get(
            FLIGHT_URL,
            {"airport_to": target_destination.name}
        )

        self.assertEqual(len(resp.data["results"]), 2)
        for flight in resp.data["results"]:
            self.assertEqual(flight["route_destination"], str(target_destination))

    def test_filter_flights_by_destination_absent(self):
        target_destination_name = "Ministro Pistarini International Airport"

        resp = self.client.get(
            FLIGHT_URL,
            {"airport_to": target_destination_name}
        )

        self.assertEqual(len(resp.data["results"]), 0)

    def test_tickets_available_if_several_tickets_ordered(self):
        user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )
        order = Order.objects.create(user=user)
        Ticket.objects.create(
            flight=self.flight_1,
            order=order,
            seat_row=1,
            seat_number=1
        )
        Ticket.objects.create(
            flight=self.flight_2,
            order=order,
            seat_row=1,
            seat_number=1
        )
        Ticket.objects.create(
            flight=self.flight_2,
            order=order,
            seat_row=1,
            seat_number=2
        )

        total_seats_1 = self.flight_1.airplane.total_seats
        total_seats_2 = self.flight_2.airplane.total_seats
        tickets_ordered_1 = self.flight_1.tickets.count()
        tickets_ordered_2 = self.flight_2.tickets.count()

        resp = self.client.get(FLIGHT_URL)

        flight_1_data = resp.data["results"][0]
        flight_2_data = resp.data["results"][1]

        self.assertEqual(
            flight_1_data["tickets_available"],
            total_seats_1 - tickets_ordered_1
        )
        self.assertEqual(
            flight_2_data["tickets_available"],
            total_seats_2 - tickets_ordered_2
        )

    def test_tickets_available_if_all_tickets_ordered(self):
        user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )
        order = Order.objects.create(user=user)
        for seat_pair in self.flight_1.airplane.seats.all():
            Ticket.objects.create(
                flight=self.flight_1,
                order=order,
                seat_row=seat_pair.row,
                seat_number=seat_pair.number
            )

        resp = self.client.get(FLIGHT_URL)

        flight_data = resp.data["results"][0]

        self.assertEqual(flight_data["tickets_available"], 0)

    def test_create_flight_by_not_admin_is_forbidden(self):
        payload = {
            "airplane": self.airplane.id,
            "route": self.route_1.id,
            "departure_time": "2022-07-04 11:00",
            "estimated_arrival_time": "2022-07-05 19:10"
        }

        resp = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "testuser@gmail.com",
            "testpass"
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = refresh.access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        resp = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminFlightApiTests(TestCase):
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

    @classmethod
    def setUpTestData(cls):
        cls.airline = Airline.objects.create(name="Test airline 2")
        cls.airplane = Airplane.objects.create(
            name="Test airplane 2",
            airline=cls.airline,
            airplane_type=AirplaneType.objects.create(name="Test airplane type 2"),
        )
        for seat_row in range(1, 21):
            for seat_number in range(1, 7):
                Seat.objects.create(
                    airplane=cls.airplane,
                    row=seat_row,
                    number=seat_number,
                )
        cls.country_source = Country.objects.create(name="USA")
        cls.country_destination = Country.objects.create(name="Germany")
        cls.closest_big_city_source = City.objects.create(
            name="New York", country=cls.country_source
        )
        cls.closest_big_city_destination = City.objects.create(
            name="Berlin", country=cls.country_destination
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
        cls.source = cls.route.source

    def test_create_flight(self):
        payload = {
            "airplane": self.airplane.id,
            "route": self.route.id,
            "departure_time": "2024-05-04 11:30",
            "estimated_arrival_time": "2024-05-04 19:40",
            "crews": [self.crew.id]
        }

        resp = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        flight = Flight.objects.get(id=resp.data["id"])
        for key in ("airplane", "route"):
            self.assertEqual(payload[key], getattr(flight, key).id)
        for key in ("departure_time", "estimated_arrival_time"):
            self.assertEqual(
                payload[key], getattr(flight, key).strftime("%Y-%m-%d %H:%M")
            )

    def test_update_flight(self):
        flight = Flight.objects.create(
            airplane=self.airplane,
            route=self.route,
            departure_time=datetime(2024, 5, 5, 12, 30, 0),
            estimated_arrival_time=datetime(2024, 5, 5, 20, 40, 0)
        )
        flight.crews.add(self.crew.id)
        flight.save()

        country_source = Country.objects.create(name="Emergent country")
        closest_big_city_source = City.objects.create(
            name="Emergent city",
            country=country_source
        )
        self.route.emergent_destination = Airport.objects.create(
            name="Emergent airport",
            iata_code="PRG",
            closest_big_city=closest_big_city_source
        )
        self.route.save()

        payload = {
            "actual_arrival_time": datetime(2024, 5, 5, 21, 00, 0),
            "route": self.route.id
        }

        resp = self.client.patch(
            detail_url(flight.id),
            data=payload,
            format="json"
        )
        flight.refresh_from_db()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertEqual(
            payload["actual_arrival_time"].strftime('%Y-%m-%d %H:%M'),
            flight.actual_arrival_time.strftime('%Y-%m-%d %H:%M')
        )

        self.assertEqual(payload["route"], flight.route.id)
