from django.urls import path
from .views import (
    TransactionListView,
    TransactionCreateView,
    TransactionUpdateView,
    TransactionDeleteView,
    PayeeListView,
    PayeeCreateView,
    PayeeUpdateView,
    PayeeDeleteView,
)

app_name = "ledger"

urlpatterns = [
    path("transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),
    
    path("payees/", PayeeListView.as_view(), name="payee_list"),
    path("payees/new/", PayeeCreateView.as_view(), name="payee_create"),
    path("payees/<int:pk>/edit/", PayeeUpdateView.as_view(), name="payee_update"),
    path("payees/<int:pk>/delete/", PayeeDeleteView.as_view(), name="payee_delete"),
]
