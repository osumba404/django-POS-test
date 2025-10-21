from django.urls import path
from . import views

urlpatterns = [
    path('stk_push/', views.initiate_stk_push, name='stk_push'),
    path('callback/', views.stk_callback, name='stk_callback'),
    path('transactions/', views.transactions_list, name='transactions_list'),
]
