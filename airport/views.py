from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from airport.models import (
    Country,
    City,
    Airport,
    Airplane,
    AirplaneType,
    Route,
    Airline,
    AirlineRating,
    Crew,
    Flight,
    Order,
    Ticket,
)

from airport.permissions import (
    IsAdminOrIfAuthenticatedReadOnly,
    ReadOnlyOrAdminPermission
)

from airport.serializers import (
    CountrySerializer,
    CitySerializer,
    CityListSerializer,
    AirportSerializer,
    AirportListSerializer,
    AirplaneTypeSerializer,
    AirplaneListSerializer,
    AirplaneSerializer,
    AirplaneCreateSerializer,
    AirplaneImageSerializer,
    RouteSerializer,
    RouteListSerializer,
    RouteDetailSerializer,
    AirlineSerializer,
    AirlineListSerializer,
    AirlineRatingSerializer,
    CrewSerializer,
    FlightSerializer,
    FlightListSerializer,
    FlightDetailSerializer,
    OrderSerializer,
    OrderListSerializer,
    TicketSerializer,
)


class CountryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet
):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer


class CityViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet
):
    queryset = City.objects.select_related("country")
    serializer_class = CitySerializer

    def get_serializer_class(self):
        if self.action == "list":
            return CityListSerializer

        return CitySerializer


class AirportViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet
):
    queryset = Airport.objects.select_related("closest_big_city")
    serializer_class = AirportSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return AirportListSerializer

        return AirportSerializer


class AirplaneTypeViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = AirplaneType.objects.all()
    serializer_class = AirplaneTypeSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class AirplaneViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    queryset = Airplane.objects.select_related("airplane_type")
    serializer_class = AirplaneSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return AirplaneListSerializer
        if self.action == "create":
            return AirplaneCreateSerializer
        if self.action == "upload_image":
            return AirplaneImageSerializer

        return AirplaneSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-image",
        permission_classes=[IsAdminUser],
    )
    def upload_image(self, request, pk=None):
        """
        Endpoint for uploading an image to specific airline.
        """
        airplane = self.get_object()
        serializer = self.get_serializer(airplane, data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class AirlineViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    pagination_class = PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 10

    queryset = Airline.objects.all()
    serializer_class = AirlineSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return AirlineListSerializer

        return AirlineSerializer

    @action(
        methods=["GET"],
        detail=True,
        url_path="airplanes",
        permission_classes=[IsAdminUser],
    )
    def airplanes(self, request, pk=None):
        """
        Endpoint for retrieving the list of all airplanes
        belonging to specific airline.
        """
        airline = self.get_object()
        airplanes = airline.airplanes.all()

        page = self.paginator.paginate_queryset(airplanes, request)

        serializer = AirplaneSerializer(page, many=True)
        paginated_response = self.paginator.get_paginated_response(
            serializer.data
        )
        return paginated_response


class AirlineRatingPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100


class AirlineRatingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AirlineRating.objects.all()
    serializer_class = AirlineRatingSerializer
    pagination_class = AirlineRatingPagination
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_queryset(self):
        airline_name = self.request.query_params.get("airline_name")

        if airline_name:
            self.queryset = self.queryset.filter(
                airline__name__icontains=airline_name
            )

        return self.queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="airline",
                description="Airline_name is required query parameter "
                            "to access the list of ratings for the specified "
                            "airline, otherwise such access will be denied.",
                required=True)
        ]
    )
    def list(self, request, *args, **kwargs):
        if "airline_name" in request.query_params:
            return super().list(request, *args, **kwargs)
        else:
            return Response(
                {"status": "Query parameter 'airline_name' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )


class CrewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Crew.objects.all()
    serializer_class = CrewSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class RouteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Route.objects.select_related("source", "destination")
    serializer_class = RouteSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return RouteListSerializer

        if self.action == "retrieve":
            return RouteDetailSerializer

        return RouteSerializer

    def get_queryset(self):
        country_from = self.request.query_params.get("country_from")
        country_to = self.request.query_params.get("country_to")
        city_from = self.request.query_params.get("city_from")
        city_to = self.request.query_params.get("city_to")
        route = self.request.query_params.get("route")

        if country_from:
            self.queryset = self.queryset.filter(
                source__closest_big_city__country__name__icontains=country_from
            )

        if country_to:
            self.queryset = self.queryset.filter(
                destination__closest_big_city__country__name__icontains=(
                    country_to
                )
            )

        if city_from:
            self.queryset = self.queryset.filter(
                source__closest_big_city__name__icontains=city_from
            )

        if city_to:
            self.queryset = self.queryset.filter(
                source__closest_big_city__name__icontains=city_to
            )

        if route:
            route = route.split("-")
            self.queryset = self.queryset.filter(
                Q(source__closest_big_city__name__icontains=route[0]),
                Q(destination__closest_big_city__name__icontains=route[-1]),
            )
        return self.queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="country_from",
                description="Filter by country of the departure "
                            "(ex. ?country_from=USA)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="country_to",
                description="Filter by country of the destination "
                            "(ex. ?country_to=Germany)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="city_from",
                description="Filter by city of the departure "
                            "(ex. ?city_from=New York)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="city_to",
                description="Filter by city of the destination "
                            "(ex. ?city_to=Berlin)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="route",
                description="Filter by city of the departure & city "
                            "of the destination (ex. ?route=New York-Berlin)",
                type=OpenApiTypes.STR
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response


class FlightPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100


class FlightViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        Flight.objects.select_related(
            "airplane",
            "route__source__closest_big_city",
            "route__destination__closest_big_city"
        )
        .prefetch_related("crews", "route__airlines")
    )
    serializer_class = FlightSerializer
    pagination_class = FlightPagination
    permission_classes = (ReadOnlyOrAdminPermission,)

    def get_serializer_class(self):
        if self.action == "list":
            return FlightListSerializer

        if self.action == "retrieve":
            return FlightDetailSerializer

        return FlightSerializer

    def get_queryset(self):
        airport_from = self.request.query_params.get("airport_from")
        airport_to = self.request.query_params.get("airport_to")
        date = self.request.query_params.get("date")

        if airport_from:
            self.queryset = self.queryset.filter(
                route__source__name__icontains=airport_from
            )

        if airport_to:
            self.queryset = self.queryset.filter(
                route__destination__name__icontains=airport_to
            )

        if date:
            date = datetime.strptime(date, "%Y-%m-%d").date()
            self.queryset = self.queryset.filter(departure_time__date=date)

        return self.queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="airport_from",
                description="Filter by airport of the departure "
                            "(ex. ?airport_from=JFK)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="airport_to",
                description="Filter by airport of the destination "
                            "(ex. ?airport_to=Berlin Central)",
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name="date",
                description="Filter by date of the departure "
                            "(ex. ?date=2024-03-18)",
                type=OpenApiTypes.DATE
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class OrderPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Order.objects.prefetch_related(
        "tickets__flight__airplane",
        "tickets__flight__route"
    )
    serializer_class = OrderSerializer
    pagination_class = OrderPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer

        return OrderSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AllocateSeatTicketAPIView(GenericAPIView):
    serializer_class = TicketSerializer
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        description="This method allocates the seat for the ticket "
                    "by providing both row and number parameters. "
                    "Such allocation occurs upon successful completion "
                    "of the check-in procedure prior to boarding the flight. "
                    "AllocateSeatTicketAPIView with method patch "
                    "is specifically designed only for implementing "
                    "the functionality of allocating seats for tickets "
                    "with a status of 'check-in-pending'.",
        responses={status.HTTP_200_OK: TicketSerializer}
    )
    def patch(self, request, ticket_id):
        try:
            ticket = Ticket.objects.get(pk=ticket_id)
        except ObjectDoesNotExist as e:
            return Response(
                {"error": f"Ticket not found: {e}"},
                status=status.HTTP_404_NOT_FOUND
            )

        if ticket.ticket_type == "check-in-completed":
            return Response(
                {"error": "Seat is already allocated"},
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket.allocate_seat()

        serializer = TicketSerializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)
