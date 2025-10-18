from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'phone_number', 'amount', 'currency', 'status', 'created_at')
    search_fields = ('id', 'phone_number', 'merchant_request_id', 'checkout_request_id')
    list_filter = ('provider', 'status')
