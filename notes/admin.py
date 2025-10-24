from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Note, NoteVersion, CustomUser, Tag, Folder, SharedFolder, CanvasElement


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("name",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin interface for CustomUser model"""

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")

    # Add the custom fields to the fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("bio", "birth_date", "location", "website")}),
    )

    # Add the custom fields to the add_fieldsets for user creation
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Additional Info",
            {"fields": ("email", "bio", "birth_date", "location", "website")},
        ),
    )


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "parent", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("name",)
    raw_id_fields = ("parent",)


@admin.register(SharedFolder)
class SharedFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "user1", "user2", "parent", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name",)
    raw_id_fields = ("parent",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "note_type", "folder", "created_at", "updated_at")
    list_filter = ("user", "note_type", "folder", "created_at", "tags")
    search_fields = ("title", "content")
    filter_horizontal = ("tags",)
    raw_id_fields = ("folder",)


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ("note", "title", "created_at", "is_locked")
    list_filter = ("created_at", "is_locked")
    search_fields = ("title", "content")
    readonly_fields = ("note", "title", "content", "is_locked", "created_at")


@admin.register(CanvasElement)
class CanvasElementAdmin(admin.ModelAdmin):
    list_display = ("id", "element_type", "note", "shared_note", "x", "y", "width", "height", "created_at")
    list_filter = ("element_type", "created_at")
    search_fields = ("text_content",)
    raw_id_fields = ("note", "shared_note")
