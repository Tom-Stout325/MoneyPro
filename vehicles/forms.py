
from __future__ import annotations

from django import forms
from django.utils import timezone

from invoices.models import Invoice
from ledger.models import Job
from vehicles.models import Vehicle, VehicleMiles, VehicleYear


class VehicleForm(forms.ModelForm):
    create_current_year_record = forms.BooleanField(
        required=False,
        initial=True,
        label="Create current-year annual record after save",
    )

    class Meta:
        model = Vehicle
        fields = [
            "label",
            "year",
            "make",
            "model",
            "vin_last6",
            "plate",
            "in_service_date",
            "sold_date",
            "is_business",
            "is_active",
            "sort_order",
        ]
        widgets = {
            "in_service_date": forms.DateInput(attrs={"type": "date"}),
            "sold_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")
        if self.instance and self.instance.pk:
            self.fields["create_current_year_record"].initial = False


class VehicleYearForm(forms.ModelForm):
    class Meta:
        model = VehicleYear
        fields = [
            "vehicle",
            "year",
            "odometer_start",
            "odometer_end",
            "standard_mileage_rate",
            "deduction_method",
            "is_locked",
        ]
        widgets = {
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "odometer_start": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "odometer_end": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "standard_mileage_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "placeholder": "e.g. 0.670"}),
            "deduction_method": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if business:
            self.fields["vehicle"].queryset = Vehicle.objects.filter(business=business).order_by("sort_order", "label")
        self.fields["vehicle"].widget.attrs.update({"class": "form-select"})
        self.fields["is_locked"].widget.attrs.update({"class": "form-check-input"})

        if not self.instance.pk:
            initial_vehicle = self.initial.get("vehicle") or self.data.get("vehicle")
            initial_year = self.initial.get("year") or self.data.get("year") or timezone.localdate().year
            try:
                initial_vehicle = int(initial_vehicle) if initial_vehicle else None
                initial_year = int(initial_year)
            except (TypeError, ValueError):
                initial_vehicle = None
                initial_year = timezone.localdate().year

            if business and initial_vehicle:
                prior = (
                    VehicleYear.objects.filter(business=business, vehicle_id=initial_vehicle, year__lt=initial_year)
                    .order_by("-year")
                    .first()
                )
                if prior:
                    self.fields["odometer_start"].initial = prior.odometer_end
                    if prior.standard_mileage_rate is not None:
                        self.fields["standard_mileage_rate"].initial = prior.standard_mileage_rate


class VehicleMilesForm(forms.ModelForm):
    class Meta:
        model = VehicleMiles
        fields = ["date", "vehicle", "mileage_type", "begin", "end", "job", "invoice", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "vehicle": forms.Select(attrs={"class": "form-select"}),
            "mileage_type": forms.Select(attrs={"class": "form-select"}),
            "begin": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "end": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "job": forms.Select(attrs={"class": "form-select"}),
            "invoice": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional trip note"}),
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

        if business:
            self.fields["vehicle"].queryset = Vehicle.objects.filter(business=business, is_active=True).order_by("sort_order", "label")
            self.fields["job"].queryset = Job.objects.filter(business=business).order_by("-is_active", "-job_year", "job_number", "label")
            self.fields["invoice"].queryset = Invoice.objects.filter(business=business).order_by("-issue_date", "-id")

        self.fields["job"].required = False
        self.fields["invoice"].required = False

        vehicle_id = self.initial.get("vehicle") or self.data.get("vehicle") or getattr(self.instance, "vehicle_id", None)
        if business and vehicle_id and not self.instance.pk:
            try:
                last_entry = VehicleMiles.objects.filter(business=business, vehicle_id=int(vehicle_id)).order_by("-date", "-id").first()
                if last_entry and last_entry.end is not None and self.fields["begin"].initial in (None, ""):
                    self.fields["begin"].initial = last_entry.end
            except (TypeError, ValueError):
                pass


class QuickMileageForm(VehicleMilesForm):
    class Meta(VehicleMilesForm.Meta):
        fields = ["date", "vehicle", "begin", "end", "job", "invoice", "notes"]
