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
    var charts = [];

    var THEME_COLORS = {
        light: { foreColor: '#373d3f', gridColor: '#e0e0e0' },
        dark: { foreColor: '#A0ACBB', gridColor: '#1b2436' },
    };

    function currentTheme() {
        return document.documentElement.classList.contains('app-skin-dark') ? 'dark' : 'light';
    }

    function themeOptions(theme) {
        var colors = THEME_COLORS[theme];
        return {
            chart: { foreColor: colors.foreColor },
            grid: { borderColor: colors.gridColor },
            legend: { labels: { colors: colors.foreColor } },
            xaxis: { labels: { style: { colors: colors.foreColor } } },
            yaxis: { labels: { style: { colors: colors.foreColor } } },
        };
    }

    function themedConfig(config, theme) {
        var options = themeOptions(theme);
        var merged = Object.assign({}, config, {
            chart: Object.assign({}, config.chart, options.chart),
            grid: Object.assign({}, config.grid, options.grid),
            legend: Object.assign({}, config.legend, options.legend),
            xaxis: Object.assign({}, config.xaxis, options.xaxis),
            yaxis: Object.assign({}, config.yaxis, options.yaxis),
        });
        Object.keys(merged).forEach(function (key) {
            if (merged[key] === undefined) {
                delete merged[key];
            }
        });
        return merged;
    }

    function renderChart(element, config) {
        var chart = new ApexCharts(element, themedConfig(config, currentTheme()));
        charts.push(chart);
        chart.render();
    }

    var categoryConfig = {
        chart: { type: 'donut', height: 320 },
        labels: data.categories.labels,
        series: data.categories.series,
        legend: { position: 'bottom' },
    };

    var categoryElement = document.getElementById('categoryChart');
    if (categoryElement) {
        renderChart(categoryElement, categoryConfig);
    }

    var consumptionConfig = {
        chart: { type: 'line', height: 320 },
        labels: data.consumption.labels,
        series: [
            { name: 'km/l', data: data.consumption.series },
        ],
        stroke: { curve: 'smooth' },
        xaxis: { categories: data.consumption.labels },
    };

    var consumptionElement = document.getElementById('consumptionChart');
    if (consumptionElement && data.consumption) {
        renderChart(consumptionElement, consumptionConfig);
    }

    document.addEventListener('app-skin-changed', function (event) {
        var theme = event.detail.theme;
        charts.forEach(function (chart) {
            chart.updateOptions(themeOptions(theme), true, true);
        });
    });
})();
