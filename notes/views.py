from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from .models import (
    Note,
    NoteVersion,
    Tag,
    CustomUser,
    Friendship,
    FriendRequest,
    SharedNote,
    ChatMessage,
    Folder,
    SharedFolder,
)
from .forms import CustomUserChangeForm, CustomPasswordChangeForm


@login_required
def note_list(request):
    notes = Note.objects.filter(user=request.user)

    # Filter by tags if specified
    tag_filter = request.GET.get("tags", "").strip()
    
    # Filter by folder if specified (but not when searching by tags)
    folder_id = request.GET.get("folder")
    current_folder = None
    
    if tag_filter:
        # When searching by tags, show results from ALL folders
        # Split by comma and filter (case-insensitive)
        tag_names = [t.strip() for t in tag_filter.split(",") if t.strip()]
        for tag_name in tag_names:
            notes = notes.filter(tags__name__iexact=tag_name)
        notes = notes.distinct()
        # Don't apply folder filtering when searching by tags
    else:
        # Only apply folder filtering when NOT searching by tags
        if folder_id == "all":  # Show all notes regardless of folder
            # Don't filter by folder, show all notes
            pass
        elif folder_id:
            try:
                current_folder = Folder.objects.get(id=folder_id, user=request.user)
                notes = notes.filter(folder=current_folder)
            except Folder.DoesNotExist:
                pass
        else:  # Default to Home (no folder) when no folder parameter or empty string
            notes = notes.filter(folder__isnull=True)

    # Get all tags for the current user
    user_tags = Tag.objects.filter(user=request.user)

    # Get all folders for the sidebar
    folders = Folder.objects.filter(user=request.user)
    
    # Get subfolders for the current folder if viewing a specific folder
    # For Home view (no current folder), show root-level folders
    subfolders = []
    if current_folder:
        subfolders = Folder.objects.filter(user=request.user, parent=current_folder).order_by('name')
    elif folder_id != "all":  # Home view - show root folders
        subfolders = Folder.objects.filter(user=request.user, parent__isnull=True).order_by('name')
    
    # Serialize folders for JavaScript
    import json
    folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in folders
    ])

    return render(
        request,
        "notes/note_list.html",
        {
            "notes": notes,
            "user_tags": user_tags,
            "selected_tags": tag_filter,
            "folders": folders,
            "folders_json": folders_json,
            "current_folder": current_folder,
            "subfolders": subfolders,
        },
    )


@login_required
def note_create(request):
    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        encrypted_content = request.POST.get("encrypted_content")
        is_locked = request.POST.get("is_locked") == "on"
        salt = request.POST.get("salt", "")
        image = request.FILES.get("image")
        tags_data = request.POST.get("tags", "")
        folder_id = request.POST.get("folder")
        note_type = request.POST.get("note_type", "markdown")

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content
        
        # Canvas notes cannot be encrypted
        if note_type == "canvas" and is_locked:
            messages.error(request, "Canvas notes cannot be encrypted.")
            return redirect("note_create")

        if title:
            # For canvas notes, content is not required initially
            if not final_content and note_type != "canvas":
                messages.error(request, "Content is required.")
                return redirect("note_create")
            
            note = Note(
                user=request.user,
                title=title,
                content=final_content or "",
                note_type=note_type,
                is_locked=is_locked if note_type != "canvas" else False,
                salt=salt if note_type != "canvas" else "",
            )

            # Assign folder if specified
            if folder_id:
                try:
                    folder = Folder.objects.get(id=folder_id, user=request.user)
                    note.folder = folder
                except Folder.DoesNotExist:
                    pass

            # Handle image upload (legacy)
            if image:
                import os
                from django.conf import settings

                # Create media directory if it doesn't exist
                media_dir = os.path.join(settings.MEDIA_ROOT, "note_images")
                os.makedirs(media_dir, exist_ok=True)

                # Save the image
                image_path = os.path.join(media_dir, image.name)
                with open(image_path, "wb+") as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)

            note.save()

            # Process tags (only for markdown notes)
            if note_type == "markdown" and tags_data:
                import json

                try:
                    tags_list = json.loads(tags_data)
                    for tag_data in tags_list:
                        tag_name = tag_data.get("name", "").strip()
                        tag_color = tag_data.get("color", "#3b82f6")
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            try:
                                tag = Tag.objects.get(
                                    user=request.user, name__iexact=tag_name
                                )
                                # Update color if changed
                                if tag.color != tag_color:
                                    tag.color = tag_color
                                    tag.save()
                            except Tag.DoesNotExist:
                                tag = Tag.objects.create(
                                    user=request.user, name=tag_name, color=tag_color
                                )
                            note.tags.add(tag)
                except (json.JSONDecodeError, ValueError):
                    pass

            messages.success(request, "Note created successfully!")
            return redirect("note_view", pk=note.pk)
        else:
            messages.error(request, "Title is required.")

    # Get all user tags for autocomplete
    user_tags = Tag.objects.filter(user=request.user)
    # Get all folders for the folder selector
    folders = Folder.objects.filter(user=request.user)
    # Get current folder from query param if provided
    current_folder_id = request.GET.get("folder")
    current_folder = None
    if current_folder_id:
        try:
            current_folder = Folder.objects.get(id=current_folder_id, user=request.user)
        except Folder.DoesNotExist:
            pass
    
    # Serialize folders for JavaScript
    import json
    folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in folders
    ])
    
    return render(
        request,
        "notes/note_form.html",
        {
            "user_tags": user_tags,
            "folders": folders,
            "folders_json": folders_json,
            "current_folder": current_folder,
        },
    )


