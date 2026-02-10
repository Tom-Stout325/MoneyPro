from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import TransactionForm
from .models import Transaction


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "ledger/transactions/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Transaction.objects.filter(business=self.request.business)
            .select_related("category", "subcategory")
            .order_by("-date", "-id")
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(description__icontains=q)
                | Q(notes__icontains=q)
                | Q(subcategory__name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        return ctx


class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "ledger/transactions/transaction_form.html"
    success_url = reverse_lazy("ledger:transaction_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "ledger/transactions/transaction_form.html"
    success_url = reverse_lazy("ledger:transaction_list")

    def get_queryset(self):
        return Transaction.objects.filter(business=self.request.business)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = "ledger/transactions/transaction_confirm_delete.html"
    success_url = reverse_lazy("ledger:transaction_list")

    def get_queryset(self):
        return Transaction.objects.filter(business=self.request.business)
