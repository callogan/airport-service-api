import os
import uuid
import pytz

from django.conf import settings
from django.db import models
from django.db.models import Count, Max, Avg
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim


class Country(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "country"
        verbose_name_plural = "countries"


class City(models.Model):
    name = models.CharField(max_length=64)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE
    )

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "city"
        verbose_name_plural = "cities"


class Airport(models.Model):
    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]

    name = models.CharField(max_length=255)
    closest_big_city = models.ForeignKey(
        City,
        on_delete=models.CASCADE
    )
    iata_code = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        unique=True,
        verbose_name="IATA code"
    )
    timezone = models.CharField(
        max_length=63,
        default="UTC",
        choices=TIMEZONE_CHOICES
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.closest_big_city}) - {self.iata_code}"


class Airline(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name="Name"
    )
    headquarters = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Headquarters"
    )
    iata_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name="IATA code"
    )
    web_site_address = models.URLField(
        blank=True,
        null=True,
        verbose_name="Web-site address"
    )
    url_logo = models.URLField(
        blank=True,
        null=True,
        verbose_name="URL logo"
    )

    def __str__(self) -> str:
        return self.name

    @property
    def fleet_size(self):
        return self.airplanes.count()

    @property
    def overall_rating(self):
        WEIGHTS = {
            "avg_boarding_deplaining": 0.05,
            "avg_crew": 0.2,
            "avg_services": 0.15,
            "avg_entertainment": 0.1,
            "avg_wi_fi": 0.05,
        }

        rating_per_category = self.ratings.filter(airline=self).aggregate(
            avg_boarding_deplaining=Avg("boarding_deplaining_rating"),
            avg_crew=Avg("crew_rating"),
            avg_services=Avg("services_rating"),
            avg_entertainment=Avg("entertainment_rating"),
            avg_wi_fi=Avg("wi_fi_rating"),
        )

        total_score = 0
        total_weight = 0

        result_dict = {"overall_rating": 0}

        for category, rating in rating_per_category.items():
            value = rating
            if value is None:
                continue
            weight = WEIGHTS.get(category, 0)

            total_score += value * weight
            total_weight += weight

            result_dict[category] = round(value, 1)

        if total_weight > 0:
            result_dict["overall_rating"] = round(
                total_score / total_weight,
                1
            )
        return result_dict


class AirlineRating(models.Model):
    SCORE_CHOICES = [
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5")
    ]

    boarding_deplaining_rating = models.SmallIntegerField(
        choices=SCORE_CHOICES,
        default=0,
        blank=True,
        null=True
    )
    crew_rating = models.SmallIntegerField(
        choices=SCORE_CHOICES,
        default=0,
        blank=True,
        null=True
    )
    services_rating = models.SmallIntegerField(
        choices=SCORE_CHOICES,
        default=0,
        blank=True,
        null=True
    )
    entertainment_rating = models.SmallIntegerField(
        choices=SCORE_CHOICES,
        default=0,
        blank=True,
        null=True
    )
    wi_fi_rating = models.SmallIntegerField(
        choices=SCORE_CHOICES,
        default=0,
        blank=True,
        null=True
    )
    airline = models.ForeignKey(
        Airline,
        related_name="ratings",
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Route(models.Model):
    source = models.ForeignKey(
        Airport,
        related_name="source_routes",
        on_delete=models.CASCADE
    )
    destination = models.ForeignKey(
        Airport,
        related_name="destination_routes",
        on_delete=models.CASCADE
    )
    distance = models.IntegerField(
        blank=True,
        null=True
    )
    airlines = models.ManyToManyField(
        Airline,
        related_name="routes",
        blank=True
    )

    def calculate_distance(self):
        try:
            geolocator = Nominatim(user_agent="distance_calculator")

            location1 = geolocator.geocode(
                f"{self.source.closest_big_city.name}, "
                f"{self.source.closest_big_city.country.name}"
            )
            latitude1 = location1.latitude
            longitude1 = location1.longitude

            location2 = geolocator.geocode(
                f"{self.destination.closest_big_city.name}, "
                f"{self.destination.closest_big_city.country.name}"
            )
            latitude2 = location2.latitude
            longitude2 = location2.longitude

            distance = geodesic(
                (latitude1, longitude1), (latitude2, longitude2)
            ).kilometers

            return int(distance)
        except (GeocoderTimedOut, GeocoderUnavailable, Exception):
            return 0

    def save(self, *args, **kwargs):
        if not self.distance:
            self.distance = self.calculate_distance()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.source.closest_big_city} - " \
               f"{self.destination.closest_big_city}"


