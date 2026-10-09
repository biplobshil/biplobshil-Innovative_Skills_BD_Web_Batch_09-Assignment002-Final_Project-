import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the first admin from DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD."

    def handle(self, *args, **options):
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if not email or not password:
            self.stdout.write("DJANGO_SUPERUSER_EMAIL / PASSWORD not set; skipping.")
            return

        User = get_user_model()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Admin {email} already exists.")
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin {email}."))