from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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
    Crew,
    Flight,
    Order,
    Ticket,
)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name")


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name", "country")


class CityListSerializer(CitySerializer):
    country = serializers.SlugRelatedField(
        read_only=True,
        slug_field="name"
    )


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "name", "closest_big_city", "iata_code", "timezone")


class AirportListSerializer(AirportSerializer):
    closest_big_city = serializers.SlugRelatedField(
        read_only=True,
        slug_field="name"
    )


class RouteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")


class RouteListSerializer(RouteSerializer):
    source = serializers.SlugRelatedField(
        queryset=Airport.objects.all(),
        slug_field="name"
    )
    destination = serializers.SlugRelatedField(
        queryset=Airport.objects.all(),
        slug_field="name"
    )

    class Meta:
        model = Route
        fields = ("id", "source", "destination")


class AirplaneTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirplaneType
        fields = ("id", "name")


class AirplaneSerializer(serializers.ModelSerializer):
    total_rows = serializers.SerializerMethodField()
    total_seats = serializers.SerializerMethodField()
    standard_number_seats_in_row = serializers.SerializerMethodField()
    unusual_rows_with_seat_count = serializers.SerializerMethodField()

    class Meta:
        model = Airplane
        fields = (
            "id",
            "name",
            "airplane_type",
            "total_seats",
            "total_rows",
            'standard_number_seats_in_row',
            "unusual_rows_with_seat_count",
            "airline",
            "image"
        )

    def get_total_rows(self, obj):
        return obj.total_rows

    def get_total_seats(self, obj):
        return obj.total_seats

    def get_standard_number_seats_in_row(self, obj):
        return obj.standard_number_seats_in_row

    def get_unusual_rows_with_seat_count(self, obj):
        if obj.standard_number_seats_in_row is not None:
            return None
        else:
            return obj.unusual_rows_with_seat_count


class AirplaneListSerializer(AirplaneSerializer):
    airplane_type = serializers.SlugRelatedField(
        read_only=True,
        slug_field="name"
    )

    class Meta:
        model = Airplane
        fields = (
            "id",
            "name",
            "airplane_type",
            "total_seats",
            "total_rows",
            "airline",
            "image"
        )


class AirplaneCreateSerializer(serializers.ModelSerializer):
    total_rows = serializers.IntegerField(required=False)
    total_seats = serializers.IntegerField(required=False)
    row_seats_distribution = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    class Meta:
        model = Airplane
        fields = (
            "id",
            "name",
            "airplane_type",
            "airline",
            "total_rows",
            "total_seats",
            "row_seats_distribution"
        )

    def validate(self, attrs):
        data = super().validate(attrs)

        if "row_seats_distribution" in attrs:
            row_seats_distribution = attrs["row_seats_distribution"]
            Airplane.validate_airplane_unusual(
                row_seats_distribution,
                ValidationError
            )
        else:
            total_rows = attrs["total_rows"]
            total_seats = attrs["total_seats"]
            Airplane.validate_airplane_standard(
                total_rows,
                total_seats,
                ValidationError
            )

        return data

    def create(self, validated_data):
        total_rows = validated_data.pop("total_rows", None)
        total_seats = validated_data.pop("total_seats", None)
        row_seats_distribution = validated_data.pop(
            "row_seats_distribution",
            None
        )

        airplane_instance = super().create(validated_data)

        if total_rows and total_seats:
            self._create_standard_airplane(
                airplane_instance,
                total_rows,
                total_seats
            )
        elif row_seats_distribution:
            self._create_unusual_airplane(
                airplane_instance,
                row_seats_distribution
            )
        else:
            raise ValidationError("No seats data provided")

        return airplane_instance

    def _create_standard_airplane(self, airplane, total_rows, total_seats):
        seats_per_row = total_seats // total_rows
        for row in range(1, total_rows + 1):
            for seat_number in range(1, seats_per_row + 1):
                Seat.objects.create(
                    airplane=airplane,
                    row=row,
                    number=seat_number
                )

    def _create_unusual_airplane(self, airplane, row_seats_distribution):
        for index, seats in enumerate(row_seats_distribution):
            for seat_number in range(1, seats + 1):
                Seat.objects.create(
                    airplane=airplane,
                    row=index + 1,
                    number=seat_number
                )


class AirplaneImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airplane
        fields = ("id", "image")


class AirlineSerializer(serializers.ModelSerializer):
    fleet_size = serializers.SerializerMethodField()
    overall_rating = serializers.SerializerMethodField()
    average_boarding_deplaining_rating = serializers.SerializerMethodField()
    average_crew_rating = serializers.SerializerMethodField()
    average_services_rating = serializers.SerializerMethodField()
    average_entertainment_rating = serializers.SerializerMethodField()
    average_wi_fi_rating = serializers.SerializerMethodField()

    class Meta:
        model = Airline
        fields = (
            "id",
            "name",
            "headquarters",
            "web_site_address",
            "iata_code",
            "url_logo",
            "fleet_size",
            "overall_rating",
            "average_boarding_deplaining_rating",
            "average_crew_rating",
            "average_services_rating",
            "average_entertainment_rating",
            "average_wi_fi_rating"
        )

    def get_fleet_size(self, obj):
        return obj.fleet_size

    def get_overall_rating(self, obj):
        return obj.overall_rating.get("overall_rating", 0)

    def get_average_boarding_deplaining_rating(self, obj):
        return obj.overall_rating.get("avg_boarding_deplaining", 0)

    def get_average_crew_rating(self, obj):
        return obj.overall_rating.get("avg_crew", 0)

    def get_average_services_rating(self, obj):
        return obj.overall_rating.get("avg_services", 0)

    def get_average_entertainment_rating(self, obj):
        return obj.overall_rating.get("avg_entertainment", 0)

    def get_average_wi_fi_rating(self, obj):
        return obj.overall_rating.get("avg_wi_fi", 0)


class AirlineListSerializer(AirlineSerializer):
    class Meta:
        model = Airline
        fields = ("id", "name", "headquarters", "iata_code", "url_logo")


class AirlineRatingSerializer(serializers.ModelSerializer):
    airline_name = serializers.SlugRelatedField(
        queryset=Airline.objects.all(),
        source="airline",
        slug_field="name"
    )

    class Meta:
        model = AirlineRating
        fields = (
            "id",
            "airline_name",
            "boarding_deplaining_rating",
            "crew_rating",
            "services_rating",
            "entertainment_rating",
            "wi_fi_rating",
            "created_at"
        )


class CrewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crew
        fields = ("id", "first_name", "last_name")


class RouteDetailSerializer(RouteSerializer):
    source = serializers.SlugRelatedField(
        read_only=True,
        slug_field="name"
    )
    destination = serializers.SlugRelatedField(
        read_only=True,
        slug_field="name"
    )

    airlines = AirlineListSerializer()

    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance", "airlines")


class FlightSerializer(serializers.ModelSerializer):
    departure_time = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M"
    )
    estimated_arrival_time = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M"
    )
    actual_arrival_time = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M"
    )

    class Meta:
        model = Flight
        fields = "__all__"

    def validate(self, data):
        if data.get("status") in ["delayed", "ahead"] and \
                data.get("actual_arrival_time") is None:
            raise serializers.ValidationError(
                "Must update actual_arrival_time field "
                "if changing status to delayed or ahead"
            )

        if data.get("status") is "emergency" and \
                data.get("emergent_destination") is None:
            raise serializers.ValidationError(
                "Must update emergent_destination field "
                "if changing status to emergency")
        return data


class FlightListSerializer(FlightSerializer):
    route_source = serializers.CharField(
        source="route.source", read_only=True
    )
    route_destination = serializers.CharField(
        source="route.destination", read_only=True
    )
    departure_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    estimated_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    actual_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    airplane_total_seats = serializers.IntegerField(
        source="airplane.total_seats", read_only=True
    )
    tickets_available = serializers.SerializerMethodField()
    airline_logo = serializers.URLField(
        source="airplane.airline.url_logo", read_only=True, default=None
    )

    class Meta:
        model = Flight
        fields = (
            "id",
            "route_source",
            "route_destination",
            "departure_time",
            "estimated_arrival_time",
            "actual_arrival_time",
            "airplane_total_seats",
            "tickets_available",
            "airline_logo"
        )

    def get_tickets_available(self, obj):
        return obj.tickets_available


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("id", "seat_row", "seat_number", "flight", "ticket_type")

    def validate(self, attrs):
        data = super().validate(attrs)

        seat_row = attrs["seat_row"]
        seat_number = attrs["seat_number"]
        flight = attrs["flight"]

        Ticket.validate_ticket(
            seat_row,
            seat_number,
            flight,
            ValidationError
        )

        return data

    queryset = Ticket.objects.all()


class TicketListSerializer(TicketSerializer):
    flight = FlightListSerializer(many=False, read_only=True)


class TicketSeatsSerializer(TicketSerializer):
    class Meta:
        model = Ticket
        fields = ("seat_row", "seat_number")


class FlightDetailSerializer(serializers.ModelSerializer):
    airlines = serializers.SerializerMethodField()

    route = RouteDetailSerializer(read_only=True)
    airplane_name = serializers.CharField(
        source="airplane.name"
    )
    airplane_type = serializers.CharField(
        source="airplane.airplane_type"
    )
    departure_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    estimated_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    actual_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    taken_places = TicketSeatsSerializer(
        source="tickets",
        many=True,
        read_only=True
    )
    crews = CrewSerializer(many=True, read_only=True)

    class Meta:
        model = Flight
        fields = (
            "id",
            "route",
            "airplane_name",
            "airplane_type",
            "departure_time",
            "estimated_arrival_time",
            "actual_arrival_time",
            "airlines",
            "taken_places",
            "crews",
            "status",
            "emergent_destination"
        )

    def get_airlines(self, obj):
        route_serializer = RouteDetailSerializer(obj.route)
        return route_serializer.data["airlines"]


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(
        many=True,
        read_only=False,
        allow_null=False
    )

    class Meta:
        model = Order
        fields = ("id", "tickets", "created_at")

    def create(self, validated_data):
        with transaction.atomic():
            tickets_data = validated_data.pop("tickets")
            flight = tickets_data[0]["flight"]
            tickets_available = flight.tickets_available

            if tickets_available < len(tickets_data):
                raise serializers.ValidationError(
                    "Not enough tickets available"
                )

            order = Order.objects.create(**validated_data)

            for ticket_data in tickets_data:
                Ticket.objects.create(order=order, **ticket_data)

            return order


class OrderListSerializer(OrderSerializer):
    tickets = TicketListSerializer(many=True, read_only=True)
