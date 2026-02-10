# ledger/admin.py
from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet

from core.models import BusinessMembership
from .models import Category, Job, Payee, PayeeTaxProfile, SubCategory, Transaction


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


@admin.register(Category)
class CategoryAdmin(BusinessAdminMixin):
    list_display = ("name", "category_type", "schedule_c_line", "business")
    list_filter = ("category_type", "business")
    search_fields = ("name",)


@admin.register(SubCategory)
class SubCategoryAdmin(BusinessAdminMixin):
    list_display = ("name", "category", "deduction_rule", "business")
    list_filter = ("deduction_rule", "business")
    search_fields = ("name", "category__name")


@admin.register(Payee)
class PayeeAdmin(BusinessAdminMixin):
    list_display = ("display_name", "is_vendor", "is_customer", "is_contractor", "business")
    list_filter = ("is_vendor", "is_customer", "is_contractor", "business")
    search_fields = ("display_name", "legal_name", "business_name")


@admin.register(PayeeTaxProfile)
class PayeeTaxProfileAdmin(BusinessAdminMixin):
    list_display = ("payee", "is_1099_eligible", "w9_status", "business")
    list_filter = ("is_1099_eligible", "w9_status", "business")
    search_fields = ("payee__display_name",)


@admin.register(Job)
class JobAdmin(BusinessAdminMixin):
    list_display = ("title", "year", "is_active", "business")
    list_filter = ("year", "is_active", "business")
    search_fields = ("title",)


@admin.register(Transaction)
class TransactionAdmin(BusinessAdminMixin):
    list_display = ("date", "description", "amount", "category", "subcategory", "business")
    list_filter = ("category", "business")
    search_fields = ("description", "notes", "invoice_number")