@login_required
def note_edit(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        encrypted_content = request.POST.get("encrypted_content")
        is_locked = request.POST.get("is_locked") == "on"
        salt = request.POST.get("salt", note.salt)
        image = request.FILES.get("image")
        tags_data = request.POST.get("tags", "")
        folder_id = request.POST.get("folder")

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        # Check if this is an AJAX request for checkbox update
        is_ajax_update = request.POST.get("ajax_update") == "true"

        # For AJAX updates, only require content; for normal edits, require both title and content
        if (is_ajax_update and final_content) or (title and final_content):
            # Handle image upload
            if image:
                import os
                from django.conf import settings

                # Create media directory if it doesn't exist
                media_dir = os.path.join(settings.MEDIA_ROOT, "note_images")
                os.makedirs(media_dir, exist_ok=True)

                # Save the image
                image_path = os.path.join(media_dir, image.name)
                with open(image_path, "wb+") as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)

            # Save current version to history before updating (only for non-AJAX updates)
            if not is_ajax_update:
                NoteVersion.objects.create(
                    note=note,
                    title=note.title,
                    content=note.content,
                    is_locked=note.is_locked,
                    salt=note.salt,
                )

            # Update note
            if not is_ajax_update and title:
                note.title = title
            note.content = final_content
            note.is_locked = is_locked
            note.salt = salt
            
            # Update folder if specified (only for non-AJAX updates)
            if not is_ajax_update:
                if folder_id:
                    try:
                        folder = Folder.objects.get(id=folder_id, user=request.user)
                        note.folder = folder
                    except Folder.DoesNotExist:
                        note.folder = None
                elif folder_id == "":  # Empty string means remove folder
                    note.folder = None
            
            note.save()

            # Check if this is an AJAX request for checkbox update
            if is_ajax_update:
                return JsonResponse({"success": True})

            # Process tags (only for non-AJAX updates)
            note.tags.clear()  # Remove existing tags
            if tags_data:
                import json

                try:
                    tags_list = json.loads(tags_data)
                    for tag_data in tags_list:
                        tag_name = tag_data.get("name", "").strip()
                        tag_color = tag_data.get("color", "#3b82f6")
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            try:
                                tag = Tag.objects.get(
                                    user=request.user, name__iexact=tag_name
                                )
                                # Update color if changed
                                if tag.color != tag_color:
                                    tag.color = tag_color
                                    tag.save()
                            except Tag.DoesNotExist:
                                tag = Tag.objects.create(
                                    user=request.user, name=tag_name, color=tag_color
                                )
                            note.tags.add(tag)
                except (json.JSONDecodeError, ValueError):
                    pass

            messages.success(request, "Note updated successfully!")
            return redirect("note_view", pk=pk)
        else:
            messages.error(request, "Title and content are required.")

    # Return note data for editing (client will handle decryption if needed)
    user_tags = Tag.objects.filter(user=request.user)
    folders = Folder.objects.filter(user=request.user)
    
    # Serialize folders for JavaScript
    import json
    folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in folders
    ])
    
    return render(
        request,
        "notes/note_form.html",
        {
            "note": note,
            "user_tags": user_tags,
            "folders": folders,
            "folders_json": folders_json,
        },
    )


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    if request.method == "POST":
        note.delete()
        messages.success(request, "Note deleted successfully!")
        return redirect("note_list")
    return render(request, "notes/note_confirm_delete.html", {"note": note})


@login_required
def note_unlock(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    if not note.is_locked:
        messages.info(request, "This note is not locked.")
        return redirect("note_edit", pk=pk)

    if request.method == "POST":
        password = request.POST.get("password")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "notes/note_unlock.html", {"note": note})

        decrypted = note.decrypt_content(password)

        if decrypted:
            # Store decrypted content and password in session temporarily
            request.session[f"note_{pk}"] = {
                "unlocked_content": decrypted,
                "password": password,
            }

            # Redirect based on the next parameter
            next_url = request.GET.get("next", "note_edit")
            if next_url == "note_view":
                return redirect("note_view", pk=pk)
            else:
                return redirect("note_edit", pk=pk)
        else:
            messages.error(request, "Incorrect password.")

    return render(request, "notes/note_unlock.html", {"note": note})


