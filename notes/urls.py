from django.urls import path
from . import views

urlpatterns = [
    path("", views.note_list, name="note_list"),
    path("create/", views.note_create, name="note_create"),
    path("edit/<int:pk>/", views.note_edit, name="note_edit"),
    path("delete/<int:pk>/", views.note_delete, name="note_delete"),
    path("view/<int:pk>/", views.note_view, name="note_view"),
    path("note/<int:pk>/", views.note_view, name="note_detail"),
    path("history/<int:pk>/", views.note_history, name="note_history"),
    path("render-markdown/", views.render_markdown, name="render_markdown"),
    path("profile/", views.profile, name="profile"),
    path("api/tags/autocomplete/", views.tag_autocomplete, name="tag_autocomplete"),
]
