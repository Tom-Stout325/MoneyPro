from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Business(models.Model):
    """Tenant model (a company/business that owns data)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "business"
            slug = base
            i = 2
            while Business.objects.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class BusinessMembership(models.Model):
    """User-to-business association with a role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "user"], name="uniq_business_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.business} ({self.role})"


class UserBusinessState(models.Model):
    """Stores per-user UI state, like the currently active business."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_state",
    )
    active_business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user} active={self.active_business_id}"


class OwnedModelMixin(models.Model):
    """Legacy ownership mixin (Phase 1): data owned by a user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class BusinessOwnedModelMixin(models.Model):
    """Tenant ownership mixin (Phase 1): data owned by a business."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE)

    class Meta:
        abstract = True
