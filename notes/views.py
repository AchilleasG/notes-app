from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from .models import Note


@login_required
def note_list(request):
    notes = Note.objects.filter(user=request.user)
    return render(request, "notes/note_list.html", {"notes": notes})


@login_required
def note_create(request):
    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        is_locked = request.POST.get("is_locked") == "on"
        lock_password = request.POST.get("lock_password")

        if title and content:
            if is_locked and not lock_password:
                messages.error(request, "Password is required for locked notes.")
                return render(
                    request,
                    "notes/note_form.html",
                    {"title": title, "content": content, "is_locked": is_locked},
                )

            note = Note(user=request.user, title=title, content=content)

            if is_locked:
                note.encrypt_content(lock_password)

            note.save()
            messages.success(request, "Note created successfully!")
            return redirect("note_list")
        else:
            messages.error(request, "Title and content are required.")
    return render(request, "notes/note_form.html")


@login_required
def note_edit(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    # If note is locked, redirect to unlock page first
    if note.is_locked and "unlocked_content" not in request.session.get(
        f"note_{pk}", {}
    ):
        return redirect("note_unlock", pk=pk)

    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")

        if title and content:
            # If the note was locked, we need to re-encrypt with the same password
            if note.is_locked:
                unlock_password = request.session.get(f"note_{pk}", {}).get("password")
                if unlock_password:
                    note.title = title  # Title is not encrypted
                    note.content = content
                    note.encrypt_content(unlock_password)  # Only content gets encrypted
                else:
                    messages.error(
                        request, "Session expired. Please unlock the note again."
                    )
                    return redirect("note_unlock", pk=pk)
            else:
                note.title = title
                note.content = content

            note.save()

            # Clear session data
            if f"note_{pk}" in request.session:
                del request.session[f"note_{pk}"]

            messages.success(request, "Note updated successfully!")
            return redirect("note_list")
        else:
            messages.error(request, "Title and content are required.")

    # Prepare note data for display
    if note.is_locked:
        decrypted = request.session.get(f"note_{pk}", {}).get("unlocked_content", {})
        note_data = {
            "pk": note.pk,
            "title": note.title,  # Title is not encrypted anymore
            "content": decrypted.get("content", ""),  # Only content needs decryption
            "is_locked": True,
        }
    else:
        note_data = note

    return render(request, "notes/note_form.html", {"note": note_data})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    if request.method == "POST":
        note.delete()

        # Clear session data if exists
        if f"note_{pk}" in request.session:
            del request.session[f"note_{pk}"]

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

    # If note is locked, check if content is unlocked in session
    if note.is_locked:
        if (
            f"note_{pk}" not in request.session
            or "unlocked_content" not in request.session.get(f"note_{pk}", {})
        ):
            return redirect("note_unlock", pk=pk) + "?next=note_view"

        decrypted = request.session[f"note_{pk}"]["unlocked_content"]
        note_data = {
            "pk": note.pk,
            "title": note.title,  # Title is not encrypted anymore
            "content": decrypted["content"],  # Only content needs decryption
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "is_locked": True,
        }
    else:
        note_data = note

    return render(request, "notes/note_view.html", {"note": note_data})


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect("note_list")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})
