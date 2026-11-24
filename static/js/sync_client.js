(function () {
    'use strict';

    var BASE_DELAY_MS = 15000;
    var MAX_DELAY_MS = 300000;
    var POLL_INTERVAL_MS = 30000;
    var REFRESH_KEY = 'trip-sync-refresh';

    var TYPE_LABELS = {
        refueling: 'Abastecimento',
        lodging: 'Hospedagem',
        meal: 'Alimentação',
        sightseeing: 'Passeio',
        toll: 'Pedágio',
    };

    function nextDelay(attempts) {
        if (!attempts || attempts < 1) {
            return 0;
        }
        var delay = BASE_DELAY_MS * Math.pow(2, attempts - 1);
        return Math.min(delay, MAX_DELAY_MS);
    }

    function getCookie(name) {
        var match = document.cookie.split('; ').find(function (item) {
            return item.indexOf(name + '=') === 0;
        });
        return match ? match.split('=')[1] : '';
    }

    function isMobile() {
        return window.matchMedia('(max-width: 991px)').matches;
    }

    function getPanel() {
        return document.getElementById('offline-sync-panel');
    }

    function getRefreshIntent() {
        try {
            return JSON.parse(window.sessionStorage.getItem(REFRESH_KEY)) || [];
        } catch (error) {
            return [];
        }
    }

    function addRefreshIntent(id) {
        var intent = getRefreshIntent();
        if (intent.indexOf(id) === -1) {
            intent.push(id);
            try {
                window.sessionStorage.setItem(REFRESH_KEY, JSON.stringify(intent));
            } catch (error) {
                return;
            }
        }
    }

    function clearRefreshIntent() {
        try {
            window.sessionStorage.removeItem(REFRESH_KEY);
        } catch (error) {
            return;
        }
    }

    function maybeReloadFromUserAction(syncedIds) {
        var intent = getRefreshIntent();
        if (!intent.length) {
            return;
        }
        clearRefreshIntent();
        var synced = intent.some(function (id) {
            return syncedIds.indexOf(id) !== -1;
        });
        if (synced) {
            window.location.reload();
        }
    }

    function describeEntry(entry) {
        var payload = entry.payload || {};
        var parts = [];
        if (payload.city) {
            parts.push(
                payload.state ? payload.city + '/' + payload.state : payload.city
            );
        }
        if (entry.type === 'refueling' && payload.total_mileage) {
            parts.push(payload.total_mileage + ' km');
        }
        if (entry.type === 'sightseeing' && payload.description) {
            parts.push(payload.description);
        }
        if (entry.type === 'toll' && payload.location) {
            parts.push(payload.location);
        }
        if (payload.amount_spent) {
            parts.push('R$ ' + payload.amount_spent);
        }
        return parts.join(' · ');
    }

    function extractError(data) {
        if (!data || !data.errors) {
            return 'Falha na validação.';
        }
        var messages = [];
        Object.keys(data.errors).forEach(function (field) {
            data.errors[field].forEach(function (error) {
                messages.push(error.message || String(error));
            });
        });
        return messages.join(' ');
    }

    function postEntry(entry) {
        return fetch(entry.syncUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(entry.payload),
        }).then(function (response) {
            if (response.ok) {
                return { synced: true };
            }
            if (response.status === 400) {
                return response.json().then(function (data) {
                    return {
                        synced: false,
                        permanent: true,
                        error: extractError(data),
                    };
                });
            }
            return { synced: false, permanent: false };
        }).catch(function () {
            return { synced: false, permanent: false };
        });
    }

    function syncEntry(entry) {
        entry.status = 'syncing';
        return postEntry(entry).then(function (result) {
            if (result.synced) {
                return window.TripOfflineDb.deleteEntry(entry.id).then(
                    function () {
                        return { synced: true };
                    }
                );
            }
            entry.attempts = (entry.attempts || 0) + 1;
            entry.nextAttemptAt = Date.now() + nextDelay(entry.attempts);
            entry.status = 'pending';
            entry.error = null;
            if (result.permanent) {
                entry.status = 'error';
                entry.error = result.error;
                entry.nextAttemptAt = null;
            }
            return window.TripOfflineDb.saveEntry(entry).then(function () {
                return { synced: false };
            });
        });
    }

    function entriesDue(entries, now) {
        return entries.filter(function (entry) {
            if (entry.status === 'error') {
                return false;
            }
            return !entry.nextAttemptAt || entry.nextAttemptAt <= now;
        });
    }

    function syncAll(force) {
        var syncedIds = [];
        return window.TripOfflineDb.getEntries()
            .then(function (entries) {
                var now = Date.now();
                var due = force
                    ? entries.filter(function (entry) {
                        return entry.status !== 'error';
                    })
                    : entriesDue(entries, now);
                return due.reduce(function (chain, entry) {
                    return chain.then(function () {
                        return syncEntry(entry).then(function (result) {
                            if (result.synced) {
                                syncedIds.push(entry.id);
                            }
                        });
                    });
                }, Promise.resolve());
            })
            .then(renderPending)
            .then(function () {
                return syncedIds;
            });
    }

    function renderEntry(entry) {
        var card = document.createElement('div');
        card.className = 'card mb-2';
        card.setAttribute('data-offline-entry', entry.id);
        var body = document.createElement('div');
        body.className =
            'card-body d-flex align-items-center justify-content-between';
        var info = document.createElement('div');
        var title = document.createElement('p');
        title.className = 'fw-semibold mb-1';
        title.textContent = TYPE_LABELS[entry.type] || entry.type;
        var details = document.createElement('p');
        details.className = 'text-muted mb-0 fs-12';
        details.textContent = describeEntry(entry);
        info.appendChild(title);
        info.appendChild(details);
        if (entry.status === 'error') {
            var errorText = document.createElement('p');
            errorText.className = 'text-danger fs-12 mb-1';
            errorText.textContent = entry.error || 'Erro na sincronização.';
            info.appendChild(errorText);
            var discard = document.createElement('button');
            discard.type = 'button';
            discard.className = 'btn btn-light btn-sm';
            discard.textContent = 'Descartar';
            discard.setAttribute('data-offline-discard', entry.id);
            body.appendChild(info);
            body.appendChild(discard);
        } else {
            var badge = document.createElement('span');
            badge.className = 'badge bg-soft-info text-info';
            badge.textContent = 'Pendente';
            body.appendChild(info);
            body.appendChild(badge);
        }
        card.appendChild(body);
        return card;
    }

    function renderPending() {
        var panel = getPanel();
        if (!panel) {
            return;
        }
        var tripId = parseInt(panel.dataset.syncTrip, 10);
        return window.TripOfflineDb.getEntries().then(function (entries) {
            var relevant = entries.filter(function (entry) {
                return !tripId || entry.trip === tripId;
            });
            var count = document.getElementById('offline-sync-count');
            if (count) {
                count.textContent =
                    relevant.length === 1
                        ? '1 lançamento pendente'
                        : relevant.length + ' lançamentos pendentes';
            }
            var list = document.getElementById('offline-sync-list');
            if (!list) {
                return;
            }
            list.innerHTML = '';
            relevant.forEach(function (entry) {
                list.appendChild(renderEntry(entry));
            });
        });
    }

    function buildEntry(form) {
        var payload = {};
        Array.prototype.forEach.call(form.elements, function (element) {
            if (element.name) {
                payload[element.name] = element.value;
            }
        });
        payload.id = crypto.randomUUID();
        payload.trip = parseInt(form.dataset.syncTrip, 10);
        return {
            id: payload.id,
            type: form.dataset.syncForm,
            trip: payload.trip,
            syncUrl: form.dataset.syncUrl,
            payload: payload,
            synced: false,
            status: 'pending',
            attempts: 0,
            nextAttemptAt: Date.now(),
            error: null,
            createdAt: new Date().toISOString(),
        };
    }

    function interceptSubmit(event) {
        var form = event.target;
        if (!form.dataset || !form.dataset.syncForm || !isMobile()) {
            return;
        }
        event.preventDefault();
        var entry = buildEntry(form);
        window.TripOfflineDb.saveEntry(entry).then(function () {
            if (navigator.onLine === false) {
                closeModal(form);
                form.reset();
                renderPending();
                return;
            }
            addRefreshIntent(entry.id);
            window.location.href = form.dataset.syncListUrl;
        });
    }

    function closeModal(form) {
        var modalElement = form.closest('.modal');
        if (!modalElement || !window.bootstrap) {
            return;
        }
        window.bootstrap.Modal.getOrCreateInstance(modalElement).hide();
    }

    function boot() {
        document.addEventListener('submit', interceptSubmit);
        var panel = getPanel();
        if (!panel) {
            return;
        }
        renderPending();
        syncAll().then(maybeReloadFromUserAction);
        window.addEventListener('online', function () {
            syncAll();
        });
        window.setInterval(function () {
            syncAll();
        }, POLL_INTERVAL_MS);
        var button = document.getElementById('offline-sync-now');
        if (button) {
            button.addEventListener('click', function () {
                clearRefreshIntent();
                syncAll(true).then(function () {
                    window.location.reload();
                });
            });
        }
        panel.addEventListener('click', function (event) {
            var id =
                event.target.getAttribute &&
                event.target.getAttribute('data-offline-discard');
            if (!id) {
                return;
            }
            window.TripOfflineDb.deleteEntry(id).then(renderPending);
        });
    }

    document.addEventListener('DOMContentLoaded', boot);

    window.TripSync = {
        nextDelay: nextDelay,
        syncAll: syncAll,
        renderPending: renderPending,
    };
})();
