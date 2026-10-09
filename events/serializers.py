from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Event

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def validate_event_image(image):
    limit = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    if image.size > limit:
        raise serializers.ValidationError(
            f"Image is too large. Maximum size is {settings.MAX_IMAGE_SIZE_MB} MB."
        )
    content_type = getattr(image, "content_type", None)
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError("Only JPEG, PNG, WebP and GIF images are allowed.")
    return image


class CategorySerializer(serializers.ModelSerializer):
    events_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "events_count", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class EventSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    organizer_name = serializers.SerializerMethodField()
    image = serializers.ImageField(
        required=False, allow_null=True, validators=[validate_event_image]
    )
    seats_booked = serializers.IntegerField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "title", "description", "category", "category_name",
            "organizer", "organizer_name", "location", "start_time", "end_time",
            "price", "total_seats", "available_seats", "seats_booked", "is_sold_out",
            "max_tickets_per_booking", "image", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organizer", "available_seats", "created_at", "updated_at"]

    def get_organizer_name(self, obj) -> str:
        return obj.organizer.get_full_name() or f"Organizer #{obj.organizer_id}"

    def validate_max_tickets_per_booking(self, value):
        if value > settings.MAX_TICKETS_PER_BOOKING:
            raise serializers.ValidationError(
                f"Cannot be higher than {settings.MAX_TICKETS_PER_BOOKING}."
            )
        return value

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "Must be after start_time."})
        if "start_time" in attrs and attrs["start_time"] <= timezone.now():
            if self.instance is None or attrs["start_time"] != self.instance.start_time:
                raise serializers.ValidationError({"start_time": "Must be in the future."})
        return attrs

    def create(self, validated_data):
        validated_data["available_seats"] = validated_data["total_seats"]
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        # Changing total_seats must keep the seats that are already booked.
        new_total = validated_data.pop("total_seats", None)
        if new_total is not None:
            locked = Event.objects.select_for_update().get(pk=instance.pk)
            booked = locked.total_seats - locked.available_seats
            if new_total < booked:
                raise serializers.ValidationError(
                    {"total_seats": f"{booked} seats are already booked."}
                )
            instance.total_seats = new_total
            instance.available_seats = new_total - booked
        return super().update(instance, validated_data)


class EventImageSerializer(serializers.Serializer):
    image = serializers.ImageField(validators=[validate_event_image])