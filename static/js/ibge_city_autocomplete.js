(function () {
    'use strict';

    var IBGE_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados/';
    var CITY_HINT = 'Selecione o estado primeiro';

    function fillCities(dataList, cities) {
        dataList.innerHTML = '';
        cities.forEach(function (city) {
            var option = document.createElement('option');
            option.value = city.nome;
            dataList.appendChild(option);
        });
    }

    function lockCity(cityInput, dataList) {
        dataList.innerHTML = '';
        cityInput.value = '';
        cityInput.disabled = true;
        cityInput.placeholder = CITY_HINT;
    }

    function unlockCity(cityInput) {
        if (cityInput.disabled) {
            cityInput.disabled = false;
        }
        if (cityInput.placeholder === CITY_HINT) {
            cityInput.placeholder =
                cityInput.getAttribute('data-original-placeholder') || '';
        }
    }

    function fetchCities(uf, dataList) {
        fetch(IBGE_URL + uf + '/municipios')
            .then(function (response) {
                return response.json();
            })
            .then(function (cities) {
                fillCities(dataList, cities);
            })
            .catch(function () {
                fillCities(dataList, []);
            });
    }

    function bindPair(cityInput) {
        var scope = cityInput.closest('[data-ibge-pair]') || document;
        var ufSelect = scope.querySelector('[data-ibge-uf]');
        var dataList = document.getElementById(cityInput.getAttribute('list'));

        if (!ufSelect || !dataList) {
            return;
        }

        if (!cityInput.hasAttribute('data-original-placeholder')) {
            cityInput.setAttribute(
                'data-original-placeholder',
                cityInput.placeholder || ''
            );
        }

        if (!ufSelect.value) {
            lockCity(cityInput, dataList);
        } else {
            unlockCity(cityInput);
        }

        ufSelect.addEventListener('change', function () {
            var uf = ufSelect.value;
            if (!uf) {
                lockCity(cityInput, dataList);
                return;
            }
            cityInput.value = '';
            dataList.innerHTML = '';
            unlockCity(cityInput);
            fetchCities(uf, dataList);
        });
    }

    document.querySelectorAll('[data-ibge-city]').forEach(bindPair);
})();
