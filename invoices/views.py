from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import inlineformset_factory
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from .forms import InvoiceForm, InvoiceItemForm
from .models import Invoice, InvoiceItem, allocate_next_invoice_number, bump_counter_if_needed
from .services import (
    create_revision,
    mark_paid,
    recalc_totals,
    render_invoice_pdf_bytes,
    send_invoice,
    void_invoice,
)


class BusinessScopedMixin:
    def get_business(self):
        b = getattr(self.request, "business", None)
        if not b:
            raise Http404("No active business.")
        return b


class InvoiceListView(LoginRequiredMixin, BusinessScopedMixin, ListView):
    model = Invoice
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        return (
            Invoice.objects.filter(business=self.get_business())
            .select_related("contact", "job")
            .order_by("-issue_date", "-id")
        )


class InvoiceDetailView(LoginRequiredMixin, BusinessScopedMixin, DetailView):
    model = Invoice
    template_name = "invoices/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return (
            Invoice.objects.filter(business=self.get_business())
            .select_related("contact", "job", "income_transaction")
            .prefetch_related("items")
        )


def _get_item_formset(*, business):
    return inlineformset_factory(
        Invoice,
        InvoiceItem,
        form=InvoiceItemForm,
        fields=["description", "subcategory", "qty", "unit_price", "sort_order"],
        extra=0,
        can_delete=True,
    )


@login_required
def invoice_create(request: HttpRequest) -> HttpResponse:
    business = request.business
    invoice = Invoice(business=business)

    ItemFormSet = _get_item_formset(business=business)

    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, business=business)
        formset = ItemFormSet(request.POST, instance=invoice, prefix="items", form_kwargs={"business": business})

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.business = business
            invoice.status = Invoice.Status.DRAFT

            entered = (form.cleaned_data.get("invoice_number") or "").strip()
            if entered:
                # Manual number already validated by InvoiceForm.clean_invoice_number()
                invoice.invoice_number = entered
                bump_counter_if_needed(
                    business=business,
                    issue_date=invoice.issue_date,
                    invoice_number=invoice.invoice_number,
                )
            else:
                # Reserve next number on draft save
                invoice.invoice_number = allocate_next_invoice_number(business=business, issue_date=invoice.issue_date)

            invoice.save()

            items = formset.save(commit=False)
            for it in items:
                it.business = business
                it.invoice = invoice
                it.save()
            for it in formset.deleted_objects:
                it.delete()

            recalc_totals(invoice=invoice, save=True)

            messages.success(request, "Invoice created.")
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        messages.error(request, "Please fix the errors below.")
    else:
        form = InvoiceForm(instance=invoice, business=business)
        formset = ItemFormSet(instance=invoice, prefix="items", form_kwargs={"business": business})

    return render(
        request,
        "invoices/invoice_form.html",
        {"form": form, "formset": formset, "invoice": None},
    )


@login_required
def invoice_update(request: HttpRequest, pk: int) -> HttpResponse:
    business = request.business
    invoice = get_object_or_404(Invoice, business=business, pk=pk)

    if invoice.status != Invoice.Status.DRAFT:
        messages.error(request, "This invoice is locked and cannot be edited.")
        return redirect("invoices:invoice_detail", pk=invoice.pk)

    ItemFormSet = _get_item_formset(business=business)

    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, business=business)
        formset = ItemFormSet(request.POST, instance=invoice, prefix="items", form_kwargs={"business": business})

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.business = business

            entered = (form.cleaned_data.get("invoice_number") or "").strip()
            if entered:
                invoice.invoice_number = entered
                bump_counter_if_needed(
                    business=business,
                    issue_date=invoice.issue_date,
                    invoice_number=invoice.invoice_number,
                )
            else:
                # Do not allow clearing an existing reserved number
                if not invoice.invoice_number:
                    invoice.invoice_number = allocate_next_invoice_number(business=business, issue_date=invoice.issue_date)

            invoice.save()

            items = formset.save(commit=False)
            for it in items:
                it.business = business
                it.invoice = invoice
                it.save()
            for it in formset.deleted_objects:
                it.delete()

            recalc_totals(invoice=invoice, save=True)

            messages.success(request, "Invoice updated.")
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        messages.error(request, "Please fix the errors below.")
    else:
        form = InvoiceForm(instance=invoice, business=business)
        formset = ItemFormSet(instance=invoice, prefix="items", form_kwargs={"business": business})

    return render(
        request,
        "invoices/invoice_form.html",
        {"form": form, "formset": formset, "invoice": invoice},
    )


