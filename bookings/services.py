"""
Booking business rules.

Every function that touches seat counts runs inside a transaction and updates
the counter with an F() expression, so two simultaneous requests can never
oversell an event or give seats back twice.
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from config.exceptions import Conflict
from events.models import Event

from .models import Booking


@transaction.atomic
def create_booking(*, user, event, quantity):
    event = Event.objects.select_for_update().get(pk=event.pk)

    if event.status != Event.Status.PUBLISHED:
        raise ValidationError({"event": "This event is not open for booking."})
    if event.has_started:
        raise ValidationError({"event": "This event has already started."})
    if quantity > event.max_tickets_per_booking:
        raise ValidationError(
            {"quantity": f"You can book at most {event.max_tickets_per_booking} tickets per booking."}
        )

    # Decrease the seats only if enough are left. This single UPDATE is what
    # prevents overselling.
    updated = Event.objects.filter(pk=event.pk, available_seats__gte=quantity).update(
        available_seats=F("available_seats") - quantity
    )
    if not updated:
        raise Conflict(f"Not enough seats available. Seats left: {event.available_seats}.")

    return Booking.objects.create(
        user=user,
        event=event,
        quantity=quantity,
        unit_price=event.price,
        total_price=event.price * quantity,
    )


def _release_seats(booking):
    Event.objects.filter(pk=booking.event_id).update(
        available_seats=F("available_seats") + booking.quantity
    )


@transaction.atomic
def cancel_booking(*, booking, cancelled_by):
    booking = Booking.objects.select_for_update().select_related("event").get(pk=booking.pk)

    if not (cancelled_by.is_admin or booking.user_id == cancelled_by.id):
        raise PermissionDenied("You can only cancel your own bookings.")
    if not booking.is_confirmed:
        raise Conflict("This booking is already cancelled.")
    if booking.is_checked_in:
        raise Conflict("This ticket has already been used for check-in.")
    if booking.event.has_started and not cancelled_by.is_admin:
        raise ValidationError({"detail": "Bookings cannot be cancelled after the event has started."})

    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancelled_at", "updated_at"])
    _release_seats(booking)
    return booking


@transaction.atomic
def delete_booking(*, booking):
    """Admin-only hard delete. Seats of a still-confirmed booking are released."""
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.is_confirmed:
        _release_seats(booking)
    booking.delete()


def check_in(*, ticket_code, checked_in_by):
    """
    Verify a scanned ticket and mark it as used.

    The UPDATE only matches a confirmed booking that has not been checked in,
    so the same QR code can never be used twice.
    """
    booking = (
        Booking.objects.select_related("event", "user", "checked_in_by")
        .filter(ticket_code=ticket_code)
        .first()
    )
    if booking is None:
        raise NotFound("No ticket matches this QR code.")
    if not (checked_in_by.is_admin or booking.event.organizer_id == checked_in_by.id):
        raise PermissionDenied("You can only check in attendees of your own events.")
    if not booking.is_confirmed:
        raise ValidationError({"detail": "This booking was cancelled. The ticket is not valid."})
    if booking.event.status == Event.Status.CANCELLED:
        raise ValidationError({"detail": "This event was cancelled."})

    now = timezone.now()
    updated = Booking.objects.filter(
        pk=booking.pk, status=Booking.Status.CONFIRMED, checked_in_at__isnull=True
    ).update(checked_in_at=now, checked_in_by=checked_in_by, updated_at=now)
    if not updated:
        booking.refresh_from_db()
        if not booking.is_confirmed:
            raise ValidationError({"detail": "This booking was cancelled. The ticket is not valid."})
        used_at = booking.checked_in_at.strftime("%Y-%m-%d %H:%M:%S %Z")
        raise Conflict(f"This ticket was already used for check-in at {used_at}.")

    booking.checked_in_at = now
    booking.checked_in_by = checked_in_by
    return booking