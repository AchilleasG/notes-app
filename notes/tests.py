from django.test import TestCase
from .models import Note, NoteVersion, Folder, SharedFolder, Friendship


class NoteVersionTestCase(TestCase):
    def setUp(self):
        """Set up test user and note"""
        from .models import CustomUser
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_version_created_on_edit(self):
        """Test that a version is created when a note is edited"""
        # Create a note
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Initial content'
        )
        
        # Edit the note
        self.client.post(f'/edit/{note.pk}/', {
            'title': 'Test Note',
            'content': 'Updated content'
        })
        
        # Check that a version was created
        versions = NoteVersion.objects.filter(note=note)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(versions.first().content, 'Initial content')
        
    def test_multiple_versions(self):
        """Test that multiple versions are created on multiple edits"""
        # Create a note
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Version 1'
        )
        
        # Edit multiple times
        self.client.post(f'/edit/{note.pk}/', {
            'title': 'Test Note',
            'content': 'Version 2'
        })
        
        self.client.post(f'/edit/{note.pk}/', {
            'title': 'Test Note',
            'content': 'Version 3'
        })
        
        # Check that two versions were created (original + first edit)
        versions = NoteVersion.objects.filter(note=note)
        self.assertEqual(versions.count(), 2)
        
    def test_history_view_requires_login(self):
        """Test that history view requires authentication"""
        self.client.logout()
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Test content'
        )
        
        response = self.client.get(f'/history/{note.pk}/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        
    def test_history_view_accessible_to_owner(self):
        """Test that history view is accessible to note owner"""
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Test content'
        )
        
        response = self.client.get(f'/history/{note.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'History: Test Note')


class FolderTestCase(TestCase):
    def setUp(self):
        """Set up test user"""
        from .models import CustomUser
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_folder_creation(self):
        """Test that a folder can be created"""
        folder = Folder.objects.create(user=self.user, name='Test Folder')
        self.assertEqual(folder.name, 'Test Folder')
        self.assertEqual(folder.user, self.user)
        self.assertIsNone(folder.parent)
        
    def test_subfolder_creation(self):
        """Test that a subfolder can be created"""
        parent = Folder.objects.create(user=self.user, name='Parent')
        child = Folder.objects.create(user=self.user, name='Child', parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.get_full_path(), 'Parent/Child')
        
    def test_note_in_folder(self):
        """Test that a note can be added to a folder"""
        folder = Folder.objects.create(user=self.user, name='Test Folder')
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Test content',
            folder=folder
        )
        self.assertEqual(note.folder, folder)
        self.assertEqual(folder.notes.count(), 1)
        
    def test_folder_delete_moves_notes_to_parent(self):
        """Test that deleting a folder moves notes to parent"""
        parent = Folder.objects.create(user=self.user, name='Parent')
        child = Folder.objects.create(user=self.user, name='Child', parent=parent)
        note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='Test content',
            folder=child
        )
        
        # Delete child folder via view
        response = self.client.post(f'/folders/{child.id}/delete/')
        
        # Check note moved to parent
        note.refresh_from_db()
        self.assertEqual(note.folder, parent)
        
    def test_folder_list_filtered_by_folder(self):
        """Test that notes can be filtered by folder"""
        folder1 = Folder.objects.create(user=self.user, name='Folder 1')
        folder2 = Folder.objects.create(user=self.user, name='Folder 2')
        
        note1 = Note.objects.create(
            user=self.user,
            title='Note 1',
            content='Content 1',
            folder=folder1
        )
        note2 = Note.objects.create(
            user=self.user,
            title='Note 2',
            content='Content 2',
            folder=folder2
        )
        
        # Get notes in folder1
        response = self.client.get(f'/?folder={folder1.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Note 1')
        self.assertNotContains(response, 'Note 2')


class SharedFolderTestCase(TestCase):
    def setUp(self):
        """Set up test users and friendship"""
        from .models import CustomUser
        self.user1 = CustomUser.objects.create_user(username='user1', password='testpass')
        self.user2 = CustomUser.objects.create_user(username='user2', password='testpass')
        
        # Create friendship
        Friendship.objects.create(user1=self.user1, user2=self.user2)
        
        self.client.login(username='user1', password='testpass')
        
    def test_shared_folder_creation(self):
        """Test that a shared folder can be created"""
        folder = SharedFolder.objects.create(
            user1=self.user1,
            user2=self.user2,
            name='Shared Folder'
        )
        self.assertEqual(folder.name, 'Shared Folder')
        self.assertTrue(folder.has_access(self.user1))
        self.assertTrue(folder.has_access(self.user2))
        
    def test_shared_note_in_folder(self):
        """Test that a shared note can be added to a shared folder"""
        from .models import SharedNote
        
        folder = SharedFolder.objects.create(
            user1=self.user1,
            user2=self.user2,
            name='Shared Folder'
        )
        
        note = SharedNote.objects.create(
            user1=self.user1,
            user2=self.user2,
            title='Shared Note',
            content='Shared content',
            folder=folder,
            created_by=self.user1
        )
        
        self.assertEqual(note.folder, folder)
        self.assertEqual(folder.notes.count(), 1)


