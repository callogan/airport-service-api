from django.urls import path, include

from rest_framework import routers

from airport.views import (
    CountryViewSet,
    CityViewSet,
    AirportViewSet,
    RouteViewSet,
    AirplaneTypeViewSet,
    AirplaneViewSet,
    AirlineViewSet,
    FlightViewSet,
    OrderViewSet,
    AllocateTicketAPIView,
)

router = routers.DefaultRouter()
router.register("countries", CountryViewSet)
router.register("cities", CityViewSet)
router.register("airports", AirportViewSet)
router.register("routes", RouteViewSet)
router.register("airplane_types", AirplaneTypeViewSet)
router.register("airplanes", AirplaneViewSet)
router.register("airlines", AirlineViewSet)
router.register("flights", FlightViewSet)
router.register("orders", OrderViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "tickets/<int:ticket_id>/allocate/",
        AllocateTicketAPIView.as_view(),
        name="ticket_allocate"
    )
]

app_name = "airport"
