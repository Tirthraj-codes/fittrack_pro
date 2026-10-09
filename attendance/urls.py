from django.urls import path

from . import views

urlpatterns = [
    path('', views.desk, name='attendance_desk'),
    path('scan/', views.scan, name='attendance_scan'),
    path('manual/', views.manual, name='attendance_manual'),
    path('<int:pk>/checkout/', views.record_checkout, name='attendance_checkout'),
    path('history/', views.history, name='attendance_history'),
    path('report/', views.monthly_report, name='attendance_report'),
    path('mine/', views.my_attendance, name='my_attendance'),
    path('qr/<int:pk>/', views.qr_image, name='attendance_qr'),
]