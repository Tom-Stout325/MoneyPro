from __future__ import annotations

from django import forms

from core.models import Business, BusinessMembership


class BusinessCreateForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Business name"}),
        }


class BusinessSwitchForm(forms.Form):
    business_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Business",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        memberships = (
            BusinessMembership.objects.filter(user=user, is_active=True)
            .select_related("business")
            .order_by("business__name")
        )
        self.fields["business_id"].choices = [(m.business_id, m.business.name) for m in memberships]
