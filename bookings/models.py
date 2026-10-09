import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from events.models import Event


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    # Random and unguessable: this is what the ticket's QR code contains.
    ticket_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="bookings")
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    # Price snapshot, so later price changes do not rewrite history.
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    # Set exactly once, when the ticket's QR code is scanned at the door.
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="check_ins",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event", "status"])]

    def __str__(self):
        return f"Booking #{self.pk} - {self.event} x{self.quantity}"

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    @property
    def is_checked_in(self):
        return self.checked_in_at is not None