@login_required
def invoice_send(request: HttpRequest, pk: int) -> HttpResponse:
    invoice = get_object_or_404(Invoice, business=request.business, pk=pk)
    if request.method != "POST":
        return redirect("invoices:invoice_detail", pk=invoice.pk)

    try:
        send_invoice(invoice=invoice, base_url=request.build_absolute_uri("/"))
        messages.success(request, "Invoice sent (PDF frozen).")
    except Exception as e:
        messages.error(request, f"Could not send invoice: {e}")
    return redirect("invoices:invoice_detail", pk=invoice.pk)


@login_required
def invoice_mark_paid(request: HttpRequest, pk: int) -> HttpResponse:
    invoice = get_object_or_404(Invoice, business=request.business, pk=pk)
    if request.method != "POST":
        return redirect("invoices:invoice_detail", pk=invoice.pk)

    try:
        mark_paid(invoice=invoice)
        messages.success(request, "Invoice marked as paid and income transaction recorded.")
    except Exception as e:
        messages.error(request, f"Could not mark as paid: {e}")
    return redirect("invoices:invoice_detail", pk=invoice.pk)


@login_required
def invoice_void(request: HttpRequest, pk: int) -> HttpResponse:
    invoice = get_object_or_404(Invoice, business=request.business, pk=pk)
    if request.method != "POST":
        return redirect("invoices:invoice_detail", pk=invoice.pk)

    try:
        void_invoice(invoice=invoice)
        messages.success(request, "Invoice voided.")
    except Exception as e:
        messages.error(request, f"Could not void invoice: {e}")
    return redirect("invoices:invoice_detail", pk=invoice.pk)


@login_required
def invoice_revise(request: HttpRequest, pk: int) -> HttpResponse:
    invoice = get_object_or_404(Invoice, business=request.business, pk=pk)
    if request.method != "POST":
        return redirect("invoices:invoice_detail", pk=invoice.pk)

    try:
        rev = create_revision(invoice=invoice)
        messages.success(request, f"Revision created: {rev.invoice_number}")
        return redirect("invoices:invoice_update", pk=rev.pk)
    except Exception as e:
        messages.error(request, f"Could not create revision: {e}")
        return redirect("invoices:invoice_detail", pk=invoice.pk)


# -----------------------------------------------------------------------------
# PDF preview/download
# -----------------------------------------------------------------------------


def _invoice_pdf_fileresponse(*, invoice: Invoice, inline: bool) -> FileResponse:
    """Serve the stored PDF file field."""
    filename = f"{invoice.invoice_number or 'invoice'}.pdf"
    resp = FileResponse(invoice.pdf_file.open("rb"), content_type="application/pdf")
    disp = "inline" if inline else "attachment"
    resp["Content-Disposition"] = f'{disp}; filename="{filename}"'
    return resp


@login_required
def invoice_pdf_preview(request: HttpRequest, pk: int) -> HttpResponse:
    """Inline PDF preview.

    - If a frozen PDF exists (sent/paid), serve it.
    - Otherwise render on-demand via WeasyPrint.
    """
    invoice = get_object_or_404(
        Invoice.objects.filter(business=request.business)
        .select_related("contact", "job")
        .prefetch_related("items"),
        pk=pk,
    )

    if invoice.pdf_file:
        return _invoice_pdf_fileresponse(invoice=invoice, inline=True)

    pdf_bytes = render_invoice_pdf_bytes(invoice=invoice, base_url=request.build_absolute_uri("/"))
    filename = f"{invoice.invoice_number or 'invoice'}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


@login_required
def invoice_pdf_download(request: HttpRequest, pk: int) -> HttpResponse:
    """Download PDF.

    - If a frozen PDF exists, serve it as attachment.
    - Otherwise render on-demand and download.
    """
    invoice = get_object_or_404(
        Invoice.objects.filter(business=request.business)
        .select_related("contact", "job")
        .prefetch_related("items"),
        pk=pk,
    )

    if invoice.pdf_file:
        return _invoice_pdf_fileresponse(invoice=invoice, inline=False)

    pdf_bytes = render_invoice_pdf_bytes(invoice=invoice, base_url=request.build_absolute_uri("/"))
    filename = f"{invoice.invoice_number or 'invoice'}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
