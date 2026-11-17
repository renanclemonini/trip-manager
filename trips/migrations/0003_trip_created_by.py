from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0002_trip_city_state_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='trip',
            old_name='user',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='trip',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_trips',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Criado por',
            ),
        ),
    ]
