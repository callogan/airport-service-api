import pytz
from django.conf import settings
from django.db import models
from django.db.models import Count
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from rest_framework.exceptions import ValidationError


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
    flight = models.ForeignKey(
        Flight,
        related_name="tickets",
        on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seat_row", "seat_number", "flight"],
                name="unique_row_seat_flight",
            )
        ]

    def __str__(self):
        return f"{str(self.flight)} " \
               f"(row: {self.seat_row}, seat: {self.seat_number})"

    @staticmethod
    def validate_ticket(seat_row, seat_number, flight, error_to_raise):
        airplane = flight.airplane

        if seat_row is not None:
            # Check if row exists for the given aircraft
            matching_rows = Seat.objects.filter(
                airplane=airplane,
                row=seat_row
            )

            if not matching_rows.exists():
                raise error_to_raise(
                    {
                        "row": (
                            f"Row number {seat_row} does not exist "
                            "for the specified airplane."
                        )
                    }
                )

            # If row is valid, check seat_number
            if seat_number is not None:
                matching_seats = matching_rows.filter(number=seat_number)

                if not matching_seats.exists():
                    raise error_to_raise(
                        {
                            "seat": (
                                f"Seat number {seat_number} does not exist "
                                f"for the specified airplane "
                                f"and row {seat_row}."
                            )
                        }
                    )

            # Check if there are no existing tickets
            # with the specified row and seat for the given flight
            existing_tickets = Ticket.objects.filter(
                flight=flight, seat_number=seat_number, seat_row=seat_row
            )
            if existing_tickets.exists():
                raise error_to_raise(
                    {
                        "row": (
                            f"Ticket with row number {seat_row} "
                            f"and seat {seat_number} already exists "
                            f"for the specified flight."
                        )
                    }
                )

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
