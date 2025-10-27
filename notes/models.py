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
    color = models.CharField(
        max_length=7, default="#3b82f6", help_text="Hex color code (e.g., #3b82f6)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["user", "name"]  # Each user can have unique tag names

    def __str__(self):
        return self.name


class Folder(models.Model):
    """Folder model for organizing personal notes"""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name="subfolders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["user", "name", "parent"]  # Unique folder names within same parent

    def __str__(self):
        if self.parent:
            return f"{self.parent.name}/{self.name}"
        return self.name

    def get_full_path(self):
        """Get the full path of the folder"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return "/".join(path)


class Note(models.Model):
    NOTE_TYPE_CHOICES = [
        ('markdown', 'Markdown Note'),
        ('canvas', 'Canvas Note'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will store encrypted content from client
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='markdown')
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(
        max_length=100, blank=True
    )  # Store salt for client-side encryption
    tags = models.ManyToManyField(Tag, related_name="notes", blank=True)
    folder = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_client_data(self):
        """Return data safe for client-side processing"""
        return {
            "id": self.pk,
            "title": self.title,
            "content": self.content,  # Encrypted content
            "note_type": self.note_type,
            "is_locked": self.is_locked,
            "salt": self.salt,
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self.tags.all()
            ],
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

    user1 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="friendships_initiated"
    )
    user2 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="friendships_received"
    )
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
        friendships = cls.objects.filter(models.Q(user1=user) | models.Q(user2=user))
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
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    from_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="friend_requests_sent"
    )
    to_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="friend_requests_received"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # Ensure we don't have duplicate requests
        unique_together = [["from_user", "to_user"]]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"


class SharedFolder(models.Model):
    """Folder model for organizing shared notes between two friends"""

    user1 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="shared_folders_1"
    )
    user2 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="shared_folders_2"
    )
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subfolders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        # Unique folder names within same parent for the same user pair
        unique_together = [["user1", "user2", "name", "parent"]]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name}/{self.name}"
        return self.name

    def get_full_path(self):
        """Get the full path of the folder"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return "/".join(path)

    def has_access(self, user):
        """Check if a user has access to this shared folder"""
        return user == self.user1 or user == self.user2


class SharedNote(models.Model):
    """A note shared between two friends"""

    NOTE_TYPE_CHOICES = [
        ('markdown', 'Markdown Note'),
        ('canvas', 'Canvas Note'),
    ]

    user1 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="shared_notes_1"
    )
    user2 = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="shared_notes_2"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()  # This will store encrypted content from client
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='markdown')
    is_locked = models.BooleanField(default=False)
    salt = models.CharField(max_length=100, blank=True)
    tags = models.ManyToManyField(Tag, related_name="shared_notes", blank=True)
    folder = models.ForeignKey(
        SharedFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="shared_notes_created",
    )

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
            "note_type": self.note_type,
            "is_locked": self.is_locked,
            "salt": self.salt,
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self.tags.all()
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by.username if self.created_by else None,
        }

    def has_access(self, user):
        """Check if a user has access to this shared note"""
        return user == self.user1 or user == self.user2


class ChatMessage(models.Model):
    """A chat message between two friends"""

    from_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="messages_sent"
    )
    to_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="messages_received"
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.from_user.username} -> {self.to_user.username}: {self.message[:50]}"
        )


class CanvasElement(models.Model):
    """An element (textbox, image, shape, or drawing) in a canvas note"""
    
    ELEMENT_TYPE_CHOICES = [
        ('textbox', 'Text Box'),
        ('image', 'Image'),
        ('rectangle', 'Rectangle'),
        ('circle', 'Circle'),
        ('line', 'Line'),
        ('freehand', 'Freehand Drawing'),
    ]
    
    # For personal notes
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="canvas_elements",
        null=True,
        blank=True
    )
    
    # For shared notes
    shared_note = models.ForeignKey(
        SharedNote,
        on_delete=models.CASCADE,
        related_name="canvas_elements",
        null=True,
        blank=True
    )
    
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPE_CHOICES)
    
    # Position on canvas
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    
    # Size
    width = models.IntegerField(default=200)
    height = models.IntegerField(default=100)
    
    # For textbox elements
    text_content = models.TextField(blank=True, default='')
    
    # For image elements
    image = models.ImageField(upload_to='canvas_images/', blank=True, null=True)
    
    # For shape elements (rectangle, circle, line) - store styling
    stroke_color = models.CharField(max_length=7, default='#000000')  # Hex color
    fill_color = models.CharField(max_length=7, default='#ffffff')  # Hex color
    stroke_width = models.IntegerField(default=2)
    
    # For freehand drawing - store path data as JSON
    path_data = models.TextField(blank=True, default='')  # JSON array of points
    
    # Z-index for layering
    z_index = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['z_index', 'created_at']
    
    def __str__(self):
        note_title = self.note.title if self.note else (self.shared_note.title if self.shared_note else "No note")
        return f"{self.element_type} in {note_title}"
    
    def to_dict(self):
        """Serialize element to dictionary"""
        data = {
            'id': self.id,
            'element_type': self.element_type,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'z_index': self.z_index,
        }
        
        if self.element_type == 'textbox':
            data['text_content'] = self.text_content
        elif self.element_type == 'image' and self.image:
            data['image_url'] = self.image.url
        elif self.element_type in ['rectangle', 'circle', 'line']:
            data['stroke_color'] = self.stroke_color
            data['fill_color'] = self.fill_color
            data['stroke_width'] = self.stroke_width
        elif self.element_type == 'freehand':
            data['stroke_color'] = self.stroke_color
            data['stroke_width'] = self.stroke_width
            data['path_data'] = self.path_data
            
        return data
