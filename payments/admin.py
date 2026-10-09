from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('member', 'description', 'amount', 'status', 'due_date', 'method', 'receipt_no')
    list_filter = ('status', 'method')
    search_fields = ('member__username', 'member__first_name', 'member__last_name', 'transaction_id', 'receipt_no')