# Canvas Notes Feature Implementation

## Overview

This document describes the implementation of the canvas notes feature for the personal notebook application. Canvas notes provide a freeform whiteboard-like interface where users can add and position text boxes and images anywhere on the canvas.

## Key Features

### 1. Note Type Selection
- Users can choose between "Markdown Note" (📝) and "Canvas Note" (🎨) when creating a new note
- Note type is set at creation and cannot be changed later
- Available for both personal notes and shared notes

### 2. Canvas Elements
Two types of elements are supported:

#### Text Boxes
- Plain text only (no markdown formatting)
- Draggable and resizable
- Auto-saves content on text changes (500ms debounce)

#### Images
- Upload via file dialog
- Draggable and resizable
- Stored using Django's ImageField in the `canvas_images/` directory

### 3. Canvas Interactions
- **Drag to Move**: Click and drag any element to reposition
- **Resize**: Use corner handles (nw, ne, sw, se) to resize elements
- **Grid Snap**: Optional grid overlay with snap-to-grid functionality
- **Auto-save**: All changes (position, size, content) are automatically saved
- **Z-index**: Elements can be layered (future enhancement for reordering)

### 4. Mobile Support
- Touch-friendly with larger resize handles on mobile devices
- Responsive toolbar that adapts to screen size
- Font size adjusted to prevent iOS zoom on input focus

### 5. Security
- Canvas notes **cannot be encrypted** (as specified in requirements)
- Access control enforced at the backend (users can only modify their own notes)
- No stack trace exposure in error messages
- Proper CSRF protection on all API endpoints

## Architecture

### Backend (Django)

#### Models
```python
# notes/models.py

class Note(models.Model):
    # ... existing fields ...
    note_type = models.CharField(
        max_length=20, 
        choices=[('markdown', 'Markdown Note'), ('canvas', 'Canvas Note')],
        default='markdown'
    )

class SharedNote(models.Model):
    # ... existing fields ...
    note_type = models.CharField(
        max_length=20,
        choices=[('markdown', 'Markdown Note'), ('canvas', 'Canvas Note')],
        default='markdown'
    )

class CanvasElement(models.Model):
    # For personal notes
    note = models.ForeignKey(Note, ...)
    
    # For shared notes
    shared_note = models.ForeignKey(SharedNote, ...)
    
    element_type = models.CharField(
        max_length=20,
        choices=[('textbox', 'Text Box'), ('image', 'Image')]
    )
    
    # Position and size
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    width = models.IntegerField(default=200)
    height = models.IntegerField(default=100)
    
    # Content
    text_content = models.TextField(blank=True)  # For textboxes
    image = models.ImageField(upload_to='canvas_images/', ...)  # For images
    
    # Layering
    z_index = models.IntegerField(default=0)
```

#### API Endpoints
- `POST /canvas/elements/create/` - Create a new canvas element
- `POST /canvas/elements/<id>/update/` - Update element position/size/content
- `POST /canvas/elements/<id>/delete/` - Delete an element
- `POST /canvas/elements/upload-image/` - Upload an image element

#### Views
Modified views to:
- Accept `note_type` parameter in note creation
- Prevent encryption of canvas notes
- Serialize canvas elements as JSON for the frontend
- Handle both personal and shared notes

### Frontend (JavaScript + HTML/CSS)

#### Files
- `static/js/canvas-editor.js` - Main canvas editor component
- `static/css/canvas-editor.css` - Styling for canvas elements
- `notes/templates/notes/canvas_editor_partial.html` - Reusable template

#### CanvasEditor Class
The main JavaScript component that handles:
- Element rendering and DOM manipulation
- Drag and drop interactions
- Resize functionality
- API communication for CRUD operations
- Grid display and snapping
- Touch event handling for mobile

#### Template Integration
```django
{% if note.note_type == 'canvas' %}
    {% with note_id=note.pk elements_json=... %}
        {% include "notes/canvas_editor_partial.html" %}
    {% endwith %}
{% else %}
    <!-- Markdown rendering -->
{% endif %}
```

## User Workflow

### Creating a Canvas Note

1. Click "Create New Note"
2. Select "Canvas Note" type
3. Enter a title
4. Click "Create Note"
5. You'll be redirected to the canvas editor

### Adding Elements

1. **Add Text Box**: Click "📝 Add Text" button
   - A new text box appears at position (50, 50)
   - Click inside to edit text
   - Drag by clicking outside the text area

2. **Add Image**: Click "🖼️ Add Image" button
   - File picker opens
   - Select an image file
   - Image appears on canvas and can be moved/resized

### Editing Elements

1. **Move**: Click and drag element
2. **Resize**: Click element to select, then drag corner handles
3. **Edit Text**: Click inside text box and type
4. **Delete**: Select element, then click "🗑️ Delete" button

### Grid Toggle

- Click "⊞ Show/Hide Grid" to toggle grid display
- When grid is visible, elements snap to grid points during drag/resize

## Testing

### Test Coverage
The implementation includes comprehensive tests:

```python
# notes/tests.py

class CanvasNotesTestCase(TestCase):
    - test_canvas_note_creation
    - test_canvas_element_creation
    - test_canvas_element_update
    - test_canvas_element_delete
    - test_canvas_note_cannot_be_encrypted
    - test_shared_canvas_note_creation
```

Run tests with:
```bash
python manage.py test notes.tests.CanvasNotesTestCase
```

All 38 tests pass (32 existing + 6 new canvas tests).

## Database Migrations

Migration file: `notes/migrations/0006_note_note_type_sharednote_note_type_canvaselement.py`

Run migrations:
```bash
python manage.py migrate
```

## Dependencies Added

Added to `requirements.txt`:
- `Pillow>=10.0.0` - For image handling

Install with:
```bash
pip install -r requirements.txt
```

## Code Reuse

The implementation follows DRY principles:

1. **Shared Template**: `canvas_editor_partial.html` used in both:
   - Personal notes (`note_view.html`)
   - Shared notes (`shared_note_view.html`)

2. **Shared JavaScript**: `CanvasEditor` class works with both note types by accepting either `noteId` or `sharedNoteId`

3. **Shared CSS**: Single stylesheet for all canvas functionality

4. **Backend Logic**: Similar handling for Note and SharedNote models

## Future Enhancements

Potential improvements (not implemented):

1. Element z-index reordering UI (bring to front/send to back)
2. Multiple element selection
3. Copy/paste elements
4. Undo/redo functionality
5. Export canvas as image
6. Real-time collaboration for shared canvas notes
7. More element types (shapes, lines, etc.)
8. Color customization for text boxes
9. Font size options for text

## Known Limitations

1. Canvas notes cannot be encrypted (by design)
2. No version history for canvas notes (elements are auto-saved)
3. Images are permanently deleted when elements are removed
4. No bulk operations (select all, delete all, etc.)
5. Grid size is fixed at 20px (could be made configurable)

## Security Considerations

1. **No Encryption**: Canvas notes are stored in plain text
2. **Access Control**: Enforced at backend - users can only access their own notes
3. **File Upload**: Image uploads are validated and stored securely
4. **CSRF Protection**: All API endpoints require CSRF token
5. **Error Handling**: Generic error messages prevent information leakage
6. **Input Validation**: All user inputs are validated on both client and server

## Conclusion

The canvas notes feature is fully implemented and tested, providing a flexible alternative to markdown notes for users who need freeform content organization. The implementation maintains code quality, security, and user experience standards while adding powerful new functionality to the personal notebook application.
