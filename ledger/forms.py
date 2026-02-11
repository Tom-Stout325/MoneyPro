# ledger/forms.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, HTML, Layout
from django.db.models.functions import Lower

from ledger.models import Job, Payee, SubCategory, Transaction
from vehicles.models import Vehicle



class TransactionForm(forms.ModelForm):
    """Business-scoped transaction form.

    - Filters all dropdowns by the active Business.
    - Uses a single 'transport_selector' UI field to drive transport_type + vehicle.
    """

    transport_selector = forms.ChoiceField(required=False, label="Transport")

    class Meta:
        model = Transaction
        fields = [
            "date",
            "amount",
            "is_refund",
            "description",
            "subcategory",
            "payee",
            "job",
            "invoice_number",
            "transport_selector",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if not self.business:
            raise ValueError("TransactionForm requires business=...")

        # Scope dropdowns
        self.fields["subcategory"].queryset = (
            SubCategory.objects
            .filter(business=self.business, is_active=True)
            .select_related("category")
            .order_by(Lower("name"))
        )
        self.fields["payee"].queryset = Payee.objects.filter(business=self.business).order_by("display_name")
        self.fields["job"].queryset = Job.objects.filter(business=self.business).order_by("-year", "title")

        self.fields["is_refund"].widget.attrs.setdefault("class", "form-check-input")

        self.fields["amount"].widget.attrs.setdefault("class", "form-control")
        self.fields["amount"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["amount"].widget.attrs.setdefault("step", "0.01")

        vehicle_choices = [
            (f"veh:{v.id}", v.label)
            for v in Vehicle.objects.filter(
                business=self.business,
                is_active=True,
                is_business=True,
            ).order_by("sort_order", "label")
        ]

        self.fields["transport_selector"].choices = [
            ("", "—"),
            ("personal_vehicle", "Personal vehicle"),
            ("rental_car", "Rental car"),
            *vehicle_choices,
        ]

        if self.instance and self.instance.pk:
            if self.instance.transport_type == "business_vehicle" and self.instance.vehicle_id:
                self.initial["transport_selector"] = f"veh:{self.instance.vehicle_id}"
            elif self.instance.transport_type in ("personal_vehicle", "rental_car"):
                self.initial["transport_selector"] = self.instance.transport_type
            else:
                self.initial["transport_selector"] = ""

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True

        self.helper.layout = Layout(
            HTML('<div class="fw-semibold mb-2">Details</div>'),
            Div(
                Div(Field("date"), css_class="col-12 col-sm-6 col-md-4"),
                Div(Field("amount"), css_class="col-12 col-sm-6 col-md-4"),
                Div(Field("description"), css_class="col-12 col-md-4"),
                css_class="row g-3",
            ),
            HTML('{% include "ledger/partials/_subcategory_select.html" %}'),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Links & extras</div>'),
            Div(
                Div(Field("job"), css_class="col-12 col-md-6"),
                Div(Field("invoice_number"), css_class="col-12 col-md-6"),
                css_class="row g-3",
            ),
            HTML('{% include "ledger/partials/_payee_and_transport.html" %}'),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Notes</div>'),
            Field("notes"),
            HTML(
                """
                <div class="alert alert-light border small mt-3 mb-0">
                  <div class="fw-semibold mb-1">Receipts</div>
                  <div class="text-muted">
                    Next: drag & drop upload + choose file + mobile camera capture.
                  </div>
                </div>
                """
            ),
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
            except Exception as exc:
                raise ValidationError("Invalid vehicle selection.") from exc

            if not Vehicle.objects.filter(
                business=self.business,
                pk=vehicle_id,
                is_active=True,
                is_business=True,
            ).exists():
                raise ValidationError("Invalid vehicle selection.")

            return val

        raise ValidationError("Invalid transport selection.")

    def clean(self):
        cleaned = super().clean()
        val = (cleaned.get("transport_selector") or "").strip()

        # If transport selector is empty, clear transport fields
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



#<------------------------------------  P A Y E E   F O R M   ---------------------------->

class PayeeForm(forms.ModelForm):
    """Business-scoped Payee form."""
    class Meta:
        model = Payee
        fields = [
            "display_name",
            "legal_name",
            "business_name",
            "email",
            "phone",
            "address1",
            "address2",
            "city",
            "state",
            "zip_code",
            "country",
            "is_vendor",
            "is_customer",
            "is_contractor",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if not self.business:
            raise ValueError("PayeeForm requires business=...")

        # Mobile-friendly defaults
        for name, field in self.fields.items():
            widget = field.widget
            if hasattr(widget, "attrs"):
                if getattr(widget, "input_type", "") != "checkbox":
                    widget.attrs.setdefault("class", "form-control")

        # Checkbox styling
        for cb in ("is_vendor", "is_customer", "is_contractor"):
            self.fields[cb].widget.attrs.setdefault("class", "form-check-input")
