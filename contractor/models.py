from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import BusinessOwnedModelMixin
from ledger.models import Contact


class ContractorW9Submission(BusinessOwnedModelMixin):
    """Audit record of a W-9 submission via the public portal.

    Security note:
    - We intentionally do NOT store full TIN long-term. We store last4 only.
    """

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="w9_submissions")

    # Audit timestamps (migration 0001 already includes these fields)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Core W-9 fields
    full_name = models.CharField(max_length=255)
    business_name = models.CharField(max_length=255, blank=True)
    entity_type = models.CharField(max_length=25, blank=True)
    tin_type = models.CharField(max_length=10, blank=True)
    tin_last4 = models.CharField(max_length=4, blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)

    signature_name = models.CharField(max_length=255, blank=True)
    signature_data = models.TextField(blank=True)  # base64 png from signature pad (optional)

    submitted_ip = models.GenericIPAddressField(null=True, blank=True)
    submitted_ua = models.CharField(max_length=255, blank=True)

    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["business", "contact"], name="ctr_w9_bus_contact_idx"),
        ]

    def __str__(self) -> str:
        return f"W-9 submission for {self.contact} on {self.submitted_at:%Y-%m-%d}"
