from django.urls import path
from . import views

urlpatterns = [
    path('stk_push/', views.initiate_stk_push, name='stk_push'),
    path('callback/', views.stk_callback, name='stk_callback'),
    path('transactions/', views.transactions_list, name='transactions_list'),
    path('callback/test/', views.callback_test, name='callback_test'),
    path('transactions/<int:txn_id>/query/', views.query_stk_status, name='query_stk_status'),
]
