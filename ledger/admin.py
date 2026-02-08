# ledger/admin.py
from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet

from .models import (
    Category,
    SubCategory,
    Transaction,
    Payee,
    PayeeTaxProfile,
    Job,
)


class OwnedAdminMixin(admin.ModelAdmin):
    """
    Non-superusers can only see/edit their own rows.
    On create, auto-assign user.
    """

    def get_queryset(self, request) -> QuerySet:
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        if not change and getattr(obj, "user_id", None) is None:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return getattr(obj, "user_id", None) == request.user.id

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return getattr(obj, "user_id", None) == request.user.id

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return True
        return getattr(obj, "user_id", None) == request.user.id


@admin.register(Category)
class CategoryAdmin(OwnedAdminMixin):
    list_display = (
        "name",
        "category_type",
        "book_reports",
        "tax_reports",
        "schedule_c_line",
        "sort_order",
        "is_active",
    )
    list_filter = ("category_type", "book_reports", "tax_reports", "is_active", "schedule_c_line")
    search_fields = ("name", "slug", "report_group")
    ordering = ("category_type", "sort_order", "name")

    fields = (
        "name",
        "slug",
        "category_type",
        "sort_order",
        "book_reports",
        "tax_reports",
        "schedule_c_line",
        "report_group",
        "is_active",
    )


@admin.register(SubCategory)
class SubCategoryAdmin(OwnedAdminMixin):
    list_display = (
        "name",
        "category",
        "book_enabled",
        "tax_enabled",
        "schedule_c_line",
        "deduction_rule",
        "requires_payee",
        "payee_role",
        "requires_transport",
        "requires_vehicle",
        "is_active",
    )
    list_filter = (
        "category__category_type",
        "book_enabled",
        "tax_enabled",
        "deduction_rule",
        "requires_payee",
        "payee_role",
        "requires_transport",
        "requires_vehicle",
        "is_active",
        "is_1099_reportable_default",
        "is_capitalizable",
    )
    search_fields = ("name", "slug", "category__name")
    ordering = ("category__category_type", "category__sort_order", "sort_order", "name")
    autocomplete_fields = ("category",)

    fields = (
        "category",
        "name",
        "slug",
        "sort_order",
        "book_enabled",
        "tax_enabled",
        "schedule_c_line",
        "deduction_rule",
        "is_1099_reportable_default",
        "is_capitalizable",
        "requires_payee",
        "payee_role",
        "requires_transport",
        "requires_vehicle",
        "is_active",
    )


class PayeeTaxProfileInline(admin.StackedInline):
    model = PayeeTaxProfile
    extra = 0
    can_delete = True


@admin.register(Payee)
class PayeeAdmin(OwnedAdminMixin):
    list_display = ("display_name", "is_vendor", "is_customer", "is_contractor", "email", "phone")
    list_filter = ("is_vendor", "is_customer", "is_contractor")
    search_fields = ("display_name", "legal_name", "business_name", "email", "phone")
    ordering = ("display_name",)
    inlines = (PayeeTaxProfileInline,)

    fields = (
        "display_name",
        "legal_name",
        "business_name",
        "email",
        "phone",
        "address1",
        "address2",
        "city",
        "state",
        "zip_code",
        "country",
        "is_vendor",
        "is_customer",
        "is_contractor",
    )


@admin.register(PayeeTaxProfile)
class PayeeTaxProfileAdmin(OwnedAdminMixin):
    list_display = ("payee", "is_1099_eligible", "entity_type", "tin_type", "tin_last4", "w9_status")
    list_filter = ("is_1099_eligible", "entity_type", "tin_type", "w9_status")
    search_fields = ("payee__display_name", "payee__email", "tin_last4")
    autocomplete_fields = ("payee",)

    fields = (
        "payee",
        "is_1099_eligible",
        "entity_type",
        "tin_type",
        "tin_last4",
        "w9_status",
        "w9_document",
        "notes",
    )


@admin.register(Job)
class JobAdmin(OwnedAdminMixin):
    list_display = ("title", "year", "is_active")
    list_filter = ("year", "is_active")
    search_fields = ("title",)
    ordering = ("-year", "title")

    fields = ("title", "year", "is_active")


@admin.register(Transaction)
class TransactionAdmin(OwnedAdminMixin):
    list_display = (
        "date",
        "description",
        "amount",
        "category",
        "subcategory",
        "payee",
        "job",
        "invoice_number",
    )
    list_filter = ("category__category_type", "category", "subcategory", "payee", "job")
    search_fields = ("description", "notes", "invoice_number", "payee__display_name", "job__title", "subcategory__name")
    date_hierarchy = "date"
    ordering = ("-date", "-id")

    autocomplete_fields = ("subcategory", "payee", "job")
    readonly_fields = ("created_at", "updated_at", "category")

    fields = (
        "date",
        "amount",
        "description",
        "subcategory",
        "category",
        "payee",
        "job",
        "invoice_number",
        "transport_type",
        "notes",
        "created_at",
        "updated_at",
    )
