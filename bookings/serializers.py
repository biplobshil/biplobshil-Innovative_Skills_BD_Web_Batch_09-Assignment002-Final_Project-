from django.urls import reverse
from rest_framework import serializers

from events.models import Event

from .models import Booking
from .qr import qr_data_uri


class BookingCreateSerializer(serializers.Serializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    quantity = serializers.IntegerField(min_value=1, default=1)


class BookingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "location", "start_time", "end_time", "status"]


class BookingSerializer(serializers.ModelSerializer):
    event = BookingEventSerializer(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    is_checked_in = serializers.BooleanField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "ticket_code", "event", "user", "user_email", "user_name",
            "quantity", "unit_price", "total_price", "status",
            "is_checked_in", "checked_in_at", "qr_code_url",
            "created_at", "cancelled_at",
        ]
        read_only_fields = fields

    def get_qr_code_url(self, obj) -> str | None:
        """Link to the ticket's QR image. Cancelled bookings have no ticket."""
        if not obj.is_confirmed:
            return None
        url = reverse("booking-qr-code", args=[obj.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class BookingDetailSerializer(BookingSerializer):
    """Single booking, with the QR code embedded so it can be shown directly."""

    qr_code = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = [*BookingSerializer.Meta.fields, "qr_code"]
        read_only_fields = fields

    def get_qr_code(self, obj) -> str | None:
        """PNG image as a base64 data URI, usable as an <img> src."""
        return qr_data_uri(str(obj.ticket_code)) if obj.is_confirmed else None


class CheckInSerializer(serializers.Serializer):
    ticket_code = serializers.UUIDField(help_text="The value read from the ticket's QR code.")


class CheckInResultSerializer(serializers.Serializer):
    detail = serializers.CharField()
    booking = BookingSerializer()


class AttendeeSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source="id")
    name = serializers.CharField(source="user.get_full_name")
    email = serializers.EmailField(source="user.email")
    is_checked_in = serializers.BooleanField()
    checked_in_by = serializers.EmailField(source="checked_in_by.email", default=None)

    class Meta:
        model = Booking
        fields = [
            "booking_id", "name", "email", "quantity",
            "is_checked_in", "checked_in_at", "checked_in_by",
        ]


class AttendanceReportSerializer(serializers.Serializer):
    event = BookingEventSerializer()
    total_seats = serializers.IntegerField()
    available_seats = serializers.IntegerField()
    tickets_sold = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    checked_in_bookings = serializers.IntegerField()
    checked_in_tickets = serializers.IntegerField()
    not_checked_in_bookings = serializers.IntegerField()
    attendance_rate = serializers.FloatField(help_text="Percent of sold tickets checked in.")
    attendees = AttendeeSerializer(many=True)