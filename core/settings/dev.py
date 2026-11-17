import os

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'trip_manager'),
        'USER': os.environ.get('POSTGRES_USER', 'trip_manager'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'trip_manager'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    },
}
