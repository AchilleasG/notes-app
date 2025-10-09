"""Test settings configuration using SQLite."""
import os
import sys

# Set environment variables before importing settings
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ.setdefault('DB_NAME', 'test')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_HOST', 'localhost')

from .settings import *

# Override database to use SQLite for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable security features for testing
SECRET_KEY = 'test-secret-key-for-testing'
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
