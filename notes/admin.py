from django.contrib import admin
from .models import Note, NoteVersion

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('user', 'created_at')
    search_fields = ('title', 'content')


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ('note', 'title', 'created_at', 'is_locked')
    list_filter = ('created_at', 'is_locked')
    search_fields = ('title', 'content')
    readonly_fields = ('note', 'title', 'content', 'is_locked', 'created_at')
