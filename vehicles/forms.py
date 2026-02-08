from __future__ import annotations

from django import forms
from vehicles.models import VehicleMiles, VehicleYear, Vehicle


class VehicleForm(forms.ModelForm):
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

        # Mobile-friendly Bootstrap classes
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")



class VehicleYearForm(forms.ModelForm):
    class Meta:
        model = VehicleYear
        fields = ["vehicle", "year", "odometer_start", "odometer_end", "deduction_method", "is_locked"]
        widgets = {
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "odometer_start": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "odometer_end": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "deduction_method": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and getattr(user, "is_authenticated", False):
            self.fields["vehicle"].queryset = self.fields["vehicle"].queryset.filter(user=user).order_by("sort_order", "label")
        self.fields["vehicle"].widget.attrs.update({"class": "form-select"})
        self.fields["is_locked"].widget.attrs.update({"class": "form-check-input"})


class VehicleMilesForm(forms.ModelForm):
    class Meta:
        model = VehicleMiles
        fields = ["date", "vehicle", "mileage_type", "begin", "end", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "vehicle": forms.Select(attrs={"class": "form-select"}),
            "mileage_type": forms.Select(attrs={"class": "form-select"}),
            "begin": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "end": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "notes": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and getattr(user, "is_authenticated", False):
            self.fields["vehicle"].queryset = self.fields["vehicle"].queryset.filter(user=user, is_active=True).order_by("sort_order", "label")