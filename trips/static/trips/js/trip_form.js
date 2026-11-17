(function () {
    'use strict';

    var tripType = document.getElementById('id_trip_type');
    var endDate = document.getElementById('id_end_date');
    var endDateField = document.getElementById('end-date-field');

    if (!tripType || !endDate || !endDateField) {
        return;
    }

    function toggleEndDate() {
        var isCar = tripType.value === 'car';
        endDateField.classList.toggle('d-none', isCar);
        endDate.required = !isCar;
        if (isCar) {
            endDate.value = '';
        }
    }

    tripType.addEventListener('change', toggleEndDate);
    toggleEndDate();
})();
