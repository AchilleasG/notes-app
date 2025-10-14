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
)
from .forms import CustomUserChangeForm, CustomPasswordChangeForm


@login_required
def note_list(request):
    notes = Note.objects.filter(user=request.user)

    # Filter by tags if specified
    tag_filter = request.GET.get("tags", "").strip()
    if tag_filter:
        # Split by comma and filter (case-insensitive)
        tag_names = [t.strip() for t in tag_filter.split(",") if t.strip()]
        for tag_name in tag_names:
            notes = notes.filter(tags__name__iexact=tag_name)
        notes = notes.distinct()

    # Get all tags for the current user
    user_tags = Tag.objects.filter(user=request.user)

    return render(
        request,
        "notes/note_list.html",
        {"notes": notes, "user_tags": user_tags, "selected_tags": tag_filter},
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

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        if title and final_content:
            note = Note(
                user=request.user,
                title=title,
                content=final_content,
                is_locked=is_locked,
                salt=salt,
            )

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

            note.save()

            # Process tags
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

            messages.success(request, "Note created successfully!")
            return redirect("note_list")
        else:
            messages.error(request, "Title and content are required.")

    # Get all user tags for autocomplete
    user_tags = Tag.objects.filter(user=request.user)
    return render(request, "notes/note_form.html", {"user_tags": user_tags})


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

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        if title and final_content:
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

            # Save current version to history before updating
            NoteVersion.objects.create(
                note=note,
                title=note.title,
                content=note.content,
                is_locked=note.is_locked,
                salt=note.salt,
            )

            # Update note
            note.title = title
            note.content = final_content
            note.is_locked = is_locked
            note.salt = salt
            note.save()

            # Process tags
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

            # Check if this is an AJAX request for checkbox update
            if request.POST.get("ajax_update") == "true":
                return JsonResponse({"success": True})

            messages.success(request, "Note updated successfully!")
            return redirect("note_view", pk=pk)
        else:
            messages.error(request, "Title and content are required.")

    # Return note data for editing (client will handle decryption if needed)
    user_tags = Tag.objects.filter(user=request.user)
    return render(
        request, "notes/note_form.html", {"note": note, "user_tags": user_tags}
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

    # Pass note data to client (client will handle decryption if needed)
    return render(
        request,
        "notes/note_view.html",
        {
            "note": note,
            "all_notes": all_notes,
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

    return render(
        request,
        "notes/shared_notes_list.html",
        {
            "friend": friend,
            "shared_notes": shared_notes,
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

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        if title and final_content:
            # Ensure consistent user ordering
            user1, user2 = sorted([request.user, friend], key=lambda u: u.id)

            shared_note = SharedNote(
                user1=user1,
                user2=user2,
                title=title,
                content=final_content,
                is_locked=is_locked,
                salt=salt,
                created_by=request.user,
            )
            shared_note.save()

            # Process tags
            if tags_data:
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
            return redirect("shared_notes_list", friend_id=friend_id)
        else:
            messages.error(request, "Title and content are required.")

    # Get tags that are used in shared notes with this friend
    user_tags = Tag.objects.filter(
        Q(user=request.user) | Q(user=friend),
        shared_notes__in=SharedNote.objects.filter(
            Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
        )
    ).distinct()
    
    return render(request, "notes/shared_note_form.html", {"friend": friend, "user_tags": user_tags})


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
    return render(
        request,
        "notes/shared_note_view.html",
        {"shared_note": shared_note, "all_notes": all_notes, "friend": friend},
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

        # Use encrypted content if provided, otherwise use regular content
        final_content = encrypted_content if encrypted_content else content

        if title and final_content:
            shared_note.title = title
            shared_note.content = final_content
            shared_note.is_locked = is_locked
            shared_note.salt = salt
            shared_note.save()

            # Process tags
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
        )
    ).distinct()
    
    return render(
        request,
        "notes/shared_note_form.html",
        {"shared_note": shared_note, "user_tags": user_tags, "friend": friend},
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
