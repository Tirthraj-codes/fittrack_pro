from django.urls import path

from . import views

urlpatterns = [
    path('', views.progress_overview, name='progress_overview'),
    path('mine/', views.my_progress, name='my_progress'),
    path('plan/', views.my_plan, name='my_plan'),
    path('member/<int:member_id>/', views.member_progress, name='member_progress'),
    path('member/<int:member_id>/plan/', views.member_plan, name='member_plan'),
    path('add/', views.entry_create, name='entry_create'),
    path('entries/<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('entries/<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('goal/', views.goal_create, name='goal_create'),
]