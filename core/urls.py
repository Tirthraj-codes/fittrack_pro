from django.urls import path

from . import pwa_views, views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/trainer/', views.trainer_dashboard, name='trainer_dashboard'),
    path('dashboard/member/', views.member_dashboard, name='member_dashboard'),

    # PWA files (these must live at the site root)
    path('manifest.webmanifest', pwa_views.manifest, name='pwa_manifest'),
    path('service-worker.js', pwa_views.service_worker, name='pwa_service_worker'),
    path('offline/', pwa_views.offline, name='pwa_offline'),
]