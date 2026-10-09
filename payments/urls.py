from django.urls import path

from . import views

urlpatterns = [
    path('', views.payment_list, name='payment_list'),
    path('add/', views.payment_create, name='payment_create'),
    path('mine/', views.my_payments, name='my_payments'),
    path('<int:pk>/pay/', views.checkout, name='payment_checkout'),
    path('<int:pk>/success/', views.success, name='payment_success'),
    path('<int:pk>/receipt/', views.receipt_pdf, name='payment_receipt'),
    path('<int:pk>/mark-paid/', views.payment_mark_paid, name='payment_mark_paid'),
    path('<int:pk>/cancel/', views.payment_cancel, name='payment_cancel'),
]