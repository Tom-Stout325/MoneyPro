from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import TransactionForm, PayeeForm
from .models import Transaction, Payee


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "ledger/transactions/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 25

    def get_queryset(self):

        qs = (
            Transaction.objects.filter(business=self.request.business)
            .select_related("category", "subcategory", "payee", "job", "vehicle")
            .order_by("-date", "-id")
        )

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



# <----------------------------------    P A Y E E   V I E W S          ------------------------------>


class PayeeListView(LoginRequiredMixin, ListView):
    model = Payee
    template_name = "ledger/payees/payee_list.html"
    context_object_name = "payees"
    paginate_by = 25

    def get_queryset(self):
        qs = Payee.objects.filter(business=self.request.business).order_by("display_name")
        q = (self.request.GET.get("q") or "").strip()
        role = (self.request.GET.get("role") or "").strip()

        if q:
            qs = qs.filter(
                Q(display_name__icontains=q)
                | Q(legal_name__icontains=q)
                | Q(business_name__icontains=q)
                | Q(email__icontains=q)
            )

        if role == "vendor":
            qs = qs.filter(is_vendor=True)
        elif role == "customer":
            qs = qs.filter(is_customer=True)
        elif role == "contractor":
            qs = qs.filter(is_contractor=True)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["role"] = (self.request.GET.get("role") or "").strip()
        return ctx


class PayeeCreateView(LoginRequiredMixin, CreateView):
    model = Payee
    form_class = PayeeForm
    template_name = "ledger/payees/payee_form.html"
    success_url = reverse_lazy("ledger:payee_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class PayeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Payee
    form_class = PayeeForm
    template_name = "ledger/payees/payee_form.html"
    success_url = reverse_lazy("ledger:payee_list")

    def get_queryset(self):
        return Payee.objects.filter(business=self.request.business)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class PayeeDeleteView(LoginRequiredMixin, DeleteView):
    model = Payee
    template_name = "ledger/payees/payee_confirm_delete.html"
    success_url = reverse_lazy("ledger:payee_list")

    def get_queryset(self):
        return Payee.objects.filter(business=self.request.business)
