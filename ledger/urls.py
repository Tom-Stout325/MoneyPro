from django.urls import path
from .views import (
    TransactionListView,
    TransactionCreateView,
    TransactionUpdateView,
    TransactionDeleteView,
    ContactListView,
    ContactCreateView,
    ContactUpdateView,
    ContactDeleteView,
    SubCategoryListView,
    SubCategoryCreateView,
    SubCategoryUpdateView,
    SubCategoryDeleteView,
    TeamListView,
    TeamCreateView,
    TeamUpdateView,
    TeamDeleteView,
    JobListView,
    JobDetailView,
    JobCreateView,
    JobUpdateView,
    JobDeleteView,
)

app_name = "ledger"

urlpatterns = [
    path("transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),

    # Contacts (formerly Payees)
    path("contacts/", ContactListView.as_view(), name="contact_list"),
    path("contacts/new/", ContactCreateView.as_view(), name="contact_create"),
    path("contacts/<int:pk>/edit/", ContactUpdateView.as_view(), name="contact_update"),
    path("contacts/<int:pk>/delete/", ContactDeleteView.as_view(), name="contact_delete"),

    # Legacy Payee URLs (aliases)
    path("payees/", ContactListView.as_view(), name="payee_list"),
    path("payees/new/", ContactCreateView.as_view(), name="payee_create"),
    path("payees/<int:pk>/edit/", ContactUpdateView.as_view(), name="payee_update"),
    path("payees/<int:pk>/delete/", ContactDeleteView.as_view(), name="payee_delete"),
    

    path("subcategories/", SubCategoryListView.as_view(), name="subcategory_list"),
    path("subcategories/new/", SubCategoryCreateView.as_view(), name="subcategory_create"),
    path("subcategories/<int:pk>/edit/", SubCategoryUpdateView.as_view(), name="subcategory_update"),
    path("subcategories/<int:pk>/delete/", SubCategoryDeleteView.as_view(), name="subcategory_delete"),

    path("teams/", TeamListView.as_view(), name="team_list"),
    path("teams/new/", TeamCreateView.as_view(), name="team_create"),
    path("teams/<int:pk>/edit/", TeamUpdateView.as_view(), name="team_update"),
    path("teams/<int:pk>/delete/", TeamDeleteView.as_view(), name="team_delete"),
    path("jobs/", JobListView.as_view(), name="job_list"),
    path("jobs/new/", JobCreateView.as_view(), name="job_create"),
    path("jobs/<int:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("jobs/<int:pk>/edit/", JobUpdateView.as_view(), name="job_update"),
    path("jobs/<int:pk>/delete/", JobDeleteView.as_view(), name="job_delete"),

]
