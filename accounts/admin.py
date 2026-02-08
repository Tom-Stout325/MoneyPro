from __future__ import annotations
from django.contrib import admin

# Register your models here.
# accounts/admin.py  (or the app where CompanyProfile is defined)

from django.contrib import admin
from django.db.models import QuerySet

from .models import CompanyProfile


class OwnedOneToOneAdminMixin:
    """
    For non-superusers:
    - only show their own profile
    - auto-assign user on create
    """
    def get_queryset(self, request) -> QuerySet:
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("user")
        return qs.select_related("user").filter(user=request.user)

    def save_model(self, request, obj, form, change):
        if not change and not getattr(obj, "user_id", None):
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return obj.user_id == request.user.id

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return obj.user_id == request.user.id

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return obj.user_id == request.user.id


@admin.register(CompanyProfile)
class CompanyProfileAdmin(OwnedOneToOneAdminMixin, admin.ModelAdmin):
    list_display = ("company_name", "user", "billing_email", "phone_display", "timezone", "currency", "created_at")
    search_fields = ("company_name", "legal_name", "ein", "billing_email", "user__username", "user__email")
    list_filter = ("timezone", "currency", "country")
    readonly_fields = ("created_at", "updated_at", "phone_display", "is_complete")

    fieldsets = (
        ("Identity", {
            "fields": ("user", "company_name", "legal_name", "ein"),
        }),
        ("Contact", {
            "fields": ("phone", "phone_display", "billing_email"),
        }),
        ("Address", {
            "fields": ("address_line1", "address_line2", "city", "state", "postal_code", "country"),
        }),
        ("Branding", {
            "fields": ("logo",),
        }),
        ("Locale / Formatting", {
            "fields": ("timezone", "currency"),
        }),
        ("Status", {
            "fields": ("is_complete", "created_at", "updated_at"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Lock user field for non-superusers to prevent cross-user assignment.
        """
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and "user" in form.base_fields:
            form.base_fields["user"].disabled = True
        return form
