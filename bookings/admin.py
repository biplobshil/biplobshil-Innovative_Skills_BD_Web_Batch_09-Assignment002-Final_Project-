from django.contrib import admin

from . import services
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "id", "event", "user", "quantity", "total_price",
        "status", "checked_in_at", "created_at",
    ]
    list_filter = ["status", "event"]
    search_fields = ["user__email", "event__title", "ticket_code"]
    actions = ["cancel_selected"]

    # Bookings are created through the API so seat counts always stay correct.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def delete_model(self, request, obj):
        services.delete_booking(booking=obj)

    def delete_queryset(self, request, queryset):
        for booking in queryset:
            services.delete_booking(booking=booking)

    @admin.action(description="Cancel selected bookings and release their seats")
    def cancel_selected(self, request, queryset):
        cancelled = 0
        for booking in queryset.filter(status=Booking.Status.CONFIRMED):
            services.cancel_booking(booking=booking, cancelled_by=request.user)
            cancelled += 1
        self.message_user(request, f"{cancelled} booking(s) cancelled.")