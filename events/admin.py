from django.contrib import admin

from .models import Category, Event


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title", "category", "organizer", "start_time", "price",
        "available_seats", "total_seats", "status",
    ]
    list_filter = ["status", "category"]
    search_fields = ["title", "location"]
    autocomplete_fields = ["organizer", "category"]
    readonly_fields = ["available_seats"]
    date_hierarchy = "start_time"

    def save_model(self, request, obj, form, change):
        if change and "total_seats" in form.changed_data:
            old = Event.objects.get(pk=obj.pk)
            booked = old.total_seats - old.available_seats
            obj.total_seats = max(obj.total_seats, booked)
            obj.available_seats = obj.total_seats - booked
        super().save_model(request, obj, form, change)