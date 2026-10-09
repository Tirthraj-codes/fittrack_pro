from django.urls import path

from . import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('log/', views.reminder_log, name='reminder_log'),
    path('run-now/', views.run_now, name='reminder_run_now'),
    path('run/<str:token>/', views.run_by_token, name='reminder_run_token'),
]