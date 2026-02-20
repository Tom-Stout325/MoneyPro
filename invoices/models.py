from __future__ import annotations

import re
import string
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from core.models import BusinessOwnedModelMixin
from ledger.models import Job, Contact, SubCategory, Transaction


INVOICE_NO_RE = re.compile(r"^(?P<num>\d{6})(?P<suffix>[a-z])?$")


class InvoiceCounter(BusinessOwnedModelMixin):
    """Tracks last numeric invoice sequence per business+year (YY####)."""

    year = models.PositiveIntegerField()
    last_seq = models.PositiveIntegerField(default=0)  # 0 => next is 1

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "year"], name="uniq_invoice_counter_business_year"),
        ]

    def __str__(self) -> str:
        return f"{self.business} {self.year}: {self.last_seq}"


class Invoice(BusinessOwnedModelMixin):
    class Status(models.TextChoices):
        DRAFT = "draft", "Invoice created"
        SENT = "sent", "Invoice sent"
        PAID = "paid", "Invoice paid"
        VOID = "void", "Voided"

    status         = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    issue_date     = models.DateField(default=timezone.localdate)
    due_date       = models.DateField(null=True, blank=True)
    sent_date      = models.DateField(null=True, blank=True)
    paid_date      = models.DateField(null=True, blank=True)
    contact        = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="invoices")
    job            = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="invoices", null=True, blank=True)
    location       = models.CharField(max_length=255, blank=True)
    invoice_number = models.CharField(max_length=12, blank=True)  # YY#### or YY####a
    revises        = models.ForeignKey("self", on_delete=models.PROTECT, related_name="revisions", null=True, blank=True, help_text="If set, this invoice is a revision of another invoice.",)

    # Snapshot fields (frozen at SEND)
    bill_to_name        = models.CharField(max_length=255, blank=True)
    bill_to_email       = models.EmailField(blank=True)
    bill_to_address1    = models.CharField(max_length=255, blank=True)
    bill_to_address2    = models.CharField(max_length=255, blank=True)
    bill_to_city        = models.CharField(max_length=120, blank=True)
    bill_to_state       = models.CharField(max_length=50, blank=True)
    bill_to_postal_code = models.CharField(max_length=20, blank=True)
    bill_to_country     = models.CharField(max_length=50, blank=True, default="US")

    memo                = models.TextField(blank=True)
    subtotal            = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total               = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    pdf_file            = models.FileField(upload_to="invoices/final/", blank=True, null=True)

    income_transaction  = models.OneToOneField(Transaction, on_delete=models.SET_NULL, related_name="invoice_income_for", null=True, blank=True,)

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["business", "invoice_number"], name="uniq_invoice_number_per_business"),
        ]

    def __str__(self) -> str:
        return self.invoice_number or f"Invoice #{self.pk}"

    def clean(self):
        super().clean()

        if self.contact_id and self.business_id and self.contact.business_id != self.business_id:
            raise ValidationError({"contact": "Contact does not belong to this business."})
        if self.job_id and self.business_id and self.job.business_id != self.business_id:
            raise ValidationError({"job": "Job does not belong to this business."})

        if self.invoice_number:
            m = INVOICE_NO_RE.match(self.invoice_number)
            if not m:
                raise ValidationError({"invoice_number": "Invoice number must be YY#### (e.g., 260001) optionally with a suffix (e.g., 260001a)."})


class InvoiceItem(BusinessOwnedModelMixin):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")

    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    subcategory = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name="invoice_items", null=True, blank=True)

    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id and self.invoice.business_id != self.business_id:
            raise ValidationError("InvoiceItem business must match Invoice business.")
        if self.subcategory_id and self.business_id and self.subcategory.business_id != self.business_id:
            raise ValidationError({"subcategory": "Subcategory does not belong to this business."})

    def save(self, *args, **kwargs):
        self.line_total = (self.qty or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
        self.full_clean()
        return super().save(*args, **kwargs)




class InvoicePayment(BusinessOwnedModelMixin):
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    date        = models.DateField(default=timezone.localdate)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "id"]

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id and self.invoice.business_id != self.business_id:
            raise ValidationError("Payment business must match Invoice business.")
        if self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be greater than 0."})


# -------------------------
# Numbering + helpers
# -------------------------

def _year_prefix(issue_date) -> str:
    return f"{issue_date.year % 100:02d}"


def _format_invoice_number(issue_date, seq: int) -> str:
    return f"{_year_prefix(issue_date)}{seq:04d}"


def _numeric_part(invoice_number: str) -> int:
    m = INVOICE_NO_RE.match(invoice_number or "")
    if not m:
        return 0
    return int(m.group("num"))


def allocate_next_invoice_number(*, business, issue_date) -> str:
    """Allocate next numeric invoice number (no alpha suffix) safely."""
    year = issue_date.year
    with transaction.atomic():
        counter, _ = (
            InvoiceCounter.objects.select_for_update()
            .get_or_create(business=business, year=year, defaults={"last_seq": 0})
        )
        counter.last_seq += 1
        counter.save(update_fields=["last_seq"])
        return _format_invoice_number(issue_date, counter.last_seq)


def validate_manual_invoice_number(*, business, issue_date, invoice_number: str) -> None:
    """
    Manual override must be numeric YY#### (no alpha) and strictly higher than current max for that year.
    """
    m = INVOICE_NO_RE.match(invoice_number or "")
    if not m or m.group("suffix"):
        raise ValidationError({"invoice_number": "Manual invoice number must be numeric YY#### (no alpha)."})

    year_prefix = _year_prefix(issue_date)
    if not invoice_number.startswith(year_prefix):
        raise ValidationError({"invoice_number": f"Invoice number must start with {year_prefix} for the invoice year."})

    year = issue_date.year
    max_used = (
        Invoice.objects.filter(business=business, issue_date__year=year)
        .exclude(invoice_number__regex=r"[a-z]$")
        .aggregate(mx=models.Max("invoice_number"))["mx"]
    )
    if max_used and _numeric_part(invoice_number) <= _numeric_part(max_used):
        raise ValidationError({"invoice_number": f"Manual invoice number must be higher than {max_used}."})


def bump_counter_if_needed(*, business, issue_date, invoice_number: str) -> None:
    """If manual number used, ensure counter follows max."""
    year = issue_date.year
    numeric = _numeric_part(invoice_number)
    seq = numeric % 10000
    with transaction.atomic():
        counter, _ = (
            InvoiceCounter.objects.select_for_update()
            .get_or_create(business=business, year=year, defaults={"last_seq": 0})
        )
        if seq > counter.last_seq:
            counter.last_seq = seq
            counter.save(update_fields=["last_seq"])


def next_revision_suffix(*, business, base_number: str) -> str:
    existing = set(
        Invoice.objects.filter(business=business, invoice_number__startswith=base_number)
        .values_list("invoice_number", flat=True)
    )
    for letter in string.ascii_lowercase:
        candidate = f"{base_number}{letter}"
        if candidate not in existing:
            return letter
    raise ValidationError("Too many revisions for this invoice number.")
