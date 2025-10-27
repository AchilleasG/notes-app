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
    # Folder management URLs
    path("folders/create/", views.folder_create, name="folder_create"),
    path("folders/<int:folder_id>/rename/", views.folder_rename, name="folder_rename"),
    path("folders/<int:folder_id>/delete/", views.folder_delete, name="folder_delete"),
    path("notes/<int:note_id>/move/", views.note_move, name="note_move"),
    # Friends system URLs
    path("friends/", views.friends_list, name="friends_list"),
    path("friends/search/", views.search_users, name="search_users"),
    path(
        "friends/request/<int:user_id>/",
        views.send_friend_request,
        name="send_friend_request",
    ),
    path(
        "friends/accept/<int:request_id>/",
        views.accept_friend_request,
        name="accept_friend_request",
    ),
    path(
        "friends/reject/<int:request_id>/",
        views.reject_friend_request,
        name="reject_friend_request",
    ),
    path("friends/<int:friend_id>/chat/", views.friend_chat, name="friend_chat"),
    path(
        "friends/<int:friend_id>/shared-notes/",
        views.shared_notes_list,
        name="shared_notes_list",
    ),
    path(
        "friends/<int:friend_id>/shared-notes/create/",
        views.shared_note_create,
        name="shared_note_create",
    ),
    path(
        "shared-notes/<int:note_id>/", views.shared_note_view, name="shared_note_view"
    ),
    path(
        "shared-notes/<int:note_id>/edit/",
        views.shared_note_edit,
        name="shared_note_edit",
    ),
    path(
        "shared-notes/<int:note_id>/delete/",
        views.shared_note_delete,
        name="shared_note_delete",
    ),
    path(
        "shared-notes/<int:note_id>/move/",
        views.shared_note_move,
        name="shared_note_move",
    ),
    # Shared folder management URLs
    path(
        "friends/<int:friend_id>/shared-folders/create/",
        views.shared_folder_create,
        name="shared_folder_create",
    ),
    path(
        "shared-folders/<int:folder_id>/rename/",
        views.shared_folder_rename,
        name="shared_folder_rename",
    ),
    path(
        "shared-folders/<int:folder_id>/delete/",
        views.shared_folder_delete,
        name="shared_folder_delete",
    ),
    # Canvas element management URLs
    path(
        "canvas/elements/create/",
        views.canvas_element_create,
        name="canvas_element_create",
    ),
    path(
        "canvas/elements/<int:element_id>/update/",
        views.canvas_element_update,
        name="canvas_element_update",
    ),
    path(
        "canvas/elements/<int:element_id>/delete/",
        views.canvas_element_delete,
        name="canvas_element_delete",
    ),
    path(
        "canvas/elements/<int:element_id>/undelete/",
        views.canvas_element_undelete,
        name="canvas_element_undelete",
    ),
    path(
        "canvas/elements/upload-image/",
        views.canvas_element_upload_image,
        name="canvas_element_upload_image",
    ),
]
