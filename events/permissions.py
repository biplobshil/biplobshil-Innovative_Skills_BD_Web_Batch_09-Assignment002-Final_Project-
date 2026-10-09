from rest_framework.permissions import SAFE_METHODS, BasePermission


class EventPermission(BasePermission):
    """
    Read: anyone.
    Create: organizers and admins.
    Update / delete: the event's own organizer, or an admin.
    """

    message = "Only the event's organizer or an admin can perform this action."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and (user.is_admin or user.is_organizer))

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin or obj.organizer_id == request.user.id