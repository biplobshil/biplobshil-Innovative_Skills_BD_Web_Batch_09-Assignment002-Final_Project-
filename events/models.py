from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify


def default_max_tickets():
    return settings.MAX_TICKETS_PER_BOOKING


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Build the slug from the name ("Tech Talks" -> "tech-talks").
        if not self.slug:
            base = slugify(self.name)[:110] or "category"
            slug, n = base, 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="events")
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="events"
    )
    location = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_seats = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # Changed only by the booking code; API clients cannot write it.
    available_seats = models.PositiveIntegerField(editable=False)
    max_tickets_per_booking = models.PositiveSmallIntegerField(
        default=default_max_tickets, validators=[MinValueValidator(1)]
    )
    image = models.ImageField(upload_to="events/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [models.Index(fields=["status", "start_time"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_seats__lte=F("total_seats")),
                name="event_available_lte_total",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="event_end_after_start",
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # A new event starts with every seat available.
        if self._state.adding and self.available_seats is None:
            self.available_seats = self.total_seats
        super().save(*args, **kwargs)

    @property
    def seats_booked(self):
        return self.total_seats - self.available_seats

    @property
    def is_sold_out(self):
        return self.available_seats == 0

    @property
    def has_started(self):
        return self.start_time <= timezone.now()