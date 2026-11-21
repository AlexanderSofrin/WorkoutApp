const CACHE_NAME = 'workout-vault-v22';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.map((k) => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    // API-запросы (тренировки, аналитика, тренер) всегда берём только с сервера, без кэша SW
    if (
        event.request.method !== 'GET' ||
        url.pathname.startsWith('/workouts') ||
        url.pathname.startsWith('/coach') ||
        url.pathname.startsWith('/nutrition') ||
        url.pathname.startsWith('/exercises') ||
        url.pathname.startsWith('/auth')
    ) {
        return;
    }

    event.respondWith(
        fetch(event.request, { cache: 'no-store' })
            .then((response) => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