@login_required
def note_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    # Get all notes for the sidebar
    all_notes = Note.objects.filter(user=request.user).order_by("-updated_at")
    
    # For canvas notes, get elements as JSON
    elements_json = "[]"
    if note.note_type == 'canvas':
        import json
        from .models import CanvasElement
        elements = CanvasElement.objects.filter(note=note)
        elements_json = json.dumps([element.to_dict() for element in elements])

    # Pass note data to client (client will handle decryption if needed)
    return render(
        request,
        "notes/note_view.html",
        {
            "note": note,
            "all_notes": all_notes,
            "elements_json": elements_json,
        },
    )


@login_required
def note_history(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    # Get all versions for this note
    # Exclude any versions that have the same content as the current note to avoid duplicates
    versions = NoteVersion.objects.filter(note=note).exclude(
        title=note.title, content=note.content
    )

    return render(
        request, "notes/note_history.html", {"note": note, "versions": versions}
    )


@login_required
def render_markdown(request):
    """Render markdown content using the same filter as server-side rendering"""
    if request.method == "POST":
        from .templatetags.markdown_extras import markdown_format
        from django.http import HttpResponse

        content = request.POST.get("content", "")
        rendered_html = markdown_format(content)

        return HttpResponse(rendered_html, content_type="text/html")

    from django.http import HttpResponseNotAllowed

    return HttpResponseNotAllowed(["POST"])


@login_required
def profile(request):
    """User profile page with password change functionality"""
    password_form = CustomPasswordChangeForm(user=request.user)
    profile_form = CustomUserChangeForm(instance=request.user)

    if request.method == "POST":
        if "change_password" in request.POST:
            password_form = CustomPasswordChangeForm(
                user=request.user, data=request.POST
            )
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, "Your password was successfully updated!")
                return redirect("profile")
            else:
                messages.error(request, "Please correct the errors below.")
        elif "update_profile" in request.POST:
            profile_form = CustomUserChangeForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile was successfully updated!")
                return redirect("profile")
            else:
                messages.error(request, "Please correct the errors below.")

    return render(
        request,
        "notes/profile.html",
        {"password_form": password_form, "profile_form": profile_form},
    )


@login_required
def tag_autocomplete(request):
    """API endpoint for tag autocomplete"""
    query = request.GET.get("q", "").strip()

    if not query:
        tags = Tag.objects.filter(user=request.user)[:20]
    else:
        # Case-insensitive search
        tags = Tag.objects.filter(user=request.user, name__icontains=query)[:20]

    results = [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in tags]
    return JsonResponse({"results": results})


# Friends system views


@login_required
def search_users(request):
    """Search for users by username or email"""
    query = request.GET.get("q", "").strip()
    results = []

    if query:
        # Search by username or email (case-insensitive)
        users = CustomUser.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        ).exclude(id=request.user.id)[:20]

        # Check friend status for each user
        for user in users:
            is_friend = Friendship.are_friends(request.user, user)

            # Check if there's a pending request
            pending_request = FriendRequest.objects.filter(
                Q(from_user=request.user, to_user=user, status="pending")
                | Q(from_user=user, to_user=request.user, status="pending")
            ).first()

            results.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_friend": is_friend,
                    "pending_request": pending_request.id if pending_request else None,
                    "pending_from_me": (
                        pending_request.from_user == request.user
                        if pending_request
                        else False
                    ),
                }
            )

    return render(
        request, "notes/search_users.html", {"query": query, "results": results}
    )


@login_required
def send_friend_request(request, user_id):
    """Send a friend request to another user"""
    to_user = get_object_or_404(CustomUser, id=user_id)

    if to_user == request.user:
        messages.error(request, "You cannot send a friend request to yourself.")
        return redirect("search_users")

    # Check if already friends
    if Friendship.are_friends(request.user, to_user):
        messages.info(request, f"You are already friends with {to_user.username}.")
        return redirect("friends_list")

    # Check if there's already a pending request
    existing_request = (
        FriendRequest.objects.filter(
            Q(from_user=request.user, to_user=to_user)
            | Q(from_user=to_user, to_user=request.user)
        )
        .filter(status="pending")
        .first()
    )

    if existing_request:
        messages.info(request, "There is already a pending friend request.")
        return redirect("search_users")

    # Create friend request
    FriendRequest.objects.create(from_user=request.user, to_user=to_user)
    messages.success(request, f"Friend request sent to {to_user.username}!")

    return redirect("search_users")


@login_required
def accept_friend_request(request, request_id):
    """Accept a friend request"""
    friend_request = get_object_or_404(
        FriendRequest, id=request_id, to_user=request.user, status="pending"
    )

    # Update request status
    friend_request.status = "accepted"
    friend_request.save()

    # Create friendship (ensure user1 is always the one with lower ID to avoid duplicates)
    user1, user2 = sorted(
        [friend_request.from_user, friend_request.to_user], key=lambda u: u.id
    )
    Friendship.objects.get_or_create(user1=user1, user2=user2)

    messages.success(
        request, f"You are now friends with {friend_request.from_user.username}!"
    )
    return redirect("friends_list")


@login_required
def reject_friend_request(request, request_id):
    """Reject a friend request"""
    friend_request = get_object_or_404(
        FriendRequest, id=request_id, to_user=request.user, status="pending"
    )

    friend_request.status = "rejected"
    friend_request.save()

    messages.info(request, "Friend request rejected.")
    return redirect("friends_list")


