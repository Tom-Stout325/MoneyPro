from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML

from ledger.models import Transaction

from .models import (
    Invoice,
    InvoiceCounter,
    InvoiceItem,
    allocate_next_invoice_number,
    bump_counter_if_needed,
    next_revision_suffix,
)


def get_next_invoice_number_preview(*, business, issue_date=None) -> str:
    """Return the next numeric invoice number (YY####) WITHOUT reserving it.

    This is for UI display only (placeholder/help text). Draft-save reservation
    happens via `allocate_next_invoice_number()`.
    """
    issue_date = issue_date or timezone.localdate()
    year = issue_date.year

    counter = InvoiceCounter.objects.filter(business=business, year=year).only("last_seq").first()
    last_seq = counter.last_seq if counter else 0

    return f"{issue_date.year % 100:02d}{last_seq + 1:04d}"


def recalc_totals(*, invoice: Invoice, save: bool = False) -> tuple[Decimal, Decimal]:
    """Option A totals: compute live totals from items.

    We still set invoice.subtotal/total in-memory for templates/PDF, but callers
    can choose to persist these cached fields by passing save=True.
    """
    subtotal = invoice.subtotal_amount
    total = invoice.total_amount

    invoice.subtotal = subtotal
    invoice.total = total

    if save:
        invoice.save(update_fields=["subtotal", "total", "updated_at"])

    return subtotal, total


def snapshot_bill_to(*, invoice: Invoice) -> None:
    p = invoice.contact
    invoice.bill_to_name = getattr(p, "display_name", "") or ""
    invoice.bill_to_email = getattr(p, "email", "") or ""
    invoice.bill_to_address1 = getattr(p, "address1", "") or ""
    invoice.bill_to_address2 = getattr(p, "address2", "") or ""
    invoice.bill_to_city = getattr(p, "city", "") or ""
    invoice.bill_to_state = getattr(p, "state", "") or ""
    invoice.bill_to_postal_code = getattr(p, "zip_code", "") or ""
    invoice.bill_to_country = getattr(p, "country", "") or "US"


def ensure_number(*, invoice: Invoice) -> None:
    """Ensure invoice has a numeric YY#### number (or existing revision number).

    If the invoice already has a number, we bump the business/year counter if needed.
    If missing, allocate the next number.
    """
    if invoice.invoice_number:
        bump_counter_if_needed(
            business=invoice.business,
            issue_date=invoice.issue_date,
            invoice_number=invoice.invoice_number,
        )
        return

    invoice.invoice_number = allocate_next_invoice_number(business=invoice.business, issue_date=invoice.issue_date)
    invoice.save(update_fields=["invoice_number"])


def render_invoice_pdf_bytes(*, invoice: Invoice, base_url: str | None = None) -> bytes:
    """Render an invoice PDF from HTML using WeasyPrint.

    `base_url` is critical so WeasyPrint can resolve relative URLs for static/media.
    - For requests, pass `request.build_absolute_uri('/')`
    - For offline rendering, we fall back to BASE_DIR
    """
    company = getattr(invoice.business, "company_profile", None)

    # Ensure totals are current for rendering (Option A)
    recalc_totals(invoice=invoice, save=False)

    html = render_to_string(
        "invoices/pdf/invoice_final.html",
        {
            "invoice": invoice,
            "business": invoice.business,
            "company": company,
        },
    )

    resolved_base_url = base_url or str(settings.BASE_DIR)
    return HTML(string=html, base_url=resolved_base_url).write_pdf()


@transaction.atomic
def send_invoice(*, invoice: Invoice, base_url: str | None = None) -> None:
    if invoice.status != Invoice.Status.DRAFT:
        raise ValueError("Only draft invoices can be sent.")

    ensure_number(invoice=invoice)
    recalc_totals(invoice=invoice, save=False)
    snapshot_bill_to(invoice=invoice)

    invoice.sent_date = timezone.localdate()
    pdf_bytes = render_invoice_pdf_bytes(invoice=invoice, base_url=base_url)
    invoice.pdf_file.save(f"{invoice.invoice_number}.pdf", ContentFile(pdf_bytes), save=False)

    invoice.status = Invoice.Status.SENT
    invoice.save()


@transaction.atomic
def create_revision(*, invoice: Invoice) -> Invoice:
    if invoice.status != Invoice.Status.SENT:
        raise ValueError("Only sent invoices can be revised.")
    if not invoice.invoice_number:
        raise ValueError("Invoice must have a number to revise.")

    base = invoice.invoice_number[:6]
    suffix = next_revision_suffix(business=invoice.business, base_number=base)
    new_number = f"{base}{suffix}"

    rev = Invoice.objects.create(
        business=invoice.business,
        status=Invoice.Status.DRAFT,
        issue_date=timezone.localdate(),
        due_date=invoice.due_date,
        contact=invoice.contact,
        job=invoice.job,
        location=invoice.location,
        invoice_number=new_number,
        revises=invoice,
        memo=invoice.memo,
    )

    for it in invoice.items.all():
        InvoiceItem.objects.create(
            business=invoice.business,
            invoice=rev,
            description=it.description,
            qty=it.qty,
            unit_price=it.unit_price,
            subcategory=it.subcategory,
            sort_order=it.sort_order,
        )

    # NOTE: alpha revisions do NOT update numeric counter.
    recalc_totals(invoice=rev, save=False)
    return rev


@transaction.atomic
def mark_paid(*, invoice: Invoice, paid_date=None) -> Transaction:
    if invoice.status != Invoice.Status.SENT:
        raise ValueError("Only sent invoices can be marked paid.")
    if invoice.income_transaction_id:
        raise ValueError("This invoice is already posted to the ledger.")

    paid_date = paid_date or timezone.localdate()

    # Ensure totals current (Option A)
    _, total = recalc_totals(invoice=invoice, save=False)

    # choose posting subcategory: first line item with subcategory required
    first = invoice.items.exclude(subcategory__isnull=True).select_related("subcategory").first()
    if not first or not first.subcategory_id:
        raise ValueError("At least one line item must have a Sub Category to post income to the ledger.")

    t = Transaction.objects.create(
        business=invoice.business,
        date=paid_date,
        amount=total,
        description=f"Invoice payment {invoice.invoice_number} - {invoice.contact.display_name}",
        subcategory=first.subcategory,
        contact=invoice.contact,
        job=invoice.job,
        invoice_number=invoice.invoice_number,
        notes="Auto-generated from paid invoice.",
    )

    invoice.paid_date = paid_date
    invoice.status = Invoice.Status.PAID
    invoice.income_transaction = t
    invoice.save(update_fields=["paid_date", "status", "income_transaction"])
    return t


@transaction.atomic
def void_invoice(*, invoice: Invoice) -> None:
    if invoice.status == Invoice.Status.PAID:
        raise ValueError("Paid invoices cannot be voided.")
    invoice.status = Invoice.Status.VOID
    invoice.save(update_fields=["status"])
