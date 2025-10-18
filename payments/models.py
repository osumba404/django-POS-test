import uuid
from django.db import models

class Payment(models.Model):
    class Provider(models.TextChoices):
        MPESA = 'mpesa', 'M-Pesa'
        STRIPE = 'stripe', 'Stripe'
        PAYPAL = 'paypal', 'PayPal'
        AMAZON = 'amazon', 'Amazon Pay'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=20, choices=Provider.choices)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='KES')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Provider-specific references
    merchant_request_id = models.CharField(max_length=128, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=128, blank=True, null=True)
    result_code = models.CharField(max_length=16, blank=True, null=True)
    result_desc = models.CharField(max_length=256, blank=True, null=True)

    raw_callback = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.provider}:{self.id} {self.amount} {self.currency} - {self.status}"
