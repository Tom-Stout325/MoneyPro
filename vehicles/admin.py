from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet

from core.models import BusinessMembership
from .models import Vehicle, VehicleMiles, VehicleYear


class BusinessAdminMixin(admin.ModelAdmin):
    """Scope objects to the user's business in Django Admin (for non-superusers)."""

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
        if not request.user.is_superuser:
            biz = self._user_business(request)
            if biz and db_field.name in {"vehicle", "job", "invoice"}:
                qs = db_field.remote_field.model.objects.filter(business=biz)
                if db_field.name == "invoice":
                    qs = qs.select_related("job")
                kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Vehicle)
class VehicleAdmin(BusinessAdminMixin):
    list_display = ("label", "year", "make", "model", "plate", "is_active")
    list_filter = ("is_active", "is_business", "year")
    search_fields = ("label", "make", "model", "plate", "vin_last6")
    ordering = ("sort_order", "label")


@admin.register(VehicleYear)
class VehicleYearAdmin(BusinessAdminMixin):
    list_display = (
        "vehicle",
        "year",
        "odometer_start",
        "odometer_end",
        "total_miles_display",
        "business_miles_display",
        "other_miles_display",
        "deduction_method",
        "is_locked",
    )
    list_filter = ("year", "deduction_method", "is_locked")
    search_fields = ("vehicle__label", "vehicle__make", "vehicle__model", "vehicle__plate")
    autocomplete_fields = ("vehicle",)
    readonly_fields = (
        "total_miles_display",
        "logged_miles_total_display",
        "business_miles_display",
        "reimbursed_miles_display",
        "other_miles_display",
        "business_use_pct_display",
        "actual_expenses_total_display",
        "standard_mileage_deduction_display",
        "deduction_amount_display",
        "missing_data_flags_display",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "vehicle",
                    "year",
                    "deduction_method",
                    "is_locked",
                )
            },
        ),
        (
            "Odometer",
            {
                "fields": (
                    "odometer_start",
                    "odometer_end",
                    "standard_mileage_rate",
                )
            },
        ),
        (
            "Computed summary",
            {
                "fields": (
                    "total_miles_display",
                    "logged_miles_total_display",
                    "business_miles_display",
                    "reimbursed_miles_display",
                    "other_miles_display",
                    "business_use_pct_display",
                    "actual_expenses_total_display",
                    "standard_mileage_deduction_display",
                    "deduction_amount_display",
                    "missing_data_flags_display",
                )
            },
        ),
        (
            "Timestamps",
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )

    @admin.display(description="Total miles")
    def total_miles_display(self, obj):
        return obj.total_miles

    @admin.display(description="Logged miles total")
    def logged_miles_total_display(self, obj):
        return obj.logged_miles_total

    @admin.display(description="Business miles")
    def business_miles_display(self, obj):
        return obj.business_miles

    @admin.display(description="Reimbursed miles")
    def reimbursed_miles_display(self, obj):
        return obj.reimbursed_miles

    @admin.display(description="Other miles")
    def other_miles_display(self, obj):
        return obj.other_miles

    @admin.display(description="Business use %")
    def business_use_pct_display(self, obj):
        pct = obj.business_use_pct
        return f"{pct}%" if pct is not None else "—"

    @admin.display(description="Actual expenses total")
    def actual_expenses_total_display(self, obj):
        return obj.actual_expenses_total

    @admin.display(description="Standard mileage deduction")
    def standard_mileage_deduction_display(self, obj):
        return obj.standard_mileage_deduction

    @admin.display(description="Deduction amount")
    def deduction_amount_display(self, obj):
        return obj.deduction_amount

    @admin.display(description="Missing data flags")
    def missing_data_flags_display(self, obj):
        return "; ".join(obj.missing_data_flags) if obj.missing_data_flags else "—"


@admin.register(VehicleMiles)
class VehicleMilesAdmin(BusinessAdminMixin):
    list_display = (
        "date",
        "vehicle",
        "mileage_type",
        "begin",
        "end",
        "total",
        "job",
        "invoice",
    )
    list_filter = ("mileage_type", "date", "vehicle")
    search_fields = (
        "vehicle__label",
        "job__job_number",
        "job__label",
        "invoice__invoice_number",
        "notes",
    )
    autocomplete_fields = ("vehicle", "job", "invoice")
    readonly_fields = ("total", "created_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "date",
                    "vehicle",
                    "mileage_type",
                    "begin",
                    "end",
                    "total",
                )
            },
        ),
        (
            "Related records",
            {"fields": ("job", "invoice", "notes")},
        ),
        (
            "Timestamps",
            {"classes": ("collapse",), "fields": ("created_at",)},
        ),
    )
