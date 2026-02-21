# ledger/forms.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, HTML, Layout
from django.db.models.functions import Lower

from ledger.models import Category, Job, Contact, SubCategory, Transaction, Team
from vehicles.models import Vehicle



class TransactionForm(forms.ModelForm):
    """Business-scoped transaction form.

    - Filters all dropdowns by the active Business.
    - Shows Type + Category as derived badges after Subcategory selection.
    - Uses explicit Transport + Vehicle fields (Vehicle appears only when relevant).
    """

    class Meta:
        model = Transaction
        fields = [
            "date",
            "amount",
            "subcategory",
            "is_refund",
            "invoice_number",
            "receipt",
            "contact",
            "team",
            "job",
            "transport_type",
            "vehicle",
            "description",
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
        self.fields["contact"].queryset = Contact.objects.filter(business=self.business).order_by("display_name")
        self.fields["contact"].label = "Contact"
        self.fields["team"].queryset = Team.objects.filter(business=self.business, is_active=True).order_by("sort_order", "name")
        self.fields["job"].queryset = Job.objects.filter(business=self.business).order_by("-is_active", "job_number", "title")

        self.fields["is_refund"].widget.attrs.setdefault("class", "form-check-input")

        # Transport + Vehicle fields
        self.fields["transport_type"].label = "Transport"
        self.fields["transport_type"].widget.attrs.setdefault("class", "form-select")
        self.fields["vehicle"].queryset = Vehicle.objects.filter(
            business=self.business,
            is_active=True,
            is_business=True,
        ).order_by("sort_order", "label")
        self.fields["vehicle"].required = False
        self.fields["vehicle"].widget.attrs.setdefault("class", "form-select")

        self.fields["amount"].widget.attrs.setdefault("class", "form-control")
        self.fields["amount"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["amount"].widget.attrs.setdefault("step", "0.01")

        # Receipt upload
        self.fields["receipt"].required = False
        self.fields["receipt"].label = "Receipt"
        self.fields["receipt"].widget.attrs.setdefault("class", "form-control")
        # Helpful on mobile (camera / files). Browsers ignore unsupported tokens.
        self.fields["receipt"].widget.attrs.setdefault("accept", "image/*,application/pdf")

        # Invoice number: prefill next number for convenience (still user-editable)
        if not (self.instance and self.instance.pk) and not (self.initial.get("invoice_number") or "").strip():
            nxt = self._next_invoice_number()
            if nxt:
                self.initial["invoice_number"] = nxt

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True

        self.helper.layout = Layout(
            HTML('<div class="fw-semibold mb-2">Details</div>'),
            Div(
                Div(Field("date"), css_class="col-12 col-sm-6 col-md-4"),
                Div(Field("amount"), css_class="col-12 col-sm-6 col-md-4"),
                css_class="row g-3",
            ),
            HTML('{% include "ledger/partials/_subcategory_select.html" %}'),
            Div(
                Div(Field("is_refund"), css_class="col-12 col-md-3"),
                Div(Field("invoice_number"), css_class="col-12 col-md-5"),
                Div(HTML('{% include "ledger/partials/_contact_select.html" %}'), css_class="col-12 col-md-4"),
                css_class="row g-3",
            ),
            Div(
                Div(Field("team"), css_class="col-12 col-md-4"),
                Div(Field("job"), css_class="col-12 col-md-4"),
                Div(Field("transport_type"), css_class="col-12 col-md-4"),
                css_class="row g-3",
            ),
            Div(
                Div(Field("vehicle"), css_class="col-12 col-md-6", css_id="vehicleWrap"),
                Div(HTML(""), css_class="col-12 col-md-6"),
                css_class="row g-3",
            ),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Notes</div>'),
            Field("description"),
            Field("notes"),
            HTML('{% include "ledger/partials/_receipt_upload.html" %}'),
        )
    def clean(self):
        cleaned = super().clean()

        transport = (cleaned.get("transport_type") or "").strip()
        vehicle = cleaned.get("vehicle")

        if not transport:
            # clear transport fields when empty
            self.instance.transport_type = ""
            self.instance.vehicle = None
            return cleaned

        if transport in ("personal_vehicle", "rental_car"):
            self.instance.transport_type = transport
            self.instance.vehicle = None
            return cleaned

        if transport == "business_vehicle":
            self.instance.transport_type = "business_vehicle"
            self.instance.vehicle = vehicle
            return cleaned

        raise ValidationError({"transport_type": "Invalid transport type."})

    def _next_invoice_number(self) -> str:
        """Best-effort next invoice number.

        Uses the max numeric invoice_number for this business + 1.
        If none exist, returns empty string.
        """
        qs = (
            Transaction.objects
            .filter(business=self.business)
            .exclude(invoice_number="")
            .values_list("invoice_number", flat=True)
        )

        best = None
        for s in qs:
            s = (s or "").strip()
            if not s.isdigit():
                continue
            try:
                n = int(s)
            except Exception:
                continue
            if best is None or n > best:
                best = n

        if best is None:
            return ""
        return str(best + 1)



#<------------------------------------  P A Y E E   F O R M   ---------------------------->

class ContactForm(forms.ModelForm):
    """Business-scoped Contact form."""
    class Meta:
        model = Contact
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
            raise ValueError("ContactForm requires business=...")

        # Mobile-friendly defaults
        for name, field in self.fields.items():
            widget = field.widget
            if hasattr(widget, "attrs"):
                if getattr(widget, "input_type", "") != "checkbox":
                    widget.attrs.setdefault("class", "form-control")

        # Checkbox styling
        for cb in ("is_vendor", "is_customer", "is_contractor"):
            self.fields[cb].widget.attrs.setdefault("class", "form-check-input")




#<------------------------------------  J O B   F O R M   ---------------------------->


class JobForm(forms.ModelForm):
    """Business-scoped Job form."""

    class Meta:
        model = Job
        fields = [
            "job_number",
            "title",
            "client",
            "job_type",
            "city",
            "address",
            "notes",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if not self.business:
            raise ValueError("JobForm requires business=...")

        # Scope client dropdown to contacts marked as customers in this business
        self.fields["client"].queryset = (
            Contact.objects.filter(business=self.business, is_customer=True)
            .order_by("display_name")
        )

        # Mobile-friendly defaults
        for name, field in self.fields.items():
            widget = field.widget
            if hasattr(widget, "attrs"):
                if getattr(widget, "input_type", "") != "checkbox":
                    widget.attrs.setdefault("class", "form-control")

        self.fields["is_active"].widget.attrs.setdefault("class", "form-check-input")


#<------------------------------------  T E A M   F O R M   ---------------------------->


class TeamForm(forms.ModelForm):
    """Business-scoped Team form."""

    class Meta:
        model = Team
        fields = [
            "name",
            "is_active",
            "sort_order",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if not self.business:
            raise ValueError("TeamForm requires business=...")

        for name, field in self.fields.items():
            widget = field.widget
            if hasattr(widget, "attrs"):
                if getattr(widget, "input_type", "") != "checkbox":
                    widget.attrs.setdefault("class", "form-control")

        self.fields["is_active"].widget.attrs.setdefault("class", "form-check-input")


# <------------------------------------  S U B - C A T E G O R Y   F O R M  ---------------------------->


class SubCategoryForm(forms.ModelForm):
    """Business-scoped SubCategory form."""

    class Meta:
        model = SubCategory
        fields = [
            "category",
            "name",
            "slug",
            "is_active",
            "sort_order",
            "book_enabled",
            "tax_enabled",
            "schedule_c_line",
            "deduction_rule",
            "is_1099_reportable_default",
            "is_capitalizable",
            "requires_contact",
            "contact_role",
            "requires_transport",
            "requires_vehicle",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if not self.business:
            raise ValueError("SubCategoryForm requires business=...")

        self.fields["category"].queryset = (
            Category.objects.filter(business=self.business, is_active=True)
            .order_by("name")
        )

        # Mobile-friendly defaults
        for name, field in self.fields.items():
            widget = field.widget
            if hasattr(widget, "attrs"):
                if getattr(widget, "input_type", "") != "checkbox":
                    widget.attrs.setdefault("class", "form-control")

        for cb in (
            "is_active",
            "book_enabled",
            "tax_enabled",
            "is_1099_reportable_default",
            "is_capitalizable",
            "requires_contact",
            "requires_transport",
            "requires_vehicle",
        ):
            self.fields[cb].widget.attrs.setdefault("class", "form-check-input")

        # Better select styling
        self.fields["category"].widget.attrs.setdefault("class", "form-select")
        self.fields["schedule_c_line"].widget.attrs.setdefault("class", "form-select")
        self.fields["deduction_rule"].widget.attrs.setdefault("class", "form-select")
        self.fields["contact_role"].widget.attrs.setdefault("class", "form-select")

        # Optional: keep slug small and unobtrusive
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Optional. Leave blank to auto-generate." 

        # Crispy layout (no <form> tag; templates own the form tag)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            HTML('<div class="fw-semibold mb-2">Basics</div>'),
            Div(
                Div(Field("category"), css_class="col-12 col-md-6"),
                Div(Field("name"), css_class="col-12 col-md-6"),
                css_class="row g-3",
            ),
            Div(
                Div(Field("slug"), css_class="col-12 col-md-6"),
                Div(Field("sort_order"), css_class="col-12 col-md-3"),
                Div(Field("is_active"), css_class="col-12 col-md-3 pt-md-4"),
                css_class="row g-3 mt-0",
            ),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Reporting</div>'),
            Div(
                Div(Field("book_enabled"), css_class="col-12 col-md-3"),
                Div(Field("tax_enabled"), css_class="col-12 col-md-3"),
                Div(Field("schedule_c_line"), css_class="col-12 col-md-3"),
                Div(Field("deduction_rule"), css_class="col-12 col-md-3"),
                css_class="row g-3",
            ),
            HTML("<hr class='my-4'>"),
            HTML('<div class="fw-semibold mb-2">Rules</div>'),
            Div(
                Div(Field("is_1099_reportable_default"), css_class="col-12 col-md-3"),
                Div(Field("is_capitalizable"), css_class="col-12 col-md-3"),
                Div(Field("requires_contact"), css_class="col-12 col-md-3"),
                Div(Field("contact_role"), css_class="col-12 col-md-3"),
                css_class="row g-3",
            ),
            Div(
                Div(Field("requires_transport"), css_class="col-12 col-md-3"),
                Div(Field("requires_vehicle"), css_class="col-12 col-md-3"),
                css_class="row g-3 mt-0",
            ),
        )
