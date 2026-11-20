from datetime import date, datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TripDateTimeFieldsMigrationTests(TransactionTestCase):
    """RF31: 0004 converts DateField to DateTimeField preserving the local day.

    The RunSQL must keep the calendar day in America/Sao_Paulo (midnight
    local time), and the reverse must restore the original dates.
    """

    def test_forward_preserves_local_day_and_reverse_restores_dates(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('trips', '0003_trip_created_by')])
        old_apps = executor.loader.project_state(
            [('trips', '0003_trip_created_by')]
        ).apps
        Trip = old_apps.get_model('trips', 'Trip')
        Trip.objects.using(connection.alias).create(
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type='car',
            start_date=date(2026, 10, 1),
            end_date=None,
        )
        Trip.objects.using(connection.alias).create(
            origin_city='Campinas',
            origin_state='SP',
            destination_city='Santos',
            destination_state='SP',
            trip_type='bus',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 10, 15),
        )

        try:
            executor = MigrationExecutor(connection)
            executor.migrate([('trips', '0004_trip_datetime_fields')])
            new_apps = executor.loader.project_state(
                [('trips', '0004_trip_datetime_fields')]
            ).apps
            Trip = new_apps.get_model('trips', 'Trip')
            car_trip = Trip.objects.using(connection.alias).get(
                origin_city='São Paulo'
            )
            self.assertEqual(
                car_trip.start_datetime,
                timezone.make_aware(datetime(2026, 10, 1)),
            )
            self.assertIsNone(car_trip.end_datetime)
            bus_trip = Trip.objects.using(connection.alias).get(
                origin_city='Campinas'
            )
            self.assertEqual(
                bus_trip.start_datetime,
                timezone.make_aware(datetime(2026, 9, 1)),
            )
            self.assertEqual(
                bus_trip.end_datetime,
                timezone.make_aware(datetime(2026, 10, 15)),
            )

            executor = MigrationExecutor(connection)
            executor.migrate([('trips', '0003_trip_created_by')])
            old_apps = executor.loader.project_state(
                [('trips', '0003_trip_created_by')]
            ).apps
            Trip = old_apps.get_model('trips', 'Trip')
            car_trip = Trip.objects.using(connection.alias).get(
                origin_city='São Paulo'
            )
            self.assertEqual(car_trip.start_date, date(2026, 10, 1))
            self.assertIsNone(car_trip.end_date)
            bus_trip = Trip.objects.using(connection.alias).get(
                origin_city='Campinas'
            )
            self.assertEqual(bus_trip.start_date, date(2026, 9, 1))
            self.assertEqual(bus_trip.end_date, date(2026, 10, 15))
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([('trips', '0004_trip_datetime_fields')])
