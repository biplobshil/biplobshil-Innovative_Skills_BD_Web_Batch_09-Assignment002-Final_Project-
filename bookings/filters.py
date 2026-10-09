import django_filters

from .models import Booking


class BookingFilter(django_filters.FilterSet):
    event = django_filters.NumberFilter(field_name="event_id")
    user = django_filters.NumberFilter(field_name="user_id", label="User id (admin only)")
    status = django_filters.ChoiceFilter(choices=Booking.Status.choices)
    checked_in = django_filters.BooleanFilter(
        field_name="checked_in_at", lookup_expr="isnull", exclude=True
    )

    class Meta:
        model = Booking
        fields = []