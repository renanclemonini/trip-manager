from trips.services import get_trip_dashboard
from vehicles.services import get_transport_details


def get_final_report_context(trip):
    """Compose the final report context (itemized lists + dashboard)."""
    return {
        'trip': trip,
        'dashboard': get_trip_dashboard(trip),
        'transport': get_transport_details(trip),
        'refuelings': trip.refuelings.order_by('total_mileage'),
        'lodgings': trip.lodgings.order_by('check_in'),
        'meals': trip.meals.order_by('datetime'),
        'sightseeings': trip.sightseeings.order_by('created_at'),
    }
