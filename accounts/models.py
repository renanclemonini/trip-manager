from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager
from common.models import TimestampedModel


class User(AbstractUser, TimestampedModel):
    """Custom user with e-mail login instead of username (RF19)."""

    username = None
    email = models.EmailField('E-mail', unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return self.email
