from django.urls import path

from . import views

urlpatterns = [
    path('', views.membership_list, name='membership_list'),
    path('mine/', views.my_membership, name='my_membership'),
    path('assign/', views.membership_assign, name='membership_assign'),
    path('<int:pk>/renew/', views.membership_renew, name='membership_renew'),
    path('<int:pk>/upgrade/', views.membership_upgrade, name='membership_upgrade'),
    path('<int:pk>/cancel/', views.membership_cancel, name='membership_cancel'),

    path('plans/', views.plan_list, name='plan_list'),
    path('plans/add/', views.plan_create, name='plan_create'),
    path('plans/<int:pk>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:pk>/toggle/', views.plan_toggle, name='plan_toggle'),
]