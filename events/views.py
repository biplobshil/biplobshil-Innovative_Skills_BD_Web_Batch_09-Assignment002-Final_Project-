from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrReadOnly, IsOrganizerOrAdmin
from config.mixins import ProtectedDestroyMixin

from .filters import EventFilter
from .models import Category, Event
from .permissions import EventPermission
from .serializers import CategorySerializer, EventImageSerializer, EventSerializer


@extend_schema(tags=["Categories"])
class CategoryViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """Anyone can read categories; only admins can create, update or delete them."""

    queryset = Category.objects.annotate(
        events_count=Count("events", filter=Q(events__status=Event.Status.PUBLISHED))
    )
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    protected_message = "This category still has events and cannot be deleted."


@extend_schema(tags=["Events"])
class EventViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [EventPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_class = EventFilter
    search_fields = ["title", "description", "location", "category__name"]
    ordering_fields = ["start_time", "price", "created_at", "available_seats", "title"]
    ordering = ["start_time"]
    protected_message = (
        "This event has bookings and cannot be deleted. Set its status to 'cancelled' instead."
    )

    def get_queryset(self):
        """Drafts and cancelled events are only visible to their organizer and admins."""
        queryset = Event.objects.select_related("category", "organizer")
        user = self.request.user
        if user.is_authenticated and user.is_admin:
            return queryset
        visible = Q(status=Event.Status.PUBLISHED)
        if user.is_authenticated and user.is_organizer:
            visible |= Q(organizer=user)
        return queryset.filter(visible)

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    @extend_schema(summary="List the events I organize")
    @action(detail=False, permission_classes=[IsAuthenticated, IsOrganizerOrAdmin])
    def mine(self, request):
        queryset = self.filter_queryset(self.get_queryset().filter(organizer=request.user))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(
        methods=["put"],
        summary="Upload or replace the event image",
        request={"multipart/form-data": EventImageSerializer},
        responses=EventSerializer,
    )
    @extend_schema(methods=["delete"], summary="Remove the event image", responses={204: None})
    @action(detail=True, methods=["put", "delete"], parser_classes=[MultiPartParser, FormParser])
    def image(self, request, pk=None):
        event = self.get_object()
        if request.method == "DELETE":
            if event.image:
                event.image.delete(save=False)
            event.image = None
            event.save(update_fields=["image", "updated_at"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = EventImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if event.image:
            event.image.delete(save=False)
        event.image = serializer.validated_data["image"]
        event.save(update_fields=["image", "updated_at"])
        return Response(self.get_serializer(event).data)