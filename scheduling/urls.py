from django.urls import path

from . import views

urlpatterns = [
    path('', views.schedule_week, name='schedule_week'),
    path('sessions/add/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/cancel/', views.session_cancel, name='session_cancel'),

    path('availability/', views.availability, name='availability'),
    path('availability/<int:pk>/delete/', views.availability_delete, name='availability_delete'),

    path('my-members/', views.my_members, name='my_members'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/<int:member_id>/set/', views.assignment_set, name='assignment_set'),
]