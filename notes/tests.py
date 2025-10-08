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
