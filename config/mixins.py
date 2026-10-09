from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response


class ProtectedDestroyMixin:
    """Return 409 instead of crashing when related rows block a delete."""

    protected_message = "This item is still in use and cannot be deleted."

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": self.protected_message}, status=status.HTTP_409_CONFLICT)