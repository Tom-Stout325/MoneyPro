from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re
from .models import CompanyProfile


US_STATE_CHOICES = [
    ("", "—"),
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]



class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "company_name", "legal_name", "ein",
            "phone", "billing_email",
            "address_line1", "address_line2", "city", "state", "postal_code", "country",
            "timezone", "currency",
            "logo",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Business name"}),
            "legal_name": forms.TextInput(attrs={"placeholder": "Legal name (optional)"}),
            "ein": forms.TextInput(attrs={"placeholder": "12-3456789", "inputmode": "numeric"}),

            "phone": forms.TextInput(attrs={"placeholder": "Business phone (optional)"}),
            "billing_email": forms.EmailInput(attrs={"placeholder": "Billing email (optional)"}),

            "address_line1": forms.TextInput(attrs={"placeholder": "Address line 1"}),
            "address_line2": forms.TextInput(attrs={"placeholder": "Address line 2 (optional)"}),
            "city": forms.TextInput(attrs={"placeholder": "City"}),

            "postal_code": forms.TextInput(attrs={"placeholder": "ZIP / Postal code"}),
            "country": forms.TextInput(attrs={"placeholder": "Country"}),

            "timezone": forms.TextInput(attrs={"placeholder": "America/Indiana/Indianapolis"}),
            "currency": forms.TextInput(attrs={"placeholder": "USD"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # State dropdown (stores USPS 2-letter codes)
        self.fields["state"].widget = forms.Select(choices=US_STATE_CHOICES)
        self.fields["state"].help_text = "USPS 2-letter code (recommended)."

        # Default country to US when blank
        current_country = (getattr(self.instance, "country", "") or "").strip()
        if not self.initial.get("country") and not current_country:
            self.initial["country"] = "US"
        elif not self.initial.get("country") and current_country:
            self.initial["country"] = current_country

        # Display phone as (xxx)xxx-xxxx if stored as digits-only
        phone = (getattr(self.instance, "phone", "") or "").strip()
        if phone.isdigit() and len(phone) == 10:
            self.initial["phone"] = f"({phone[:3]}){phone[3:6]}-{phone[6:]}"

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        if not raw:
            return ""

        digits = re.sub(r"\D+", "", raw)

        # Handle US leading country code
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        if len(digits) != 10:
            raise forms.ValidationError("Enter a valid 10-digit US phone number.")

        return digits

    def clean_state(self):
        state = (self.cleaned_data.get("state") or "").strip().upper()
        if not state:
            return ""
        if len(state) != 2:
            raise forms.ValidationError("Select a valid US state.")
        return state

    def clean_ein(self):
        raw = (self.cleaned_data.get("ein") or "").strip()
        if not raw:
            return ""

        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) != 9:
            raise ValidationError("EIN must have 9 digits (example: 12-3456789).")

        return f"{digits[:2]}-{digits[2:]}"



User = get_user_model()


class UserInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")

        # Prevent duplicates (common with allauth setups)
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("That email is already in use.")
        return email
