/* FitTrack Pro service worker */
var VERSION = '{{ version }}';
var STATIC_CACHE = 'fittrack-static-' + VERSION;
var CDN_CACHE = 'fittrack-cdn-' + VERSION;
var OFFLINE_URL = '{{ offline_url }}';
var PRECACHE = [OFFLINE_URL{% for url in precache %}, '{{ url }}'{% endfor %}];
var CDN_HOSTS = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];

// Install: store the offline page, styles, scripts and icon
self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function (cache) {
      return Promise.all(PRECACHE.map(function (url) {
        return cache.add(url).catch(function () { /* skip a file that cannot be fetched */ });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

// Activate: remove caches from older versions
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys
        .filter(function (key) { return key.indexOf('fittrack-') === 0 && key !== STATIC_CACHE && key !== CDN_CACHE; })
        .map(function (key) { return caches.delete(key); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function staleWhileRevalidate(request, cacheName) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(request).then(function (cached) {
      var network = fetch(request).then(function (response) {
        if (response && response.ok) { cache.put(request, response.clone()); }
        return response;
      }).catch(function () { return cached; });
      return cached || network;
    });
  });
}

function cacheFirst(request, cacheName) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(request).then(function (cached) {
      if (cached) { return cached; }
      return fetch(request).then(function (response) {
        if (response && (response.ok || response.type === 'opaque')) { cache.put(request, response.clone()); }
        return response;
      });
    });
  });
}

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') { return; }               // never touch form posts
  var url = new URL(request.url);

  // 1. Pages: always ask the server. Only if the network fails, show the offline page.
  //    Pages are never stored, so private data (dashboards, payments...) is not kept on the device.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(function () { return caches.match(OFFLINE_URL); }));
    return;
  }

  // 2. Our own CSS, JS and images: from the cache, refreshed in the background
  if (url.origin === self.location.origin && url.pathname.indexOf('/static/') === 0) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  // 3. Libraries and fonts from CDNs: cache first
  if (CDN_HOSTS.indexOf(url.hostname) !== -1) {
    event.respondWith(cacheFirst(request, CDN_CACHE));
  }
  // Anything else (data, PDFs, the admin panel) goes straight to the network.
});