class AirplaneType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


def airplane_image_file_path(instance, filename):
    _, extension = os.path.splitext(filename)
    filename = f"{slugify(instance.name)}-{uuid.uuid4()}{extension}"

    return os.path.join("uploads", "airplanes", filename)


class Airplane(models.Model):
    name = models.CharField(max_length=255)
    airplane_type = models.ForeignKey(
        AirplaneType,
        related_name="airplanes",
        on_delete=models.CASCADE
    )
    airline = models.ForeignKey(
        Airline,
        related_name="airplanes",
        on_delete=models.CASCADE
    )
    image = models.ImageField(
        blank=True,
        null=True,
        upload_to=airplane_image_file_path
    )

    def __str__(self) -> str:
        return self.name

    @property
    def total_rows(self):
        return self.seats.values("row").distinct().count()

    @property
    def total_seats(self):
        return self.seats.count()

    @property
    def unusual_rows_with_seat_count(self):
        return (
            Seat.objects.filter(airplane_id=self.pk)
            .values("row")
            .annotate(seat_count=Count("id"))
        )

    @property
    def standard_number_seats_in_row(self):
        seat_counts = [
            row_data["seat_count"]
            for row_data in self.unusual_rows_with_seat_count
        ]
        if len(set(seat_counts)) == 1:
            return seat_counts[0]
        return None

    @staticmethod
    def validate_airplane_standard(total_rows, total_seats, error):
        if total_rows <= 0 or total_seats <= 0:
            raise error({"error": "Total rows and total seats must be > 0"})

        if total_seats % total_rows != 0:
            raise error({
                "error": "Total seats must be divisible by total rows"
            })

    @staticmethod
    def validate_airplane_unusual(row_seats_distribution, error):
        if (
            any(seats <= 0 for seats in row_seats_distribution)
            or not row_seats_distribution
        ):
            raise error(
                {
                    "error": (
                        "Rows and seats distribution must be > 0, "
                        "and seat distribution list must not be empty"
                    )
                }
            )


class Seat(models.Model):
    row = models.IntegerField()
    number = models.IntegerField()
    airplane = models.ForeignKey(
        Airplane,
        related_name="seats",
        on_delete=models.CASCADE
    )


