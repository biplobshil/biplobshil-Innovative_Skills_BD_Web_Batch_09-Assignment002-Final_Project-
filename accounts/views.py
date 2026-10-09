from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.mixins import ProtectedDestroyMixin

from .permissions import IsAdmin
from .serializers import (
    AdminUserSerializer,
    AuthResponseSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    MessageSerializer,
    RegisterSerializer,
    UserSerializer,
    tokens_for_user,
)

User = get_user_model()


@extend_schema(tags=["Auth"], responses={201: AuthResponseSerializer})
class RegisterView(generics.CreateAPIView):
    """Create an account and receive a JWT token pair straight away."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {"user": UserSerializer(user).data, **tokens_for_user(user)}
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"], responses={200: AuthResponseSerializer})
class LoginView(TokenObtainPairView):
    """Exchange email and password for an access and a refresh token."""

    serializer_class = LoginSerializer


@extend_schema(tags=["Auth"])
class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new token pair."""


@extend_schema(tags=["Auth"], request=LogoutSerializer, responses={200: MessageSerializer})
class LogoutView(APIView):
    """Blacklist the refresh token so it can no longer be used."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            raise ValidationError({"refresh": "Token is invalid or expired."})
        return Response({"detail": "Logged out."})


@extend_schema(tags=["Auth"])
class MeView(generics.RetrieveUpdateAPIView):
    """View or update your own profile."""

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Auth"], request=ChangePasswordSerializer, responses={200: MessageSerializer})
class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated."})


@extend_schema(tags=["Users (admin)"])
class UserAdminViewSet(
    ProtectedDestroyMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Admins list users and change their role or active state."""

    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "patch", "delete", "head", "options"]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["date_joined", "email"]
    protected_message = (
        "This user has events or bookings and cannot be deleted. "
        "Set is_active to false instead."
    )

    def _reject_self(self, request, action):
        if self.get_object() == request.user:
            raise ValidationError({"detail": f"You cannot {action} your own account here."})

    def partial_update(self, request, *args, **kwargs):
        if {"role", "is_active"} & set(request.data):
            self._reject_self(request, "change the role or status of")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._reject_self(request, "delete")
        return super().destroy(request, *args, **kwargs)