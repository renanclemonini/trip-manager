from django.db import models


class TimestampedModel(models.Model):
    """Abstract base model with created_at/updated_at for every project model."""

    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        abstract = True
