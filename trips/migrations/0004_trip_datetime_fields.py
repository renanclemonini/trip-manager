from django.db import migrations, models

# 'America/Sao_Paulo' is written as a literal on purpose: the legacy
# DateField values were calendar days in the author's local time zone, and
# that meaning must not change if settings.TIME_ZONE changes later.
#
# The ALTER COLUMN cast produced by AlterField runs with the connection time
# zone set to UTC (USE_TZ), so each legacy date becomes midnight UTC, which
# renders as 21:00 of the previous day in America/Sao_Paulo. The UPDATE below
# shifts the stored value back to midnight in the local time zone, preserving
# the original day (00:00 local) for both start and end.
#
# Reverse note: the shift back (reverse_sql) restores midnight UTC, so a
# rollback keeps the local calendar day but loses the time of day for values
# entered after this migration.
LOCAL_TZ = 'America/Sao_Paulo'

FORWARD_SQL = [
    (
        f"UPDATE trips_trip SET start_datetime = "
        f"start_datetime AT TIME ZONE 'UTC' AT TIME ZONE '{LOCAL_TZ}';"
    ),
    (
        f"UPDATE trips_trip SET end_datetime = "
        f"end_datetime AT TIME ZONE 'UTC' AT TIME ZONE '{LOCAL_TZ}' "
        "WHERE end_datetime IS NOT NULL;"
    ),
]

REVERSE_SQL = [
    (
        f"UPDATE trips_trip SET start_datetime = "
        f"start_datetime AT TIME ZONE '{LOCAL_TZ}' AT TIME ZONE 'UTC';"
    ),
    (
        f"UPDATE trips_trip SET end_datetime = "
        f"end_datetime AT TIME ZONE '{LOCAL_TZ}' AT TIME ZONE 'UTC' "
        "WHERE end_datetime IS NOT NULL;"
    ),
]


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0003_trip_created_by'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='trip',
            options={
                'ordering': ['-start_datetime', '-id'],
                'verbose_name': 'Viagem',
                'verbose_name_plural': 'Viagens',
            },
        ),
        migrations.RenameField(
            model_name='trip',
            old_name='start_date',
            new_name='start_datetime',
        ),
        migrations.RenameField(
            model_name='trip',
            old_name='end_date',
            new_name='end_datetime',
        ),
        migrations.AlterField(
            model_name='trip',
            name='start_datetime',
            field=models.DateTimeField(verbose_name='Data e hora de início'),
        ),
        migrations.AlterField(
            model_name='trip',
            name='end_datetime',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Data e hora de fim'
            ),
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
