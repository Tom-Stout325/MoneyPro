# ledger/forms.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, HTML

from .models import Transaction
from vehicles.models import Vehicle




class TransactionForm(forms.ModelForm):
    transport_selector = forms.ChoiceField(required=False, label="Transport")

    class Meta:
        model = Transaction
        fields = [
            "date",
            "amount",
            "description",
            "subcategory",
            "payee",
            "job",
            "invoice_number",
            "transport_selector",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False  
        self.helper.disable_csrf = True 
        self.fields["amount"].widget.attrs.setdefault("class", "form-control")
        self.fields["amount"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["amount"].widget.attrs.setdefault("step", "0.01")

        self.helper.layout = Layout(
            HTML('<div class="fw-semibold mb-2">Details</div>'),
            Div(
                Div(Field("date"), css_class="col-12 col-sm-6 col-md-4"),
                Div(Field("amount"), css_class="col-12 col-sm-6 col-md-4"),
                Div(Field("description"), css_class="col-12 col-md-4"),
                css_class="row g-3",
            ),
            HTML('<div class="mt-3">{% include "ledger/transactions/_subcategory_select.html" %}</div>'),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Links & extras</div>'),
            Div(
                Div(Field("job"), css_class="col-12 col-md-6"),
                Div(Field("invoice_number"), css_class="col-12 col-md-6"),
                css_class="row g-3",
            ),
            HTML('{% include "ledger/transactions/_payee_and_transport.html" %}'),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Notes</div>'),
            Field("notes"),
            HTML("""
              <div class="alert alert-light border small mt-3 mb-0">
                <div class="fw-semibold mb-1">Receipts</div>
                <div class="text-muted">
                  Next: drag & drop upload + choose file + mobile camera capture.
                </div>
              </div>
            """),
        )

    def clean_transport_selector(self):
        val = (self.cleaned_data.get("transport_selector") or "").strip()
        if not val:
            return ""
        if val in ("personal_vehicle", "rental_car"):
            return val
        if val.startswith("veh:"):
            try:
                vehicle_id = int(val.split(":", 1)[1])
            except Exception:
                raise ValidationError("Invalid vehicle selection.")

            if not self.user or not getattr(self.user, "is_authenticated", False):
                raise ValidationError("Invalid vehicle selection.")

            if not Vehicle.objects.filter(
                user=self.user, pk=vehicle_id, is_active=True, is_business=True
            ).exists():
                raise ValidationError("Invalid vehicle selection.")
            return val
        raise ValidationError("Invalid transport selection.")

    def clean(self):
        cleaned = super().clean()
        val = (cleaned.get("transport_selector") or "").strip()
        if not val:
            self.instance.transport_type = ""
            self.instance.vehicle = None
            return cleaned
        if val in ("personal_vehicle", "rental_car"):
            self.instance.transport_type = val
            self.instance.vehicle = None
            return cleaned
        if val.startswith("veh:"):
            vehicle_id = int(val.split(":", 1)[1])
            self.instance.transport_type = "business_vehicle"
            self.instance.vehicle_id = vehicle_id
            return cleaned
        return cleaned
