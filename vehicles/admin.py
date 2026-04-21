from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet

from core.models import BusinessMembership
from .models import Vehicle, VehicleMiles, VehicleYear


class BusinessAdminMixin(admin.ModelAdmin):
    """Scope admin records to the active business for non-superusers."""

    def _user_business(self, request):
        membership = (
            BusinessMembership.objects.filter(user=request.user, is_active=True)
            .select_related("business")
            .first()
        )
        return membership.business if membership else None

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        biz = self._user_business(request)
        return qs.filter(business=biz) if biz else qs.none()

    def save_model(self, request, obj, form, change):
        if not change and getattr(obj, "business_id", None) is None and not request.user.is_superuser:
            biz = self._user_business(request)
            obj.business = biz
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if request.user.is_superuser:
            return super().formfield_for_foreignkey(db_field, request, **kwargs)
        biz = self._user_business(request)
        model = db_field.remote_field.model
        if biz and hasattr(model, "business_id"):
            kwargs["queryset"] = model.objects.filter(business=biz)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Vehicle)
class VehicleAdmin(BusinessAdminMixin):
    list_display = ("label", "year", "make", "model", "is_business", "is_active")
    list_filter = ("is_business", "is_active", "make")
    search_fields = ("label", "make", "model", "plate", "vin_last6")


@admin.register(VehicleYear)
class VehicleYearAdmin(BusinessAdminMixin):
    list_display = (
        "vehicle",
        "year",
        "deduction_method",
        "annual_interest_paid",
        "business_interest_amount_display",
        "business_use_pct_display",
        "is_locked",
    )
    list_filter = ("year", "deduction_method", "is_locked")
    search_fields = ("vehicle__label",)
    readonly_fields = (
        "business_interest_amount_display",
        "business_use_pct_display",
        "actual_expenses_with_interest_total_display",
    )
    fieldsets = (
        (None, {"fields": ("vehicle", "year", "deduction_method", "is_locked")}),
        ("Odometer", {"fields": ("odometer_start", "odometer_end", "standard_mileage_rate")}),
        (
            "Loan interest",
            {
                "fields": (
                    "annual_interest_paid",
                    "business_use_pct_display",
                    "business_interest_amount_display",
                    "actual_expenses_with_interest_total_display",
                ),
                "description": "Enter the full annual interest paid. MoneyPro calculates the business-use portion from the annual business-use percentage.",
            },
        ),
    )

    @admin.display(description="Business use %")
    def business_use_pct_display(self, obj):
        return f"{obj.business_use_pct:.2f}%" if obj.business_use_pct is not None else "—"

    @admin.display(description="Business interest amount")
    def business_interest_amount_display(self, obj):
        return obj.business_interest_amount

    @admin.display(description="Actual expenses + interest")
    def actual_expenses_with_interest_total_display(self, obj):
        return obj.actual_expenses_with_interest_total


@admin.register(VehicleMiles)
class VehicleMilesAdmin(BusinessAdminMixin):
    list_display = ("date", "vehicle", "mileage_type", "total", "job", "invoice")
    list_filter = ("mileage_type", "date", "vehicle")
    search_fields = ("vehicle__label", "notes", "job__label", "invoice__invoice_number")
    readonly_fields = ("total",)
