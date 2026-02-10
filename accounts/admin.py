# accounts/admin.py 
from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.core.mail import send_mail
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect

from .models import CompanyProfile, Invitation


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



@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "invited_by",
        "created_at",
        "expires_at",
        "accepted_at",
        "is_used",
        "is_expired",
    )
    list_filter = ("accepted_at",)
    search_fields = ("email", "invited_by__email", "invited_by__username")
    readonly_fields = ("token", "created_at", "accepted_at", "accepted_user")

    actions = ["send_invite_email"]

    change_form_template = "admin/accounts/invitation/change_form.html"


    @admin.action(description="Send invite email")
    def send_invite_email(self, request, queryset):
        sent = 0
        renewed = 0

        for inv in queryset:
            inv_to_send = inv
            if inv.is_expired or inv.is_used:
                inv_to_send = Invitation.objects.create(email=inv.email, invited_by=inv.invited_by)
                renewed += 1

            self._send_invite(request, inv_to_send)
            sent += 1

        messages.success(
            request,
            f"Sent {sent} invite email(s)."
            + (f" ({renewed} renewed)" if renewed else ""),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/resend/",
                self.admin_site.admin_view(self.resend_invite_view),
                name="accounts_invitation_resend",
            ),
        ]
        return custom + urls

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj and obj.pk:
            context["resend_invite_url"] = reverse("admin:accounts_invitation_resend", args=[obj.pk])
            # Always show button; it will renew if needed.
            context["show_resend_invite"] = True
            context["resend_invite_label"] = "Resend invite"
        return super().render_change_form(request, context, add, change, form_url, obj)

    def resend_invite_view(self, request, object_id):
        inv = get_object_or_404(Invitation, pk=object_id)

        # If expired OR used, auto-renew (create a fresh invite) and send that.
        inv_to_send = inv
        renewed = False

        if inv.is_expired or inv.is_used:
            inv_to_send = Invitation.objects.create(email=inv.email, invited_by=inv.invited_by)
            renewed = True

        self._send_invite(request, inv_to_send)

        if renewed:
            messages.success(request, f"Invite was renewed and sent to {inv_to_send.email}.")
            return redirect(reverse("admin:accounts_invitation_change", args=[inv_to_send.pk]))

        messages.success(request, f"Invite re-sent to {inv_to_send.email}.")
        return redirect("../")

    def _send_invite(self, request, inv: Invitation) -> None:
        invite_url = request.build_absolute_uri(
            reverse("accounts:invite_start", args=[inv.token])
        )

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "webmaster@localhost"

        send_mail(
            subject="You're invited to MoneyPro",
            message=(
                "Use this link to create your account:\n\n"
                f"{invite_url}\n\n"
                f"This link expires on {inv.expires_at:%b %d, %Y}."
            ),
            from_email=from_email,
            recipient_list=[inv.email],
        )