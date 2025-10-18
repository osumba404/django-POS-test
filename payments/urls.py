from django.urls import path
from . import views

urlpatterns = [
    path('mpesa/initiate/', views.initiate_mpesa_stk, name='mpesa_initiate'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('<uuid:payment_id>/status/', views.payment_status, name='payment_status'),
]