@login_required
def friends_list(request):
    """Display list of friends and pending friend requests"""
    friends = Friendship.get_friends(request.user)
    pending_requests = FriendRequest.objects.filter(
        to_user=request.user, status="pending"
    )
    sent_requests = FriendRequest.objects.filter(
        from_user=request.user, status="pending"
    )

    return render(
        request,
        "notes/friends_list.html",
        {
            "friends": friends,
            "pending_requests": pending_requests,
            "sent_requests": sent_requests,
        },
    )


@login_required
def friend_chat(request, friend_id):
    """Chat with a friend"""
    friend = get_object_or_404(CustomUser, id=friend_id)

    # Verify friendship
    if not Friendship.are_friends(request.user, friend):
        messages.error(request, "You can only chat with friends.")
        return redirect("friends_list")

    # Handle message sending
    if request.method == "POST":
        message_text = request.POST.get("message", "").strip()
        if message_text:
            ChatMessage.objects.create(
                from_user=request.user, to_user=friend, message=message_text
            )
            return redirect("friend_chat", friend_id=friend_id)

    # Get all messages between the two users
    chat_messages = ChatMessage.objects.filter(
        Q(from_user=request.user, to_user=friend)
        | Q(from_user=friend, to_user=request.user)
    ).order_by("created_at")

    return render(
        request,
        "notes/friend_chat.html",
        {
            "friend": friend,
            "chat_messages": chat_messages,
        },
    )


@login_required
def shared_notes_list(request, friend_id):
    """List shared notes with a friend"""
    friend = get_object_or_404(CustomUser, id=friend_id)

    # Verify friendship
    if not Friendship.are_friends(request.user, friend):
        messages.error(request, "You can only view shared notes with friends.")
        return redirect("friends_list")

    # Get shared notes (both directions)
    shared_notes = SharedNote.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    )

    # Filter by folder if specified
    folder_id = request.GET.get("folder")
    current_folder = None
    if folder_id == "all":  # Show all shared notes regardless of folder
        # Don't filter by folder, show all shared notes
        pass
    elif folder_id:
        try:
            current_folder = SharedFolder.objects.get(id=folder_id)
            if not current_folder.has_access(request.user):
                messages.error(request, "Access denied to folder")
                return redirect("shared_notes_list", friend_id=friend_id)
            shared_notes = shared_notes.filter(folder=current_folder)
        except SharedFolder.DoesNotExist:
            pass
    else:  # Default to Home (no folder) when no folder parameter or empty string
        shared_notes = shared_notes.filter(folder__isnull=True)

    # Get all shared folders for this friendship
    shared_folders = SharedFolder.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    )
    
    # Get subfolders for the current folder if viewing a specific folder
    # For Home view (no current folder), show root-level folders
    subfolders = []
    if current_folder:
        subfolders = SharedFolder.objects.filter(
            Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user),
            parent=current_folder
        ).order_by('name')
    elif folder_id != "all":  # Home view - show root folders
        subfolders = SharedFolder.objects.filter(
            Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user),
            parent__isnull=True
        ).order_by('name')
    
    # Serialize folders for JavaScript
    import json
    shared_folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in shared_folders
    ])

    return render(
        request,
        "notes/shared_notes_list.html",
        {
            "friend": friend,
            "shared_notes": shared_notes,
            "shared_folders": shared_folders,
            "shared_folders_json": shared_folders_json,
            "current_folder": current_folder,
            "subfolders": subfolders,
        },
    )