class Crew(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Flight(models.Model):
    STATUS_CHOICES = [
        ("normal", "Normal"),
        ("canceled", "Canceled"),
        ("delayed", "Delayed"),
        ("ahead", "Ahead"),
        ("emergency", "Emergency")
    ]

    route = models.ForeignKey(
        Route,
        related_name="flights",
        on_delete=models.CASCADE
    )
    emergent_destination = models.OneToOneField(
        Airport,
        blank=True,
        null=True,
        on_delete=models.CASCADE
    )
    airplane = models.ForeignKey(
        Airplane,
        on_delete=models.CASCADE
    )
    crews = models.ManyToManyField(
        Crew,
        related_name="flights"
    )
    departure_time = models.DateTimeField()
    estimated_arrival_time = models.DateTimeField()
    actual_arrival_time = models.DateTimeField(
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="normal"
    )

    def __str__(self):
        return f"{self.route}; " \
               f"{self.departure_time} - {self.estimated_arrival_time}"

    @property
    def tickets_available(self):
        tickets = Ticket.objects.filter(flight=self)
        airplanes = Airplane.objects.filter(flight=self)

        rows_with_seat_count = airplanes.values("seats__row").annotate(
            seat_count=Count("id")
        )

        sold_tickets = tickets.count()

        total_seats = sum(row["seat_count"] for row in rows_with_seat_count)
        available_tickets = max(0, total_seats - sold_tickets)

        return available_tickets


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{str(self.created_at.strftime('%Y-%m-%d %H:%M'))}"


class Ticket(models.Model):
    TYPE_CHOICES = [
        ("check-in-pending", "Check-in-pending"),
        ("check-in-completed", "Check-in-completed")
    ]

    order = models.ForeignKey(
        Order,
        related_name="tickets",
        on_delete=models.CASCADE
    )
    seat_row = models.IntegerField(
        blank=True,
        null=True
    )
    seat_number = models.IntegerField(
        blank=True,
        null=True
    )
    ticket_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="check-in-completed"
    )
    flight = models.ForeignKey(
        Flight,
        related_name="tickets",
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{str(self.flight)} " \
               f"(row: {self.seat_row}, seat: {self.seat_number})"

    @staticmethod
    def validate_ticket(seat_row, seat_number, flight, error_to_raise):
        airplane = flight.airplane

        if seat_row is not None:
            # Check if row exists for the specified airplane
            matching_rows = Seat.objects.filter(
                airplane=airplane,
                row=seat_row
            )

            if not matching_rows.exists():
                raise error_to_raise(
                    {
                        "row": (
                            f"Row {seat_row} does not exist "
                            "in the specified airplane."
                        )
                    }
                )

            # If row is valid, check seat
            if seat_number is not None:
                matching_seats = matching_rows.filter(number=seat_number)

                if not matching_seats.exists():
                    raise error_to_raise(
                        {
                            "seat": (
                                f"Seat {seat_number} does not exist "
                                f"in row {seat_row} in the specified airplane."
                            )
                        }
                    )

            # Check if there are no existing tickets
            # with the same row and seat for the specified flight
            existing_tickets = Ticket.objects.filter(
                flight=flight, seat_row=seat_row, seat_number=seat_number
            )
            if existing_tickets.exists():
                raise error_to_raise(
                    {
                        "row": (
                            f"Ticket with row {seat_row} "
                            f"and seat {seat_number} already exists "
                            f"for the specified flight."
                        )
                    }
                )

    def allocate_seat(self):
        # automated allocation logic, for example, by check-in
        if self.ticket_type == "check-in-pending":
            seat_row, seat_number = self.get_last_available_seat()
            if seat_row is not None and seat_number is not None:
                self.seat_row = seat_row  # Assigning the row to the ticket
                self.seat_number = (
                    seat_number  # Assigning the seat number to the ticket
                )
                self.ticket_type = "check-in-completed"
                self.save()

    def get_last_available_seat(self):
        airplane = self.flight.airplane

        # Basically there is a related Seat model with a field seat_number
        # and it has a foreign key to Airplane
        rows = (
            Seat.objects.filter(airplane=airplane)
            .values_list("row", flat=True)
            .distinct()
            .order_by("row")
        )

        # Iterate through each row
        for row in rows:
            booked_seats_in_row = Ticket.objects.filter(
                flight=self.flight, seat_row=row
            )

            # max number of seat in row
            max_seat_in_row = self.get_max_seat_in_row()

            # first free seat in a row
            for seat_number in range(1, max_seat_in_row + 1):
                if not booked_seats_in_row.filter(
                    seat_number=seat_number
                ).exists():
                    return row, seat_number
                    # If available seat is found, exit the loop
                    break

            return None, None

    def get_max_seat_in_row(self):
        # Get the related Airplane for the current Ticket
        airplane = self.flight.airplane

        # Leveraging relationship: there is a related Seat model
        # with a field seat_number
        # and it has a foreign key to Airplane
        max_seat_in_row = (
            Seat.objects.filter(airplane=airplane)
            .values("row")
            .annotate(max_seat=Count("number"))
            .aggregate(Max("max_seat"))
        )["max_seat__max"]

        return max_seat_in_row

    def clean(self):
        Ticket.validate_ticket(
            self.seat_row,
            self.seat_number,
            self.flight,
            ValidationError
        )

    def save(
        self,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None
    ):
        self.full_clean()
        return super(Ticket, self).save(
            force_insert,
            force_update,
            using,
            update_fields
        )
