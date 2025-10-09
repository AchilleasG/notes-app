from django.db import models
from django.contrib.auth.models import AbstractUser
import json


class CustomUser(AbstractUser):
    """Custom user model extending Django's AbstractUser"""

    # Add any additional fields here
    bio = models.TextField(max_length=500, blank=True, help_text="Optional bio")
    birth_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.username


class Note(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will store encrypted content from client
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(
        max_length=100, blank=True
    )  # Store salt for client-side encryption
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_client_data(self):
        """Return data safe for client-side processing"""
        return {
            "id": self.pk,
            "title": self.title,
            "content": self.content,  # Encrypted content
            "is_locked": self.is_locked,
            "salt": self.salt,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class NoteVersion(models.Model):
    """Stores historical versions of notes"""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="versions")
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will also store encrypted content
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.note.title} - {self.created_at}"

    def get_client_data(self):
        """Return data safe for client-side processing"""
        return {
            "id": self.pk,
            "title": self.title,
            "content": self.content,  # Encrypted content
            "is_locked": self.is_locked,
            "salt": self.salt,
            "created_at": self.created_at.isoformat(),
        }
