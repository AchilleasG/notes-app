from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import getpass
from notes.models import Note


class Command(BaseCommand):
    help = "Migrate existing encrypted notes to new format (title unencrypted, only content encrypted)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="User ID to migrate notes for (optional, if not provided will migrate all users)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be migrated without making changes",
        )

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def decrypt_old_format(self, note, password):
        """Decrypt note using old format (both title and content encrypted)"""
        try:
            salt = str(note.user.id).encode().ljust(16, b"0")[:16]
            key = self.derive_key(password, salt)
            fernet = Fernet(key)

            # Try to decrypt both title and content
            decrypted_title = fernet.decrypt(note.title.encode()).decode()
            decrypted_content = fernet.decrypt(note.content.encode()).decode()

            return {"title": decrypted_title, "content": decrypted_content}
        except Exception as e:
            return None

    def encrypt_new_format(self, note, password, decrypted_title, decrypted_content):
        """Encrypt note using new format (only content encrypted)"""
        salt = str(note.user.id).encode().ljust(16, b"0")[:16]
        key = self.derive_key(password, salt)
        fernet = Fernet(key)

        # Set title as unencrypted and encrypt only content
        note.title = decrypted_title
        note.content = fernet.encrypt(decrypted_content.encode()).decode()

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        dry_run = options.get("dry_run")

        # Get locked notes to migrate
        if user_id:
            locked_notes = Note.objects.filter(user_id=user_id, is_locked=True)
            users = User.objects.filter(id=user_id)
        else:
            locked_notes = Note.objects.filter(is_locked=True)
            users = User.objects.filter(notes__is_locked=True).distinct()

        if not locked_notes.exists():
            self.stdout.write(self.style.SUCCESS("No locked notes found to migrate."))
            return

        self.stdout.write(
            f"Found {locked_notes.count()} locked notes to potentially migrate."
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        migrated_count = 0
        failed_count = 0

        # Process each user's locked notes
        for user in users:
            user_locked_notes = locked_notes.filter(user=user)
            if not user_locked_notes.exists():
                continue

            self.stdout.write(
                f"\nProcessing {user_locked_notes.count()} locked notes for user: {user.username}"
            )

            # Get password for this user's notes
            password = getpass.getpass(
                f"Enter encryption password for user {user.username}: "
            )

            for note in user_locked_notes:
                # Try to decrypt using old format
                decrypted = self.decrypt_old_format(note, password)

                if decrypted:
                    # Check if this note needs migration by seeing if title looks encrypted
                    try:
                        # If title is encrypted, it won't be readable text
                        # We can try to determine this by checking if it's base64 encoded
                        import base64

                        base64.b64decode(note.title.encode())
                        # If we reach here, title is likely encrypted (base64)
                        needs_migration = True
                    except:
                        # Title is not base64, probably already in new format
                        needs_migration = False

                    if needs_migration:
                        if dry_run:
                            self.stdout.write(
                                f'  WOULD MIGRATE: Note ID {note.id} - "{decrypted["title"]}"'
                            )
                            migrated_count += 1
                        else:
                            try:
                                self.encrypt_new_format(
                                    note,
                                    password,
                                    decrypted["title"],
                                    decrypted["content"],
                                )
                                note.save()
                                self.stdout.write(
                                    f'  MIGRATED: Note ID {note.id} - "{decrypted["title"]}"'
                                )
                                migrated_count += 1
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"  FAILED to migrate Note ID {note.id}: {e}"
                                    )
                                )
                                failed_count += 1
                    else:
                        self.stdout.write(
                            f"  SKIPPED: Note ID {note.id} - already in new format"
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  FAILED to decrypt Note ID {note.id} - incorrect password or corrupted data"
                        )
                    )
                    failed_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDRY RUN COMPLETE: {migrated_count} notes would be migrated, {failed_count} failures"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nMIGRATION COMPLETE: {migrated_count} notes migrated, {failed_count} failures"
                )
            )

        if failed_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Some notes failed to migrate. Please check passwords and try again."
                )
            )
