from __future__ import annotations

from datetime import date
from django import forms


class ContractorYearForm(forms.Form):
    year = forms.ChoiceField(choices=[], required=True)

    def __init__(self, *args, year_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if year_choices:
            self.fields["year"].choices = [(y, y) for y in year_choices]
        self.fields["year"].widget.attrs.update({"class": "form-select form-select-sm"})


class W9PortalForm(forms.Form):
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    business_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    address1 = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    address2 = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    city = forms.CharField(max_length=128, widget=forms.TextInput(attrs={"class": "form-control"}))
    state = forms.CharField(max_length=2, widget=forms.TextInput(attrs={"class": "form-control", "maxlength": "2"}))
    zip_code = forms.CharField(max_length=10, widget=forms.TextInput(attrs={"class": "form-control"}))

    taxpayer_id_type = forms.ChoiceField(
        choices=[("ssn", "SSN"), ("ein", "EIN")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    tin = forms.CharField(
        max_length=11,
        widget=forms.PasswordInput(attrs={"class": "form-control"}, render_value=False),
        help_text="Enter your SSN or EIN. We store only the last 4 digits.",
    )

    signature_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    signature_date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def clean_state(self):
        val = (self.cleaned_data.get("state") or "").strip().upper()
        if len(val) != 2:
            raise forms.ValidationError("Enter a 2-letter state code.")
        return val

    def clean_tin(self):
        raw = (self.cleaned_data.get("tin") or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) != 9:
            raise forms.ValidationError("Enter a valid 9-digit SSN/EIN.")
        return digits
