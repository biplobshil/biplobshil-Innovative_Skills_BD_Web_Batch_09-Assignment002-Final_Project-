from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsOrganizerOrAdmin
from events.models import Event

from . import services
from .filters import BookingFilter
from .models import Booking
from .qr import qr_png
from .serializers import (
    AttendanceReportSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingSerializer,
    CheckInResultSerializer,
    CheckInSerializer,
)


def get_managed_event(request, event_id):
    """Return the event if the user is an admin or the event's own organizer."""
    event = get_object_or_404(Event, pk=event_id)
    if not (request.user.is_admin or event.organizer_id == request.user.id):
        raise PermissionDenied("Only the event's organizer or an admin can perform this action.")
    return event


@extend_schema_view(
    list=extend_schema(summary="My booking history (admins see every booking)"),
    retrieve=extend_schema(summary="Get one booking, including its QR code"),
    destroy=extend_schema(summary="Delete a booking permanently (admin)"),
)
@extend_schema(tags=["Bookings"])
class BookingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = BookingFilter
    search_fields = ["event__title", "user__email"]
    ordering_fields = ["created_at", "total_price", "event__start_time"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), IsAdmin()]
        if self.action == "check_in":
            return [IsAuthenticated(), IsOrganizerOrAdmin()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in ("create", "retrieve"):
            return BookingDetailSerializer
        return BookingSerializer

    def get_queryset(self):
        """
        Users only ever see their own bookings and admins see all of them.
        An organizer can additionally open single bookings of their own events.
        """
        queryset = Booking.objects.select_related("event", "user")
        user = self.request.user
        if not user.is_authenticated or user.is_admin:
            return queryset
        own = Q(user=user)
        if self.action in ("retrieve", "qr_code") and user.is_organizer:
            own |= Q(event__organizer=user)
        return queryset.filter(own)

    @extend_schema(
        summary="Book tickets for an event",
        request=BookingCreateSerializer,
        responses={201: BookingDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.create_booking(user=request.user, **serializer.validated_data)
        data = self.get_serializer(booking).data
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        services.delete_booking(booking=instance)

    @extend_schema(
        summary="Cancel a booking and release its seats",
        request=None,
        responses=BookingSerializer,
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = services.cancel_booking(booking=self.get_object(), cancelled_by=request.user)
        return Response(self.get_serializer(booking).data)

    @extend_schema(
        summary="Download the ticket QR code (PNG image)",
        responses={(200, "image/png"): OpenApiTypes.BINARY},
    )
    @action(detail=True, url_path="qr-code")
    def qr_code(self, request, pk=None):
        booking = self.get_object()
        if not booking.is_confirmed:
            return Response(
                {"detail": "Cancelled bookings do not have a ticket."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = HttpResponse(qr_png(str(booking.ticket_code)), content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="ticket-{booking.pk}.png"'
        response["Cache-Control"] = "private, no-store"
        return response

    @extend_schema(
        tags=["Check-in"],
        summary="Check in an attendee by scanning their QR code (organizer / admin)",
        request=CheckInSerializer,
        responses={200: CheckInResultSerializer},
    )
    @action(detail=False, methods=["post"], url_path="check-in", filterset_class=None)
    def check_in(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.check_in(
            ticket_code=serializer.validated_data["ticket_code"], checked_in_by=request.user
        )
        data = BookingSerializer(booking, context=self.get_serializer_context()).data
        return Response({"detail": "Check-in successful.", "booking": data})


@extend_schema(tags=["Events"], summary="List bookings of an event (its organizer / admin)")
class EventBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOrganizerOrAdmin]
    filterset_class = BookingFilter
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    ordering_fields = ["created_at", "quantity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        event = get_managed_event(self.request, self.kwargs["event_id"])
        return Booking.objects.filter(event=event).select_related("event", "user")


@extend_schema(
    tags=["Check-in"],
    summary="Attendance report of an event (its organizer / admin)",
    parameters=[
        OpenApiParameter(
            "checked_in", bool, description="Only list attendees who have / have not checked in."
        )
    ],
    responses=AttendanceReportSerializer,
)
class EventAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizerOrAdmin]

    def get(self, request, event_id):
        event = get_managed_event(request, event_id)
        confirmed = Q(status=Booking.Status.CONFIRMED)
        checked_in = confirmed & Q(checked_in_at__isnull=False)
        totals = event.bookings.aggregate(
            confirmed_bookings=Count("id", filter=confirmed),
            cancelled_bookings=Count("id", filter=Q(status=Booking.Status.CANCELLED)),
            tickets_sold=Sum("quantity", filter=confirmed, default=0),
            checked_in_bookings=Count("id", filter=checked_in),
            checked_in_tickets=Sum("quantity", filter=checked_in, default=0),
        )
        sold = totals["tickets_sold"]

        attendees = (
            event.bookings.filter(confirmed)
            .select_related("user", "checked_in_by")
            .order_by("checked_in_at", "created_at")
        )
        only = request.query_params.get("checked_in", "").lower()
        if only in ("true", "1"):
            attendees = attendees.filter(checked_in_at__isnull=False)
        elif only in ("false", "0"):
            attendees = attendees.filter(checked_in_at__isnull=True)

        report = {
            "event": event,
            "total_seats": event.total_seats,
            "available_seats": event.available_seats,
            **totals,
            "not_checked_in_bookings": totals["confirmed_bookings"] - totals["checked_in_bookings"],
            "attendance_rate": round(totals["checked_in_tickets"] / sold * 100, 2) if sold else 0.0,
            "attendees": attendees,
        }
        return Response(AttendanceReportSerializer(report).data)