from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """The request is valid but clashes with the current state (e.g. sold out)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"