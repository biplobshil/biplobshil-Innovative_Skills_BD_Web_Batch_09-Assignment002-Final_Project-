from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_admin)


class IsAdmin(BasePermission):
    """Only users with the admin role."""

    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    """Anyone can read; only admins can write."""

    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_admin(request.user)


class IsOrganizerOrAdmin(BasePermission):
    """Only organizers and admins."""

    message = "Only organizers and admins can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_admin or user.is_organizer))