@login_required
def shared_note_create(request, friend_id):
    """Create a shared note with a friend"""
    friend = get_object_or_404(CustomUser, id=friend_id)

    # Verify friendship
    if not Friendship.are_friends(request.user, friend):
        messages.error(request, "You can only create shared notes with friends.")
        return redirect("friends_list")

    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        encrypted_content = request.POST.get("encrypted_content")
        is_locked = request.POST.get("is_locked") == "on"
        salt = request.POST.get("salt", "")
        tags_data = request.POST.get("tags", "")
        folder_id = request.POST.get("folder")
        note_type = request.POST.get("note_type", "markdown")

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content
        
        # Canvas notes cannot be encrypted
        if note_type == "canvas" and is_locked:
            messages.error(request, "Canvas notes cannot be encrypted.")
            return redirect("shared_note_create", friend_id=friend_id)

        if title:
            # For canvas notes, content is not required initially
            if not final_content and note_type != "canvas":
                messages.error(request, "Content is required.")
                return redirect("shared_note_create", friend_id=friend_id)
            
            # Ensure consistent user ordering
            user1, user2 = sorted([request.user, friend], key=lambda u: u.id)

            shared_note = SharedNote(
                user1=user1,
                user2=user2,
                title=title,
                content=final_content or "",
                note_type=note_type,
                is_locked=is_locked if note_type != "canvas" else False,
                salt=salt if note_type != "canvas" else "",
                created_by=request.user,
            )

            # Assign folder if specified
            if folder_id:
                try:
                    folder = SharedFolder.objects.get(id=folder_id)
                    if folder.has_access(request.user):
                        shared_note.folder = folder
                except SharedFolder.DoesNotExist:
                    pass

            shared_note.save()

            # Process tags (only for markdown notes)
            if note_type == "markdown" and tags_data:
                import json

                try:
                    tags_list = json.loads(tags_data)
                    for tag_data in tags_list:
                        tag_name = tag_data.get("name", "").strip()
                        tag_color = tag_data.get("color", "#3b82f6")
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            # Tags can be shared between users via shared notes
                            try:
                                tag = Tag.objects.get(
                                    user=request.user, name__iexact=tag_name
                                )
                                # Update color if changed
                                if tag.color != tag_color:
                                    tag.color = tag_color
                                    tag.save()
                            except Tag.DoesNotExist:
                                tag = Tag.objects.create(
                                    user=request.user, name=tag_name, color=tag_color
                                )
                            shared_note.tags.add(tag)
                except (json.JSONDecodeError, ValueError):
                    pass

            messages.success(request, "Shared note created successfully!")
            return redirect("shared_note_view", note_id=shared_note.id)
        else:
            messages.error(request, "Title is required.")

    # Get tags that are used in shared notes with this friend
    user_tags = Tag.objects.filter(
        Q(user=request.user) | Q(user=friend),
        shared_notes__in=SharedNote.objects.filter(
            Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
        ),
    ).distinct()

    # Get shared folders for this friendship
    shared_folders = SharedFolder.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    )

    # Get current folder from query param if provided
    current_folder_id = request.GET.get("folder")
    current_folder = None
    if current_folder_id:
        try:
            current_folder = SharedFolder.objects.get(id=current_folder_id)
            if not current_folder.has_access(request.user):
                current_folder = None
        except SharedFolder.DoesNotExist:
            pass

    # Serialize folders for JavaScript
    import json
    shared_folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in shared_folders
    ])

    return render(
        request,
        "notes/shared_note_form.html",
        {
            "friend": friend,
            "user_tags": user_tags,
            "shared_folders": shared_folders,
            "shared_folders_json": shared_folders_json,
            "current_folder": current_folder,
        },
    )


@login_required
def shared_note_view(request, note_id):
    """View a shared note"""
    shared_note = get_object_or_404(SharedNote, id=note_id)

    # Verify access
    if not shared_note.has_access(request.user):
        messages.error(request, "You don't have access to this note.")
        return redirect("friends_list")

    # Determine who the friend is
    friend = (
        shared_note.user2 if shared_note.user1 == request.user else shared_note.user1
    )
    all_notes = SharedNote.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    ).order_by("-updated_at")
    
    # For canvas notes, get elements as JSON
    elements_json = "[]"
    if shared_note.note_type == 'canvas':
        import json
        from .models import CanvasElement
        elements = CanvasElement.objects.filter(shared_note=shared_note)
        elements_json = json.dumps([element.to_dict() for element in elements])
    
    return render(
        request,
        "notes/shared_note_view.html",
        {
            "shared_note": shared_note,
            "all_notes": all_notes,
            "friend": friend,
            "elements_json": elements_json,
        },
    )


@login_required
def shared_note_edit(request, note_id):
    """Edit a shared note"""
    shared_note = get_object_or_404(SharedNote, id=note_id)

    # Verify access
    if not shared_note.has_access(request.user):
        messages.error(request, "You don't have access to this note.")
        return redirect("friends_list")

    friend = (
        shared_note.user2 if shared_note.user1 == request.user else shared_note.user1
    )

    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        encrypted_content = request.POST.get("encrypted_content")
        is_locked = request.POST.get("is_locked") == "on"
        salt = request.POST.get("salt", shared_note.salt)
        tags_data = request.POST.get("tags", "")
        folder_id = request.POST.get("folder")

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        # Check if this is an AJAX request for checkbox update
        is_ajax_update = request.POST.get("ajax_update") == "true"

        # For AJAX updates, only require content; for normal edits, require both title and content
        if (is_ajax_update and final_content) or (title and final_content):
            if not is_ajax_update and title:
                shared_note.title = title
            shared_note.content = final_content
            shared_note.is_locked = is_locked
            shared_note.salt = salt

            # Update folder if specified (only for non-AJAX updates)
            if not is_ajax_update:
                if folder_id:
                    try:
                        folder = SharedFolder.objects.get(id=folder_id)
                        if folder.has_access(request.user):
                            shared_note.folder = folder
                    except SharedFolder.DoesNotExist:
                        shared_note.folder = None
                elif folder_id == "":  # Empty string means remove folder
                    shared_note.folder = None

            shared_note.save()

            # Check if this is an AJAX request for checkbox update
            if is_ajax_update:
                return JsonResponse({"success": True})

            # Process tags (only for non-AJAX updates)
            shared_note.tags.clear()  # Remove existing tags
            if tags_data:
                import json

                try:
                    tags_list = json.loads(tags_data)
                    for tag_data in tags_list:
                        tag_name = tag_data.get("name", "").strip()
                        tag_color = tag_data.get("color", "#3b82f6")
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            try:
                                tag = Tag.objects.get(
                                    user=request.user, name__iexact=tag_name
                                )
                                # Update color if changed
                                if tag.color != tag_color:
                                    tag.color = tag_color
                                    tag.save()
                            except Tag.DoesNotExist:
                                tag = Tag.objects.create(
                                    user=request.user, name=tag_name, color=tag_color
                                )
                            shared_note.tags.add(tag)
                except (json.JSONDecodeError, ValueError):
                    pass

            messages.success(request, "Shared note updated successfully!")
            return redirect("shared_note_view", note_id=note_id)
        else:
            messages.error(request, "Title and content are required.")
    # find all tags that have shared notes between the two users, meaning tags that are present in at least one of their shared notes
    user_tags = Tag.objects.filter(
        Q(user=request.user) | Q(user=friend),
        shared_notes__in=SharedNote.objects.filter(
            Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
        ),
    ).distinct()

    # Get shared folders for this friendship
    shared_folders = SharedFolder.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    )

    # Serialize folders for JavaScript
    import json
    shared_folders_json = json.dumps([
        {"id": folder.id, "name": folder.name, "parent_id": folder.parent.id if folder.parent else None}
        for folder in shared_folders
    ])

    return render(
        request,
        "notes/shared_note_form.html",
        {
            "shared_note": shared_note,
            "user_tags": user_tags,
            "friend": friend,
            "shared_folders": shared_folders,
            "shared_folders_json": shared_folders_json,
        },
    )


