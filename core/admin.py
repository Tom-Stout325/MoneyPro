from django.contrib import admin

from core.models import Business, BusinessMembership, BusinessEmailSettings, OutgoingEmailLog


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ("business", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = ("business__name", "user__email", "user__username")


@admin.register(BusinessEmailSettings)
class BusinessEmailSettingsAdmin(admin.ModelAdmin):
    list_display = ("business", "send_mode", "status_label", "from_email", "reply_to_email", "updated_at")
    list_filter = ("send_mode", "is_active", "verified_for_sending", "custom_domain_status")
    search_fields = ("business__name", "from_email", "reply_to_email", "custom_domain")
    readonly_fields = ("created_at", "updated_at", "last_verified_at")


@admin.register(OutgoingEmailLog)
class OutgoingEmailLogAdmin(admin.ModelAdmin):
    list_display = ("business", "template_type", "recipient_email", "status", "sent_at", "created_at")
    list_filter = ("template_type", "status")
    search_fields = ("business__name", "recipient_email", "subject", "from_email")
    readonly_fields = ("created_at",)
