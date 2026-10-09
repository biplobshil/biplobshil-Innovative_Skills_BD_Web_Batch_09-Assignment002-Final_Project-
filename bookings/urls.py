from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("bookings", views.BookingViewSet, basename="booking")

urlpatterns = [
    path(
        "events/<int:event_id>/bookings/",
        views.EventBookingsView.as_view(),
        name="event-bookings",
    ),
    path(
        "events/<int:event_id>/attendance/",
        views.EventAttendanceView.as_view(),
        name="event-attendance",
    ),
    *router.urls,
]