(function () {
    'use strict';

    var tripType = document.getElementById('id_trip_type');
    var endDatetime = document.getElementById('id_end_datetime');
    var endDateField = document.getElementById('end-date-field');

    if (!tripType || !endDatetime || !endDateField) {
        return;
    }

    function toggleEndDate() {
        var isCar = tripType.value === 'car';
        endDateField.classList.toggle('d-none', isCar);
        endDatetime.required = !isCar;
        if (isCar) {
            endDatetime.value = '';
        }
    }

    tripType.addEventListener('change', toggleEndDate);
    toggleEndDate();
})();
