(function () {
    'use strict';

    var DB_NAME = 'trip-manager-offline';
    var DB_VERSION = 1;
    var STORE_NAME = 'pending_entries';

    function openDatabase() {
        return new Promise(function (resolve, reject) {
            var request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = function () {
                var database = request.result;
                if (!database.objectStoreNames.contains(STORE_NAME)) {
                    var store = database.createObjectStore(
                        STORE_NAME, { keyPath: 'id' }
                    );
                    store.createIndex('trip', 'trip', { unique: false });
                    store.createIndex('type', 'type', { unique: false });
                }
            };
            request.onsuccess = function () {
                resolve(request.result);
            };
            request.onerror = function () {
                reject(request.error);
            };
        });
    }

    function transactionDone(transaction) {
        return new Promise(function (resolve, reject) {
            transaction.oncomplete = function () {
                resolve();
            };
            transaction.onerror = function () {
                reject(transaction.error);
            };
            transaction.onabort = function () {
                reject(transaction.error);
            };
        });
    }

    function saveEntry(entry) {
        return openDatabase().then(function (database) {
            var transaction = database.transaction(STORE_NAME, 'readwrite');
            transaction.objectStore(STORE_NAME).put(entry);
            return transactionDone(transaction).then(function () {
                return entry;
            });
        });
    }

    function getEntries() {
        return openDatabase().then(function (database) {
            var transaction = database.transaction(STORE_NAME, 'readonly');
            var request = transaction.objectStore(STORE_NAME).getAll();
            return new Promise(function (resolve, reject) {
                request.onsuccess = function () {
                    resolve(request.result || []);
                };
                request.onerror = function () {
                    reject(request.error);
                };
            });
        });
    }

    function deleteEntry(id) {
        return openDatabase().then(function (database) {
            var transaction = database.transaction(STORE_NAME, 'readwrite');
            transaction.objectStore(STORE_NAME).delete(id);
            return transactionDone(transaction);
        });
    }

    window.TripOfflineDb = {
        openDatabase: openDatabase,
        saveEntry: saveEntry,
        getEntries: getEntries,
        deleteEntry: deleteEntry,
    };
})();