@login_required
def shared_note_delete(request, note_id):
    """Delete a shared note"""
    shared_note = get_object_or_404(SharedNote, id=note_id)

    # Verify access
    if not shared_note.has_access(request.user):
        messages.error(request, "You don't have access to this note.")
        return redirect("friends_list")

    friend = (
        shared_note.user2 if shared_note.user1 == request.user else shared_note.user1
    )

    if request.method == "POST":
        friend_id = friend.id
        shared_note.delete()
        messages.success(request, "Shared note deleted successfully!")
        return redirect("shared_notes_list", friend_id=friend_id)

    return render(
        request,
        "notes/shared_note_confirm_delete.html",
        {
            "shared_note": shared_note,
            "friend": friend,
        },
    )


# Folder management views


@login_required
def folder_create(request):
    """Create a new folder"""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        parent_id = request.POST.get("parent")

        if not name:
            return JsonResponse({"success": False, "error": "Folder name is required"})

        parent = None
        if parent_id:
            try:
                parent = Folder.objects.get(id=parent_id, user=request.user)
            except Folder.DoesNotExist:
                return JsonResponse({"success": False, "error": "Parent folder not found"})

        # Check if folder with same name already exists in parent
        if Folder.objects.filter(user=request.user, name=name, parent=parent).exists():
            return JsonResponse({"success": False, "error": "A folder with this name already exists"})

        folder = Folder.objects.create(user=request.user, name=name, parent=parent)
        return JsonResponse({
            "success": True,
            "folder": {
                "id": folder.id,
                "name": folder.name,
                "parent_id": folder.parent.id if folder.parent else None,
            }
        })

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def folder_rename(request, folder_id):
    """Rename a folder"""
    folder = get_object_or_404(Folder, id=folder_id, user=request.user)

    if request.method == "POST":
        new_name = request.POST.get("name", "").strip()

        if not new_name:
            return JsonResponse({"success": False, "error": "Folder name is required"})

        # Check if folder with same name already exists in parent
        if Folder.objects.filter(
            user=request.user, name=new_name, parent=folder.parent
        ).exclude(id=folder.id).exists():
            return JsonResponse({"success": False, "error": "A folder with this name already exists"})

        folder.name = new_name
        folder.save()
        return JsonResponse({"success": True, "folder": {"id": folder.id, "name": folder.name}})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def folder_delete(request, folder_id):
    """Delete a folder (notes inside will be moved to parent or root)"""
    folder = get_object_or_404(Folder, id=folder_id, user=request.user)

    if request.method == "POST":
        # Move all notes to parent folder (or None if root folder)
        Note.objects.filter(folder=folder).update(folder=folder.parent)
        
        # Move all subfolders to parent folder (or None if root folder)
        Folder.objects.filter(parent=folder).update(parent=folder.parent)
        
        folder.delete()
        messages.success(request, f"Folder '{folder.name}' deleted successfully!")
        return redirect("note_list")

    return render(request, "notes/folder_confirm_delete.html", {"folder": folder})


@login_required
def note_move(request, note_id):
    """Move a note to a different folder"""
    note = get_object_or_404(Note, id=note_id, user=request.user)

    if request.method == "POST":
        folder_id = request.POST.get("folder")

        if folder_id:
            try:
                folder = Folder.objects.get(id=folder_id, user=request.user)
                note.folder = folder
            except Folder.DoesNotExist:
                return JsonResponse({"success": False, "error": "Folder not found"})
        else:
            note.folder = None

        note.save()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "error": "Invalid request method"})


