from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from .models import Note, NoteVersion, Tag
from .forms import CustomUserChangeForm, CustomPasswordChangeForm


@login_required
def note_list(request):
    notes = Note.objects.filter(user=request.user)
    
    # Filter by tags if specified
    tag_filter = request.GET.get('tags', '').strip()
    if tag_filter:
        # Split by comma and filter (case-insensitive)
        tag_names = [t.strip() for t in tag_filter.split(',') if t.strip()]
        for tag_name in tag_names:
            notes = notes.filter(tags__name__iexact=tag_name)
        notes = notes.distinct()
    
    # Get all tags for the current user
    user_tags = Tag.objects.filter(user=request.user)
    
    return render(request, "notes/note_list.html", {
        "notes": notes,
        "user_tags": user_tags,
        "selected_tags": tag_filter
    })


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
                        tag_name = tag_data.get('name', '').strip()
                        tag_color = tag_data.get('color', '#3b82f6')
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            tag, created = Tag.objects.get_or_create(
                                user=request.user,
                                name__iexact=tag_name,
                                defaults={'name': tag_name, 'color': tag_color}
                            )
                            # Update color if tag exists but color changed
                            if not created and tag.color != tag_color:
                                tag.color = tag_color
                                tag.save()
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
                        tag_name = tag_data.get('name', '').strip()
                        tag_color = tag_data.get('color', '#3b82f6')
                        if tag_name:
                            # Get or create tag (case-insensitive)
                            tag, created = Tag.objects.get_or_create(
                                user=request.user,
                                name__iexact=tag_name,
                                defaults={'name': tag_name, 'color': tag_color}
                            )
                            # Update color if tag exists but color changed
                            if not created and tag.color != tag_color:
                                tag.color = tag_color
                                tag.save()
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
    return render(request, "notes/note_form.html", {"note": note, "user_tags": user_tags})


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
    versions = NoteVersion.objects.filter(note=note)

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
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
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
    query = request.GET.get('q', '').strip()
    
    if not query:
        tags = Tag.objects.filter(user=request.user)[:20]
    else:
        # Case-insensitive search
        tags = Tag.objects.filter(user=request.user, name__icontains=query)[:20]
    
    results = [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in tags]
    return JsonResponse({"results": results})
