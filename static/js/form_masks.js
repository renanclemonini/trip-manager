(function () {
    'use strict';

    function onlyDigits(value) {
        return value.replace(/\D/g, '');
    }

    function stripLeadingZeros(digits) {
        return digits.replace(/^0+(?=\d)/, '');
    }

    function formatThousands(digits) {
        return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function formatCurrency(digits) {
        digits = stripLeadingZeros(digits);
        if (!digits) {
            return '';
        }
        var padded = digits.padStart(3, '0');
        var cents = padded.slice(-2);
        var integer = formatThousands(padded.slice(0, -2));
        return 'R$ ' + integer + ',' + cents;
    }

    function formatDecimal(value) {
        var digits = stripLeadingZeros(onlyDigits(value));
        if (!digits) {
            return '';
        }
        var padded = digits.padStart(3, '0');
        var cents = padded.slice(-2);
        var integer = formatThousands(padded.slice(0, -2));
        return integer + ',' + cents;
    }

    function formatInteger(value) {
        var digits = stripLeadingZeros(onlyDigits(value));
        return digits ? formatThousands(digits) : '';
    }

    function canonicalValue(input) {
        var mask = input.getAttribute('data-mask');
        var value = input.value;
        if (mask === 'currency') {
            var digits = stripLeadingZeros(onlyDigits(value));
            if (!digits) {
                return '';
            }
            var padded = digits.padStart(3, '0');
            return padded.slice(0, -2) + '.' + padded.slice(-2);
        }
        if (mask === 'decimal') {
            var decimal = value.replace(/[^0-9.,]/g, '');
            if (decimal.indexOf(',') === -1) {
                return decimal;
            }
            return decimal.replace(/\./g, '').replace(',', '.');
        }
        if (mask === 'integer') {
            return stripLeadingZeros(onlyDigits(value));
        }
        return value;
    }

    function formatInitialValue(input) {
        var mask = input.getAttribute('data-mask');
        if (!input.value) {
            return;
        }
        if (mask === 'currency') {
            input.value = formatCurrency(onlyDigits(input.value));
        } else if (mask === 'decimal') {
            input.value = formatDecimal(input.value);
        } else if (mask === 'integer') {
            input.value = formatInteger(input.value);
        }
    }

    function applyInputMask(input) {
        var mask = input.getAttribute('data-mask');
        if (mask === 'currency') {
            input.value = formatCurrency(onlyDigits(input.value));
        } else if (mask === 'decimal') {
            input.value = formatDecimal(input.value);
        } else if (mask === 'integer') {
            input.value = formatInteger(input.value);
        }
    }

    function applyBlurMask(input) {
        var mask = input.getAttribute('data-mask');
        if (mask === 'decimal' && input.value) {
            input.value = formatDecimal(input.value);
        } else if (mask === 'currency' && input.value) {
            input.value = formatCurrency(onlyDigits(input.value));
        }
    }

    function nowValue() {
        var now = new Date();
        function pad(number) {
            return (number < 10 ? '0' : '') + number;
        }
        return (
            now.getFullYear() +
            '-' +
            pad(now.getMonth() + 1) +
            '-' +
            pad(now.getDate()) +
            'T' +
            pad(now.getHours()) +
            ':' +
            pad(now.getMinutes())
        );
    }

    function attachNowButton(input) {
        if (input.getAttribute('data-now-ready') === 'true') {
            return;
        }
        input.setAttribute('data-now-ready', 'true');
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-light';
        button.textContent = 'Agora';
        button.addEventListener('click', function () {
            input.value = nowValue();
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        var group = input.closest('.input-group');
        if (!group) {
            group = document.createElement('div');
            group.className = 'input-group';
            input.parentNode.insertBefore(group, input);
            group.appendChild(input);
        }
        group.appendChild(button);
    }

    function onSubmitCapture(event) {
        var form = event.target;
        if (!form || !form.querySelectorAll) {
            return;
        }
        form.querySelectorAll('[data-mask]').forEach(function (input) {
            input.value = canonicalValue(input);
        });
    }

    function init() {
        document.querySelectorAll('[data-mask]').forEach(function (input) {
            formatInitialValue(input);
            input.addEventListener('input', function () {
                applyInputMask(input);
            });
            input.addEventListener('blur', function () {
                applyBlurMask(input);
            });
        });
        document.querySelectorAll('[data-now]').forEach(attachNowButton);
        document.addEventListener('submit', onSubmitCapture, true);
    }

    document.addEventListener('DOMContentLoaded', init);

    window.FormMasks = {
        formatCurrency: formatCurrency,
        formatDecimal: formatDecimal,
        formatInteger: formatInteger,
        canonicalValue: canonicalValue,
        nowValue: nowValue,
    };
})();