# Shared folder management views


@login_required
def shared_folder_create(request, friend_id):
    """Create a new shared folder with a friend"""
    friend = get_object_or_404(CustomUser, id=friend_id)

    if not Friendship.are_friends(request.user, friend):
        return JsonResponse({"success": False, "error": "You can only create shared folders with friends"})

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        parent_id = request.POST.get("parent")

        if not name:
            return JsonResponse({"success": False, "error": "Folder name is required"})

        parent = None
        if parent_id:
            try:
                parent = SharedFolder.objects.get(id=parent_id)
                if not parent.has_access(request.user):
                    return JsonResponse({"success": False, "error": "Access denied to parent folder"})
            except SharedFolder.DoesNotExist:
                return JsonResponse({"success": False, "error": "Parent folder not found"})

        # Ensure consistent user ordering
        user1, user2 = sorted([request.user, friend], key=lambda u: u.id)

        # Check if folder with same name already exists in parent
        if SharedFolder.objects.filter(
            user1=user1, user2=user2, name=name, parent=parent
        ).exists():
            return JsonResponse({"success": False, "error": "A folder with this name already exists"})

        folder = SharedFolder.objects.create(
            user1=user1, user2=user2, name=name, parent=parent
        )
        return JsonResponse({
            "success": True,
            "folder": {
                "id": folder.id,
                "name": folder.name,
                "parent_id": folder.parent.id if folder.parent else None,
            }
        })

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def shared_folder_rename(request, folder_id):
    """Rename a shared folder"""
    folder = get_object_or_404(SharedFolder, id=folder_id)

    if not folder.has_access(request.user):
        return JsonResponse({"success": False, "error": "Access denied"})

    if request.method == "POST":
        new_name = request.POST.get("name", "").strip()

        if not new_name:
            return JsonResponse({"success": False, "error": "Folder name is required"})

        # Check if folder with same name already exists in parent
        if SharedFolder.objects.filter(
            user1=folder.user1, user2=folder.user2, name=new_name, parent=folder.parent
        ).exclude(id=folder.id).exists():
            return JsonResponse({"success": False, "error": "A folder with this name already exists"})

        folder.name = new_name
        folder.save()
        return JsonResponse({"success": True, "folder": {"id": folder.id, "name": folder.name}})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def shared_folder_delete(request, folder_id):
    """Delete a shared folder"""
    folder = get_object_or_404(SharedFolder, id=folder_id)

    if not folder.has_access(request.user):
        messages.error(request, "Access denied")
        return redirect("friends_list")

    friend = folder.user2 if folder.user1 == request.user else folder.user1

    if request.method == "POST":
        # Move all notes to parent folder (or None if root folder)
        SharedNote.objects.filter(folder=folder).update(folder=folder.parent)
        
        # Move all subfolders to parent folder (or None if root folder)
        SharedFolder.objects.filter(parent=folder).update(parent=folder.parent)
        
        folder.delete()
        messages.success(request, f"Folder '{folder.name}' deleted successfully!")
        return redirect("shared_notes_list", friend_id=friend.id)

    return render(
        request,
        "notes/shared_folder_confirm_delete.html",
        {"folder": folder, "friend": friend},
    )


@login_required
def shared_note_move(request, note_id):
    """Move a shared note to a different folder"""
    shared_note = get_object_or_404(SharedNote, id=note_id)

    if not shared_note.has_access(request.user):
        return JsonResponse({"success": False, "error": "Access denied"})

    if request.method == "POST":
        folder_id = request.POST.get("folder")

        if folder_id:
            try:
                folder = SharedFolder.objects.get(id=folder_id)
                if not folder.has_access(request.user):
                    return JsonResponse({"success": False, "error": "Access denied to folder"})
                shared_note.folder = folder
            except SharedFolder.DoesNotExist:
                return JsonResponse({"success": False, "error": "Folder not found"})
        else:
            shared_note.folder = None

        shared_note.save()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "error": "Invalid request method"})


# Canvas element management views


