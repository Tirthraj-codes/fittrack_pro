from django.urls import path

from . import views

urlpatterns = [
    path('', views.report_dashboard, name='report_dashboard'),
    path('export/summary.pdf', views.export_summary, name='export_summary'),
    path('export/payments.csv', views.export_payments, name='export_payments'),
    path('export/dues.csv', views.export_dues, name='export_dues'),
    path('export/memberships.csv', views.export_memberships, name='export_memberships'),
    path('export/attendance.csv', views.export_attendance, name='export_attendance'),
]