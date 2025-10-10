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
    
    # Friends system URLs
    path("friends/", views.friends_list, name="friends_list"),
    path("friends/search/", views.search_users, name="search_users"),
    path("friends/request/<int:user_id>/", views.send_friend_request, name="send_friend_request"),
    path("friends/accept/<int:request_id>/", views.accept_friend_request, name="accept_friend_request"),
    path("friends/reject/<int:request_id>/", views.reject_friend_request, name="reject_friend_request"),
    path("friends/<int:friend_id>/chat/", views.friend_chat, name="friend_chat"),
    path("friends/<int:friend_id>/shared-notes/", views.shared_notes_list, name="shared_notes_list"),
    path("friends/<int:friend_id>/shared-notes/create/", views.shared_note_create, name="shared_note_create"),
    path("shared-notes/<int:note_id>/", views.shared_note_view, name="shared_note_view"),
    path("shared-notes/<int:note_id>/edit/", views.shared_note_edit, name="shared_note_edit"),
    path("shared-notes/<int:note_id>/delete/", views.shared_note_delete, name="shared_note_delete"),
]