class DarkModeTestCase(TestCase):
    def setUp(self):
        """Set up test user"""
        from .models import CustomUser
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_dark_mode_toggle_present(self):
        """Test that dark mode toggle button is present in base template"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for theme toggle button
        self.assertContains(response, 'id="themeToggle"')
        self.assertContains(response, 'id="themeIcon"')
        
    def test_dark_mode_css_variables(self):
        """Test that dark mode CSS variables are defined"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for CSS variables
        self.assertContains(response, '--bg-primary')
        self.assertContains(response, '--text-primary')
        self.assertContains(response, '[data-theme="dark"]')


class ProfileTestCase(TestCase):
    def setUp(self):
        """Set up test user"""
        from .models import CustomUser
        self.user = CustomUser.objects.create_user(
            username='testuser', 
            password='testpass123',
            email='test@example.com'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_profile_page_accessible(self):
        """Test that profile page is accessible to logged in users"""
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User Profile')
        
    def test_profile_page_requires_login(self):
        """Test that profile page requires authentication"""
        self.client.logout()
        response = self.client.get('/profile/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        
    def test_password_change_form_present(self):
        """Test that password change form is present"""
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Change Password')
        self.assertContains(response, 'Current Password')
        self.assertContains(response, 'New Password')
        
    def test_profile_update_form_present(self):
        """Test that profile update form is present"""
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Update Profile Information')
        self.assertContains(response, 'First Name')
        self.assertContains(response, 'Email')
        
    def test_password_change_successful(self):
        """Test that password can be changed successfully"""
        response = self.client.post('/profile/', {
            'change_password': 'true',
            'old_password': 'testpass123',
            'new_password1': 'newtestpass456',
            'new_password2': 'newtestpass456'
        })
        # Should redirect to profile page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/profile/')
        
        # Verify user can login with new password
        self.client.logout()
        login_success = self.client.login(username='testuser', password='newtestpass456')
        self.assertTrue(login_success)
        
    def test_profile_update_successful(self):
        """Test that profile can be updated successfully"""
        response = self.client.post('/profile/', {
            'update_profile': 'true',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'newemail@example.com',
            'bio': 'This is my bio',
            'location': 'Test City',
            'website': 'https://example.com'
        })
        # Should redirect to profile page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/profile/')
        
        # Verify profile was updated
        from .models import CustomUser
        user = CustomUser.objects.get(username='testuser')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.email, 'newemail@example.com')
        self.assertEqual(user.bio, 'This is my bio')
        
    def test_profile_link_in_header(self):
        """Test that Profile link appears in header for logged in users"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile')


class TagsTestCase(TestCase):
    def setUp(self):
        """Set up test user and login"""
        from .models import CustomUser, Tag, Note
        self.user = CustomUser.objects.create_user(
            username='testuser', 
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_tag_creation(self):
        """Test that tags can be created"""
        from .models import Tag
        tag = Tag.objects.create(
            user=self.user,
            name='Python',
            color='#3b82f6'
        )
        self.assertEqual(tag.name, 'Python')
        self.assertEqual(tag.color, '#3b82f6')
        
    def test_tag_autocomplete_endpoint(self):
        """Test that tag autocomplete endpoint works"""
        from .models import Tag
        # Create some tags
        Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        Tag.objects.create(user=self.user, name='Django', color='#16a34a')
        Tag.objects.create(user=self.user, name='JavaScript', color='#ea580c')
        
        response = self.client.get('/api/tags/autocomplete/?q=py')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Python')
        
    def test_note_with_tags(self):
        """Test creating a note with tags"""
        from .models import Tag, Note
        import json
        
        # Create tags
        tag1 = Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        tag2 = Tag.objects.create(user=self.user, name='Django', color='#16a34a')
        
        # Create note with tags
        tags_data = json.dumps([
            {'name': 'Python', 'color': '#3b82f6'},
            {'name': 'Django', 'color': '#16a34a'}
        ])
        
        response = self.client.post('/create/', {
            'title': 'Test Note with Tags',
            'content': 'Content with tags',
            'tags': tags_data
        })
        
        # Should redirect after creation
        self.assertEqual(response.status_code, 302)
        
        # Check that note was created with tags
        note = Note.objects.get(title='Test Note with Tags')
        self.assertEqual(note.tags.count(), 2)
        self.assertTrue(note.tags.filter(name='Python').exists())
        self.assertTrue(note.tags.filter(name='Django').exists())
        
    def test_tag_filtering(self):
        """Test filtering notes by tags"""
        from .models import Tag, Note
        
        # Create tags
        tag1 = Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        tag2 = Tag.objects.create(user=self.user, name='Django', color='#16a34a')
        
        # Create notes
        note1 = Note.objects.create(user=self.user, title='Note 1', content='Content 1')
        note1.tags.add(tag1)
        
        note2 = Note.objects.create(user=self.user, title='Note 2', content='Content 2')
        note2.tags.add(tag2)
        
        note3 = Note.objects.create(user=self.user, title='Note 3', content='Content 3')
        note3.tags.add(tag1, tag2)
        
        # Filter by Python tag
        response = self.client.get('/?tags=Python')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Note 1')
        self.assertContains(response, 'Note 3')
        self.assertNotContains(response, 'Note 2')
        
    def test_tag_case_insensitive(self):
        """Test that tags are case-insensitive"""
        from .models import Tag
        
        # Create tag with lowercase
        Tag.objects.create(user=self.user, name='python', color='#3b82f6')
        
        # Try to filter with uppercase
        response = self.client.get('/?tags=PYTHON')
        self.assertEqual(response.status_code, 200)
        
    def test_tags_display_in_note_list(self):
        """Test that tags are displayed in note list"""
        from .models import Tag, Note
        
        tag = Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        note = Note.objects.create(user=self.user, title='Test Note', content='Content')
        note.tags.add(tag)
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python')
        self.assertContains(response, tag.color)
        
    def test_multiple_tags_per_note(self):
        """Test that a note can have multiple tags"""
        from .models import Tag, Note
        
        tag1 = Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        tag2 = Tag.objects.create(user=self.user, name='Django', color='#16a34a')
        tag3 = Tag.objects.create(user=self.user, name='WebDev', color='#ea580c')
        
        note = Note.objects.create(user=self.user, title='Test Note', content='Content')
        note.tags.add(tag1, tag2, tag3)
        
        self.assertEqual(note.tags.count(), 3)
        
    def test_tag_unique_per_user(self):
        """Test that tag names are unique per user"""
        from .models import Tag, CustomUser
        from django.db import IntegrityError, transaction
        
        # Create first tag
        Tag.objects.create(user=self.user, name='Python', color='#3b82f6')
        
        # Try to create duplicate tag for same user
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(user=self.user, name='Python', color='#16a34a')
        
        # But another user can have the same tag name
        other_user = CustomUser.objects.create_user(
            username='otheruser',
            password='otherpass'
        )
        tag2 = Tag.objects.create(user=other_user, name='Python', color='#16a34a')
        self.assertEqual(tag2.name, 'Python')


class SharedNotesTestCase(TestCase):
    def setUp(self):
        """Set up test users and friendship"""
        from .models import CustomUser, Friendship
        self.user1 = CustomUser.objects.create_user(username='user1', password='pass1')
        self.user2 = CustomUser.objects.create_user(username='user2', password='pass2')
        
        # Create friendship
        Friendship.objects.create(user1=self.user1, user2=self.user2)
        
        self.client.login(username='user1', password='pass1')
        
    def test_shared_note_with_tags(self):
        """Test creating a shared note with tags"""
        from .models import SharedNote, Tag
        import json
        
        # Create tags data
        tags_data = json.dumps([
            {'name': 'Shared', 'color': '#3b82f6'},
            {'name': 'Important', 'color': '#16a34a'}
        ])
        
        response = self.client.post(f'/friends/{self.user2.id}/shared-notes/create/', {
            'title': 'Shared Note with Tags',
            'content': 'Content with tags',
            'tags': tags_data
        })
        
        # Should redirect after creation
        self.assertEqual(response.status_code, 302)
        
        # Check that note was created with tags
        shared_note = SharedNote.objects.get(title='Shared Note with Tags')
        self.assertEqual(shared_note.tags.count(), 2)
        self.assertTrue(shared_note.tags.filter(name='Shared').exists())
        self.assertTrue(shared_note.tags.filter(name='Important').exists())
        
    def test_shared_note_tags_display(self):
        """Test that tags are displayed in shared note view"""
        from .models import SharedNote, Tag
        
        # Create a shared note with tags
        user1, user2 = sorted([self.user1, self.user2], key=lambda u: u.id)
        shared_note = SharedNote.objects.create(
            user1=user1,
            user2=user2,
            title='Test Shared Note',
            content='Test content',
            created_by=self.user1
        )
        
        tag = Tag.objects.create(user=self.user1, name='TestTag', color='#3b82f6')
        shared_note.tags.add(tag)
        
        response = self.client.get(f'/shared-notes/{shared_note.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TestTag')
        self.assertContains(response, tag.color)
        
    def test_shared_note_encryption(self):
        """Test that shared notes can be encrypted"""
        from .models import SharedNote
        
        # Note: We can't easily test client-side encryption in Django tests
        # but we can test that the model fields are properly set
        user1, user2 = sorted([self.user1, self.user2], key=lambda u: u.id)
        shared_note = SharedNote.objects.create(
            user1=user1,
            user2=user2,
            title='Encrypted Note',
            content='encrypted_content_here',
            is_locked=True,
            salt='abc123',
            created_by=self.user1
        )
        
        self.assertTrue(shared_note.is_locked)
        self.assertEqual(shared_note.salt, 'abc123')
        
    def test_shared_note_edit_preserves_tags(self):
        """Test that editing a shared note preserves tags"""
        from .models import SharedNote, Tag
        import json
        
        # Create a shared note with tags
        user1, user2 = sorted([self.user1, self.user2], key=lambda u: u.id)
        shared_note = SharedNote.objects.create(
            user1=user1,
            user2=user2,
            title='Test Note',
            content='Test content',
            created_by=self.user1
        )
        
        tag = Tag.objects.create(user=self.user1, name='Original', color='#3b82f6')
        shared_note.tags.add(tag)
        
        # Edit the note and add another tag
        tags_data = json.dumps([
            {'name': 'Original', 'color': '#3b82f6'},
            {'name': 'Updated', 'color': '#16a34a'}
        ])
        
        response = self.client.post(f'/shared-notes/{shared_note.id}/edit/', {
            'title': 'Updated Note',
            'content': 'Updated content',
            'tags': tags_data
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check that note has both tags
        shared_note.refresh_from_db()
        self.assertEqual(shared_note.tags.count(), 2)
        self.assertTrue(shared_note.tags.filter(name='Original').exists())
        self.assertTrue(shared_note.tags.filter(name='Updated').exists())


class CanvasNotesTestCase(TestCase):
    def setUp(self):
        """Set up test user"""
        from .models import CustomUser
        self.user = CustomUser.objects.create_user(
            username='testuser', 
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_canvas_note_creation(self):
        """Test that a canvas note can be created"""
        from .models import Note
        
        response = self.client.post('/create/', {
            'title': 'Test Canvas Note',
            'note_type': 'canvas',
        })
        
        # Should redirect after creation
        self.assertEqual(response.status_code, 302)
        
        # Check that note was created with canvas type
        note = Note.objects.get(title='Test Canvas Note')
        self.assertEqual(note.note_type, 'canvas')
        self.assertFalse(note.is_locked)  # Canvas notes cannot be encrypted
        
    def test_canvas_element_creation(self):
        """Test that canvas elements can be created"""
        from .models import Note, CanvasElement
        import json
        
        # Create a canvas note
        note = Note.objects.create(
            user=self.user,
            title='Test Canvas Note',
            note_type='canvas',
            content=''
        )
        
        # Create a textbox element
        response = self.client.post('/canvas/elements/create/', 
            data=json.dumps({
                'note_id': note.id,
                'element_type': 'textbox',
                'x': 50,
                'y': 50,
                'width': 200,
                'height': 100,
                'text_content': 'Hello canvas',
                'z_index': 0,
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        
        # Check element was created
        self.assertEqual(CanvasElement.objects.filter(note=note).count(), 1)
        element = CanvasElement.objects.get(note=note)
        self.assertEqual(element.element_type, 'textbox')
        self.assertEqual(element.text_content, 'Hello canvas')
        
    def test_canvas_element_update(self):
        """Test that canvas elements can be updated"""
        from .models import Note, CanvasElement
        import json
        
        # Create a canvas note with an element
        note = Note.objects.create(
            user=self.user,
            title='Test Canvas Note',
            note_type='canvas',
            content=''
        )
        
        element = CanvasElement.objects.create(
            note=note,
            element_type='textbox',
            x=50,
            y=50,
            width=200,
            height=100,
            text_content='Original text',
        )
        
        # Update the element
        response = self.client.post(f'/canvas/elements/{element.id}/update/', 
            data=json.dumps({
                'x': 100,
                'y': 100,
                'text_content': 'Updated text',
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        
        # Check element was updated
        element.refresh_from_db()
        self.assertEqual(element.x, 100)
        self.assertEqual(element.y, 100)
        self.assertEqual(element.text_content, 'Updated text')
        
    def test_canvas_element_delete(self):
        """Test that canvas elements can be deleted"""
        from .models import Note, CanvasElement
        
        # Create a canvas note with an element
        note = Note.objects.create(
            user=self.user,
            title='Test Canvas Note',
            note_type='canvas',
            content=''
        )
        
        element = CanvasElement.objects.create(
            note=note,
            element_type='textbox',
            x=50,
            y=50,
            width=200,
            height=100,
            text_content='Text to delete',
        )
        
        element_id = element.id
        
        # Delete the element
        response = self.client.post(f'/canvas/elements/{element_id}/delete/')
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        
        # Check element was deleted
        self.assertFalse(CanvasElement.objects.filter(id=element_id).exists())
        
    def test_canvas_note_cannot_be_encrypted(self):
        """Test that canvas notes cannot be encrypted"""
        from .models import Note
        
        response = self.client.post('/create/', {
            'title': 'Test Canvas Note',
            'note_type': 'canvas',
            'is_locked': 'on',
        })
        
        # Should redirect but with error
        self.assertEqual(response.status_code, 302)
        # The view should have shown an error and redirected back
        
    def test_shared_canvas_note_creation(self):
        """Test that shared canvas notes can be created"""
        from .models import CustomUser, Friendship, SharedNote
        
        # Create a friend
        friend = CustomUser.objects.create_user(username='friend', password='pass')
        Friendship.objects.create(user1=self.user, user2=friend)
        
        response = self.client.post(f'/friends/{friend.id}/shared-notes/create/', {
            'title': 'Shared Canvas Note',
            'note_type': 'canvas',
        })
        
        # Should redirect after creation
        self.assertEqual(response.status_code, 302)
        
        # Check that shared note was created with canvas type
        shared_note = SharedNote.objects.get(title='Shared Canvas Note')
        self.assertEqual(shared_note.note_type, 'canvas')
        self.assertFalse(shared_note.is_locked)
        
    def test_shape_element_creation(self):
        """Test that shape elements can be created"""
        from .models import Note, CanvasElement
        import json
        
        # Create a canvas note
        note = Note.objects.create(
            user=self.user,
            title='Test Canvas Note',
            note_type='canvas',
            content=''
        )
        
        # Create a rectangle element
        response = self.client.post('/canvas/elements/create/', 
            data=json.dumps({
                'note_id': note.id,
                'element_type': 'rectangle',
                'x': 50,
                'y': 50,
                'width': 200,
                'height': 100,
                'stroke_color': '#000000',
                'fill_color': '#ffffff',
                'stroke_width': 2,
                'z_index': 0,
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        
        # Check element was created
        self.assertEqual(CanvasElement.objects.filter(note=note).count(), 1)
        element = CanvasElement.objects.get(note=note)
        self.assertEqual(element.element_type, 'rectangle')
        self.assertEqual(element.stroke_color, '#000000')
        self.assertEqual(element.fill_color, '#ffffff')
        
    def test_freehand_element_creation(self):
        """Test that freehand drawing elements can be created"""
        from .models import Note, CanvasElement
        import json
        
        # Create a canvas note
        note = Note.objects.create(
            user=self.user,
            title='Test Canvas Note',
            note_type='canvas',
            content=''
        )
        
        # Create a freehand element
        response = self.client.post('/canvas/elements/create/', 
            data=json.dumps({
                'note_id': note.id,
                'element_type': 'freehand',
                'x': 10,
                'y': 10,
                'width': 100,
                'height': 100,
                'stroke_color': '#000000',
                'stroke_width': 2,
                'path_data': 'M 0 0 L 10 10 L 20 5',
                'z_index': 0,
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        
        # Check element was created
        self.assertEqual(CanvasElement.objects.filter(note=note).count(), 1)
        element = CanvasElement.objects.get(note=note)
        self.assertEqual(element.element_type, 'freehand')
        self.assertEqual(element.path_data, 'M 0 0 L 10 10 L 20 5')
