from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import getpass


class Command(BaseCommand):
    help = "Create a new user account"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Username for the new user",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Email address for the new user",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the new user (if not provided, will prompt securely)",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Create user as superuser/admin",
        )
        parser.add_argument(
            "--bio",
            type=str,
            help="User bio/description",
            default="",
        )
        parser.add_argument(
            "--location",
            type=str,
            help="User location",
            default="",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        # Get username
        username = options.get("username")
        if not username:
            username = input("Username: ")

        if not username:
            raise CommandError("Username is required")

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            raise CommandError(f'User "{username}" already exists')

        # Get email
        email = options.get("email")
        if not email:
            email = input("Email address: ")

        # Validate email
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise CommandError("Invalid email address")

        # Check if email already exists
        if email and User.objects.filter(email=email).exists():
            raise CommandError(f'User with email "{email}" already exists')

        # Get password
        password = options.get("password")
        if not password:
            password = getpass.getpass("Password: ")
            confirm_password = getpass.getpass("Confirm password: ")

            if password != confirm_password:
                raise CommandError("Passwords do not match")

        if not password:
            raise CommandError("Password is required")

        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters long")

        # Get optional fields
        bio = options.get("bio", "")
        location = options.get("location", "")
        is_superuser = options.get("superuser", False)

        try:
            # Create user
            if is_superuser:
                user = User.objects.create_superuser(
                    username=username, email=email, password=password
                )
                user_type = "superuser"
            else:
                user = User.objects.create_user(
                    username=username, email=email, password=password
                )
                user_type = "user"

            # Set additional fields if provided
            if bio:
                user.bio = bio
            if location:
                user.location = location

            user.save()

            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {user_type} "{username}"')
            )

            if email:
                self.stdout.write(f"Email: {email}")
            if bio:
                self.stdout.write(f"Bio: {bio}")
            if location:
                self.stdout.write(f"Location: {location}")

        except Exception as e:
            raise CommandError(f"Error creating user: {str(e)}")
