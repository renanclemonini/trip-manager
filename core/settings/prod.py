import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

ALLOWED_HOSTS = [
    host for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if host
]

if not os.environ.get('EMAIL_HOST'):
    raise ImproperlyConfigured(
        'Defina EMAIL_HOST (SMTP) no ambiente de produção.'
    )

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin
]

SECURE_SSL_REDIRECT = os.environ.get(
    'DJANGO_SECURE_SSL_REDIRECT', 'true'
).lower() in ('true', '1', 'yes')
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS = int(
    os.environ.get(
        'DJANGO_SECURE_HSTS_SECONDS',
        '31536000' if SECURE_SSL_REDIRECT else '0',
    )
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
if os.environ.get('DJANGO_SECURE_PROXY_SSL', 'true').lower() in (
    'true',
    '1',
    'yes',
):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'common.storage.StaticFilesStorage',
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'trip_manager'),
        'USER': os.environ.get('POSTGRES_USER', 'trip_manager'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', ''),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    },
}
