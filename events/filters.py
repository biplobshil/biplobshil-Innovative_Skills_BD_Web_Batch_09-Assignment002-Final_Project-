import django_filters
from django.utils import timezone

from .models import Event


class EventFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_id")
    category_slug = django_filters.CharFilter(field_name="category__slug")
    organizer = django_filters.NumberFilter(field_name="organizer_id")
    location = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=Event.Status.choices)
    date = django_filters.DateFilter(field_name="start_time", lookup_expr="date")
    starts_after = django_filters.IsoDateTimeFilter(field_name="start_time", lookup_expr="gte")
    starts_before = django_filters.IsoDateTimeFilter(field_name="start_time", lookup_expr="lte")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    is_free = django_filters.BooleanFilter(method="filter_is_free")
    has_seats = django_filters.BooleanFilter(method="filter_has_seats")
    upcoming = django_filters.BooleanFilter(method="filter_upcoming")

    class Meta:
        model = Event
        fields = []

    def filter_is_free(self, queryset, name, value):
        return queryset.filter(price=0) if value else queryset.filter(price__gt=0)

    def filter_has_seats(self, queryset, name, value):
        if value:
            return queryset.filter(available_seats__gt=0)
        return queryset.filter(available_seats=0)

    def filter_upcoming(self, queryset, name, value):
        now = timezone.now()
        return queryset.filter(start_time__gt=now) if value else queryset.filter(start_time__lte=now)