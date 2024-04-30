from django.contrib import admin

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


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country")


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("name", "closest_big_city")
    list_filter = ("closest_big_city",)
    search_fields = ("name",)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("source", "destination")
    list_filter = ("source",)


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 1


@admin.register(Airplane)
class AirplaneAdmin(admin.ModelAdmin):
    inlines = [
        SeatInline,
    ]

    readonly_fields = ["total_rows"]

    @admin.display(description="total_rows")
    def total_rows(self, obj):
        return obj.total_rows


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "headquarters",
        "iata_code",
        "web_site_address",
        "url_logo"
    )


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name")


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "airplane",
        "departure_time",
        "estimated_arrival_time",
        "actual_arrival_time"
    )
    list_filter = ("route",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "flight",
        "seat_row",
        "seat_number"
    )
    list_filter = ("flight__route",)


admin.site.register(Country)
admin.site.register(AirplaneType)
admin.site.register(Order)
