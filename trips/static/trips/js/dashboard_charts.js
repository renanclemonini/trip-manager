(function () {
    'use strict';

    var dataElement = document.getElementById('dashboard-chart-data');
    if (!dataElement || !window.ApexCharts) {
        return;
    }
    if (!window.matchMedia('(min-width: 992px)').matches) {
        return;
    }

    var data = JSON.parse(dataElement.textContent);

    var categoryElement = document.getElementById('categoryChart');
    if (categoryElement) {
        new ApexCharts(categoryElement, {
            chart: { type: 'donut', height: 320 },
            labels: data.categories.labels,
            series: data.categories.series,
            legend: { position: 'bottom' },
        }).render();
    }

    var consumptionElement = document.getElementById('consumptionChart');
    if (consumptionElement && data.consumption) {
        new ApexCharts(consumptionElement, {
            chart: { type: 'line', height: 320 },
            labels: data.consumption.labels,
            series: [
                { name: 'km/l', data: data.consumption.series },
            ],
            stroke: { curve: 'smooth' },
            xaxis: { categories: data.consumption.labels },
        }).render();
    }
})();
