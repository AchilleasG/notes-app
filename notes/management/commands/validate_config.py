"""
Django management command to validate Pydantic configuration.
"""

from django.core.management.base import BaseCommand
from personal_notebook.config import settings


class Command(BaseCommand):
    help = "Validate application configuration using Pydantic settings"

    def handle(self, *args, **options):
        """Validate and display current configuration."""
        self.stdout.write(self.style.SUCCESS("✅ Configuration validation successful!"))

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Current Configuration:")
        self.stdout.write("=" * 50)

        # App settings
        self.stdout.write(f"\n🔧 App Settings:")
        self.stdout.write(f"  DEBUG: {settings.debug}")
        self.stdout.write(f"  SECRET_KEY: {'*' * len(settings.secret_key)}")
        self.stdout.write(f"  ALLOWED_HOSTS: {settings.allowed_hosts}")

        # Database settings
        self.stdout.write(f"\n🗄️  Database Settings:")
        self.stdout.write(f"  HOST: {settings.db_host}")
        self.stdout.write(f"  PORT: {settings.db_port}")
        self.stdout.write(f"  NAME: {settings.db_name}")
        self.stdout.write(f"  USER: {settings.db_user}")
        self.stdout.write(f"  PASSWORD: {'*' * len(settings.db_password)}")

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("✅ All settings loaded successfully!"))
