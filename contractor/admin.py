from __future__ import annotations

from django.contrib import admin

from .models import ContractorW9Submission


@admin.register(ContractorW9Submission)
class ContractorW9SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "contact", "tin_last4", "entity_type", "submitted_at")
    list_filter = ("business", "entity_type", "tin_type", "submitted_at")
    search_fields = ("contact__display_name", "contact__email", "full_name", "business_name", "tin_last4")
    readonly_fields = ("submitted_at", "created_at", "updated_at")
