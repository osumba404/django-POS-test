from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('phone_number', 'mpesa_receipt_number')
