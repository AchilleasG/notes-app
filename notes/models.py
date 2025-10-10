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


class Tag(models.Model):
    """Tag model for categorizing notes"""
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#3b82f6", help_text="Hex color code (e.g., #3b82f6)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["name"]
        unique_together = ["user", "name"]  # Each user can have unique tag names
    
    def __str__(self):
        return self.name


class Note(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will store encrypted content from client
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(
        max_length=100, blank=True
    )  # Store salt for client-side encryption
    tags = models.ManyToManyField(Tag, related_name="notes", blank=True)
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
            "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in self.tags.all()],
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


class Friendship(models.Model):
    """Represents a friendship between two users"""
    user1 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="friendships_initiated")
    user2 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="friendships_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Ensure we don't have duplicate friendships
        unique_together = [["user1", "user2"]]

    def __str__(self):
        return f"{self.user1.username} <-> {self.user2.username}"

    @classmethod
    def are_friends(cls, user1, user2):
        """Check if two users are friends"""
        return cls.objects.filter(
            models.Q(user1=user1, user2=user2) | models.Q(user1=user2, user2=user1)
        ).exists()

    @classmethod
    def get_friends(cls, user):
        """Get all friends of a user"""
        friendships = cls.objects.filter(
            models.Q(user1=user) | models.Q(user2=user)
        )
        friends = []
        for friendship in friendships:
            if friendship.user1 == user:
                friends.append(friendship.user2)
            else:
                friends.append(friendship.user1)
        return friends


class FriendRequest(models.Model):
    """Represents a friend request from one user to another"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    from_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="friend_requests_sent")
    to_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="friend_requests_received")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # Ensure we don't have duplicate requests
        unique_together = [["from_user", "to_user"]]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"


class SharedNote(models.Model):
    """A note shared between two friends"""
    user1 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="shared_notes_1")
    user2 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="shared_notes_2")
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will store encrypted content from client
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(max_length=100, blank=True)
    tags = models.ManyToManyField(Tag, related_name="shared_notes", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="shared_notes_created")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} (shared by {self.user1.username} & {self.user2.username})"

    def get_client_data(self):
        """Return data safe for client-side processing"""
        return {
            "id": self.pk,
            "title": self.title,
            "content": self.content,  # Encrypted content
            "is_locked": self.is_locked,
            "salt": self.salt,
            "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in self.tags.all()],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by.username if self.created_by else None,
        }

    def has_access(self, user):
        """Check if a user has access to this shared note"""
        return user == self.user1 or user == self.user2


class ChatMessage(models.Model):
    """A chat message between two friends"""
    from_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="messages_sent")
    to_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="messages_received")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username}: {self.message[:50]}"