@login_required
def canvas_element_create(request):
    """Create a new canvas element"""
    if request.method == "POST":
        import json
        from .models import CanvasElement
        
        try:
            data = json.loads(request.body)
            
            element_type = data.get("element_type")
            note_id = data.get("note_id")
            shared_note_id = data.get("shared_note_id")
            
            # Validate element type
            if element_type not in ["textbox", "image"]:
                return JsonResponse({"success": False, "error": "Invalid element type"})
            
            # Create the element
            element = CanvasElement(
                element_type=element_type,
                x=data.get("x", 0),
                y=data.get("y", 0),
                width=data.get("width", 200),
                height=data.get("height", 100),
                z_index=data.get("z_index", 0),
            )
            
            # For textbox elements
            if element_type == "textbox":
                element.text_content = data.get("text_content", "")
            
            # Associate with note or shared note
            if note_id:
                try:
                    note = Note.objects.get(id=note_id, user=request.user)
                    if note.note_type != 'canvas':
                        return JsonResponse({"success": False, "error": "Note is not a canvas note"})
                    element.note = note
                except Note.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Note not found"})
            elif shared_note_id:
                try:
                    shared_note = SharedNote.objects.get(id=shared_note_id)
                    if not shared_note.has_access(request.user):
                        return JsonResponse({"success": False, "error": "Access denied"})
                    if shared_note.note_type != 'canvas':
                        return JsonResponse({"success": False, "error": "Shared note is not a canvas note"})
                    element.shared_note = shared_note
                except SharedNote.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Shared note not found"})
            else:
                return JsonResponse({"success": False, "error": "Note or shared note ID required"})
            
            element.save()
            
            return JsonResponse({"success": True, "element": element.to_dict()})
        except Exception as e:
            # Log the error for debugging but don't expose stack trace to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating canvas element: {str(e)}", exc_info=True)
            return JsonResponse({"success": False, "error": "Failed to create element"})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def canvas_element_update(request, element_id):
    """Update a canvas element"""
    if request.method == "POST":
        import json
        from .models import CanvasElement
        
        try:
            element = get_object_or_404(CanvasElement, id=element_id)
            
            # Verify access
            if element.note:
                if element.note.user != request.user:
                    return JsonResponse({"success": False, "error": "Access denied"})
            elif element.shared_note:
                if not element.shared_note.has_access(request.user):
                    return JsonResponse({"success": False, "error": "Access denied"})
            
            data = json.loads(request.body)
            
            # Update position and size
            if "x" in data:
                element.x = data["x"]
            if "y" in data:
                element.y = data["y"]
            if "width" in data:
                element.width = data["width"]
            if "height" in data:
                element.height = data["height"]
            if "z_index" in data:
                element.z_index = data["z_index"]
            
            # Update content for textbox
            if element.element_type == "textbox" and "text_content" in data:
                element.text_content = data["text_content"]
            
            element.save()
            
            # Update the parent note's updated_at timestamp
            if element.note:
                element.note.save()
            elif element.shared_note:
                element.shared_note.save()
            
            return JsonResponse({"success": True, "element": element.to_dict()})
        except Exception as e:
            # Log the error for debugging but don't expose stack trace to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating canvas element: {str(e)}", exc_info=True)
            return JsonResponse({"success": False, "error": "Failed to update element"})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def canvas_element_delete(request, element_id):
    """Delete a canvas element"""
    if request.method == "POST":
        from .models import CanvasElement
        
        try:
            element = get_object_or_404(CanvasElement, id=element_id)
            
            # Verify access
            if element.note:
                if element.note.user != request.user:
                    return JsonResponse({"success": False, "error": "Access denied"})
            elif element.shared_note:
                if not element.shared_note.has_access(request.user):
                    return JsonResponse({"success": False, "error": "Access denied"})
            
            # Update the parent note's updated_at timestamp before deleting element
            if element.note:
                element.note.save()
            elif element.shared_note:
                element.shared_note.save()
            
            element.delete()
            
            return JsonResponse({"success": True})
        except Exception as e:
            # Log the error for debugging but don't expose stack trace to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting canvas element: {str(e)}", exc_info=True)
            return JsonResponse({"success": False, "error": "Failed to delete element"})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def canvas_element_upload_image(request):
    """Upload an image for a canvas element"""
    if request.method == "POST":
        from .models import CanvasElement
        
        try:
            note_id = request.POST.get("note_id")
            shared_note_id = request.POST.get("shared_note_id")
            image_file = request.FILES.get("image")
            
            if not image_file:
                return JsonResponse({"success": False, "error": "No image file provided"})
            
            # Create the image element
            element = CanvasElement(
                element_type="image",
                x=int(request.POST.get("x", 0)),
                y=int(request.POST.get("y", 0)),
                width=int(request.POST.get("width", 200)),
                height=int(request.POST.get("height", 200)),
                z_index=int(request.POST.get("z_index", 0)),
                image=image_file
            )
            
            # Associate with note or shared note
            if note_id:
                try:
                    note = Note.objects.get(id=note_id, user=request.user)
                    if note.note_type != 'canvas':
                        return JsonResponse({"success": False, "error": "Note is not a canvas note"})
                    element.note = note
                except Note.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Note not found"})
            elif shared_note_id:
                try:
                    shared_note = SharedNote.objects.get(id=shared_note_id)
                    if not shared_note.has_access(request.user):
                        return JsonResponse({"success": False, "error": "Access denied"})
                    if shared_note.note_type != 'canvas':
                        return JsonResponse({"success": False, "error": "Shared note is not a canvas note"})
                    element.shared_note = shared_note
                except SharedNote.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Shared note not found"})
            else:
                return JsonResponse({"success": False, "error": "Note or shared note ID required"})
            
            element.save()
            
            return JsonResponse({"success": True, "element": element.to_dict()})
        except Exception as e:
            # Log the error for debugging but don't expose stack trace to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error uploading image: {str(e)}", exc_info=True)
            return JsonResponse({"success": False, "error": "Failed to upload image"})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})
