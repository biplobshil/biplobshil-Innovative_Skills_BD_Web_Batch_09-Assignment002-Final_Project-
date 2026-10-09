from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """The logged-in user's own profile."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "role", "date_joined"]
        read_only_fields = ["id", "email", "role", "date_joined"]


class AdminUserSerializer(serializers.ModelSerializer):
    """User management for admins, who may change role and active state."""

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone",
            "role", "is_active", "date_joined", "last_login",
        ]
        read_only_fields = ["id", "email", "date_joined", "last_login"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    # Admin accounts cannot be self-registered.
    role = serializers.ChoiceField(
        choices=[User.Role.USER, User.Role.ORGANIZER], default=User.Role.USER
    )

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "password_confirm",
            "first_name", "last_name", "phone", "role",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        password = attrs.pop("password")
        validate_password(password, User(**attrs))
        attrs["password"] = password
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password login that also returns the user's profile."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        attrs[self.username_field] = attrs[self.username_field].lower()
        data = super().validate(attrs)
        return {"user": UserSerializer(self.user).data, **data}


def tokens_for_user(user):
    refresh = LoginSerializer.get_token(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class AuthResponseSerializer(serializers.Serializer):
    """Response body of register and login (for the docs)."""

    user = UserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField()