from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse

# Change this number (v1 -> v2) whenever you edit the service worker or want every device to refresh its cache.
PWA_VERSION = 'v2'


def manifest(request):
    data = {
        'id': '/',
        'name': 'FitTrack Pro',
        'short_name': 'FitTrack',
        'description': 'Fitness club management: memberships, attendance, payments, schedule and progress.',
        'start_url': reverse('dashboard') + '?source=pwa',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#FFF9F3',
        'theme_color': '#7B2FF7',
        'icons': [
            {'src': static('pwa/icons/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icons/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icons/maskable-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
        'shortcuts': [
            {'name': 'Dashboard', 'url': reverse('dashboard')},
            {'name': 'Notifications', 'url': reverse('notification_list')},
        ],
    }
    return JsonResponse(data, content_type='application/manifest+json')


def service_worker(request):
    """Served from the site root so it can control every page."""
    context = {
        'version': PWA_VERSION,
        'offline_url': reverse('pwa_offline'),
        'precache': [
            static('css/style.css'),
            static('js/main.js'),
            static('js/pwa.js'),
            static('pwa/icons/icon-192.png'),
        ],
    }
    response = render(request, 'pwa/service-worker.js', context, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


def offline(request):
    return render(request, 'pwa/offline.html')