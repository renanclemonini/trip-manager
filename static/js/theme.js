(function () {
    'use strict';

    var STORAGE_KEY = 'trip-manager-theme';
    var DARK_CLASS = 'app-skin-dark';
    var CHANGE_EVENT = 'app-skin-changed';

    function readStoredTheme() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light';
        } catch (error) {
            return 'light';
        }
    }

    function storeTheme(theme) {
        try {
            window.localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            // Storage unavailable: preference applies to this session only.
        }
    }

    function currentTheme() {
        return document.documentElement.classList.contains(DARK_CLASS) ? 'dark' : 'light';
    }

    function updateToggle(theme) {
        var isDark = theme === 'dark';
        var label = isDark ? 'Ativar tema claro' : 'Ativar tema escuro';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (toggle) {
            toggle.classList.toggle('dark-button', !isDark);
            toggle.classList.toggle('light-button', isDark);
            toggle.setAttribute('aria-label', label);
            toggle.setAttribute('title', label);
            var icon = toggle.querySelector('i');
            if (icon) {
                icon.className = isDark ? 'feather-sun' : 'feather-moon';
            }
        });
    }

    function setTheme(theme) {
        if (theme === currentTheme()) {
            return;
        }
        document.documentElement.classList.toggle(DARK_CLASS, theme === 'dark');
        storeTheme(theme);
        updateToggle(theme);
        document.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { theme: theme } }));
    }

    function init() {
        var theme = currentTheme();
        updateToggle(theme);
        document.querySelectorAll('[data-theme-toggle]').forEach(function (toggle) {
            toggle.addEventListener('click', function () {
                setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
            });
        });
    }

    init();
})();
