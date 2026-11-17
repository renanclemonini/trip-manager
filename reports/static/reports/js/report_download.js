(function () {
    'use strict';

    var form = document.getElementById('report-form');
    if (!form || !window.fetch) {
        return;
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var button = form.querySelector('button[type="submit"]');
        if (button) {
            button.disabled = true;
        }
        var filename =
            form.getAttribute('data-filename') || 'relatorio.pdf';
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Falha ao gerar o relatório.');
                }
                return response.blob();
            })
            .then(function (blob) {
                var link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);
            })
            .catch(function () {
                form.submit();
            })
            .finally(function () {
                if (button) {
                    button.disabled = false;
                }
            });
    });
})();
