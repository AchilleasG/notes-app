from django.db import models
from django.contrib.auth.models import User
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

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

    def encrypt_content(self, password: str):
        """Encrypt only content with the given password, leaving title unencrypted"""
        # Use user ID as salt for consistency
        salt = str(self.user.id).encode().ljust(16, b"0")[:16]
        key = self.derive_key(password, salt)
        fernet = Fernet(key)

        # Encrypt only content, leave title as is
        self.content = fernet.encrypt(self.content.encode()).decode()
        self.is_locked = True

    def decrypt_content(self, password: str) -> dict:
        """Decrypt only content with the given password, title remains unencrypted"""
        if not self.is_locked:
            return {"title": self.title, "content": self.content}

        try:
            # Use user ID as salt for consistency
            salt = str(self.user.id).encode().ljust(16, b"0")[:16]
            key = self.derive_key(password, salt)
            fernet = Fernet(key)

            # Decrypt only content, title is already unencrypted
            decrypted_content = fernet.decrypt(self.content.encode()).decode()

            return {"title": self.title, "content": decrypted_content}
        except Exception:
            return None
