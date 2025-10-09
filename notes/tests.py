from django.test import TestCase
from django.contrib.auth.models import User
from .models import Note, NoteVersion


class NoteVersionTestCase(TestCase):
    def setUp(self):
        """Set up test user and note"""
        self.user = User.objects.create_user(username='testuser', password='testpass')
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


class DarkModeTestCase(TestCase):
    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(username='testuser', password='testpass')
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
