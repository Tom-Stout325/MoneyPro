# Vehicle/admin.py
from __future__ import annotations
from django.contrib import admin
from django.db.models import QuerySet
from core.models import BusinessMembership
from .models import Vehicle


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

@admin.register(Vehicle)
class VehicleAdmin(BusinessAdminMixin):
    list_display = ("label", "is_active")
    list_filter = ("label", "is_active")
    search_fields = ("label", "is_active")
