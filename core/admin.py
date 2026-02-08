from django.contrib import admin

from core.models import Business, BusinessMembership, UserBusinessState


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


@admin.register(UserBusinessState)
class UserBusinessStateAdmin(admin.ModelAdmin):
    list_display = ("user", "active_business")
    search_fields = ("user__email", "user__username", "active_business__name")
