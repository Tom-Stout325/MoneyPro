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
    SubCategoryListView,
    SubCategoryCreateView,
    SubCategoryUpdateView,
    SubCategoryDeleteView,
    TeamListView,
    TeamCreateView,
    TeamUpdateView,
    TeamDeleteView,
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

    path("subcategories/", SubCategoryListView.as_view(), name="subcategory_list"),
    path("subcategories/new/", SubCategoryCreateView.as_view(), name="subcategory_create"),
    path("subcategories/<int:pk>/edit/", SubCategoryUpdateView.as_view(), name="subcategory_update"),
    path("subcategories/<int:pk>/delete/", SubCategoryDeleteView.as_view(), name="subcategory_delete"),

    path("teams/", TeamListView.as_view(), name="team_list"),
    path("teams/new/", TeamCreateView.as_view(), name="team_create"),
    path("teams/<int:pk>/edit/", TeamUpdateView.as_view(), name="team_update"),
    path("teams/<int:pk>/delete/", TeamDeleteView.as_view(), name="team_delete"),
]
