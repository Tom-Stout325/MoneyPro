from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from ledger.models import Contact, Transaction

from .forms import ContractorYearForm, W9PortalForm
from .models import Contractor1099, ContractorW9Submission
from .renderer_1099nec import render_1099nec_pdf_bytes, render_1099nec_pdf_response
from .services.nec1099 import nec_total_for_contact, nec_totals_for_year, default_tax_year
from .utils_token import build_portal_url, issue_portal_token, verify_portal_token


def _current_year() -> int:
    return timezone.localdate().year


def _year_choices() -> list[int]:
    y = _current_year()
    return list(range(y - 5, y + 1))


def _get_business(request: HttpRequest):
    business = getattr(request, "business", None)
    if business is None:
        raise Http404("Business not found on request")
    return business


class ContractorListView(LoginRequiredMixin, ListView):
    template_name = "contractor/contractor_list.html"
    context_object_name = "contractors"
    paginate_by = 50
    model = Contact

    def get_queryset(self):
        business = _get_business(self.request)
        return (
            Contact.objects.filter(business=business, is_contractor=True, is_active=True)
            .order_by("display_name", "legal_name", "id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["year_form"] = ContractorYearForm(initial={"year": default_tax_year()}, year_choices=_year_choices())
        ctx["year"] = default_tax_year()
        return ctx


class ContractorDetailView(LoginRequiredMixin, DetailView):
    template_name = "contractor/contractor_detail.html"
    model = Contact
    context_object_name = "contractor"

    def get_object(self, queryset=None):
        business = _get_business(self.request)
        pk = self.kwargs.get("pk")
        return get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        business = _get_business(self.request)
        contractor: Contact = ctx["contractor"]

        year = int(self.request.GET.get("year") or default_tax_year())
        total = nec_total_for_contact(business_id=business.id, contact_id=contractor.id, year=year)

        # Linked transactions (same filter used for totals)
        tx_qs = (
            Transaction.objects.filter(
                business=business,
                contact=contractor,
                date__year=year,
                trans_type=Transaction.TransactionType.EXPENSE,
                is_refund=False,
                subcategory__is_1099_reportable_default=True,
            )
            .select_related("subcategory")
            .order_by("-date", "-id")
        )

        ctx.update(
            {
                "year": year,
                "year_form": ContractorYearForm(initial={"year": year}, year_choices=_year_choices()),
                "total_1099": total,
                "linked_transactions": tx_qs,
            }
        )

        token = issue_portal_token(business_id=business.id, contact_id=contractor.id)
        ctx["w9_portal_url"] = build_portal_url(self.request, token)
        return ctx


@login_required
def mark_w9_requested(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)

    contact.w9_status = "requested"
    contact.w9_sent_date = contact.w9_sent_date or timezone.localdate()
    contact.save(update_fields=["w9_status", "w9_sent_date"])

    messages.success(request, "W-9 marked as requested.")
    return redirect("contractor:detail", pk=contact.pk)


@login_required
def send_w9_email(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)

    if not contact.email:
        messages.error(request, "This contractor has no email address.")
        return redirect("contractor:detail", pk=contact.pk)

    token = issue_portal_token(business_id=business.id, contact_id=contact.id)
    portal_url = build_portal_url(request, token)

    subject = f"W-9 request from {business.name}"
    body = (
        f"Hi {contact.display_name},\n\n"
        f"Please complete your W-9 using the secure link below:\n{portal_url}\n\n"
        f"Thank you."
    )

    EmailMessage(subject=subject, body=body, to=[contact.email]).send(fail_silently=False)

    # Update status automatically (requested)
    contact.w9_status = "requested"
    contact.w9_sent_date = timezone.localdate()
    contact.save(update_fields=["w9_status", "w9_sent_date"])

    messages.success(request, "W-9 email sent and status set to Requested.")
    return redirect("contractor:detail", pk=contact.pk)


@login_required
def w9_view(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    return render(request, "contractor/w9_view.html", {"contractor": contact})


def w9_portal(request: HttpRequest, token: str) -> HttpResponse:
    verified = verify_portal_token(token)
    if not verified:
        raise Http404("Invalid or expired token")

    business_id = verified["business_id"]
    contact_id = verified["contact_id"]

    contact = get_object_or_404(Contact, business_id=business_id, pk=contact_id, is_contractor=True)

    if request.method == "POST":
        form = W9PortalForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data

            ContractorW9Submission.objects.create(
                business_id=business_id,
                contact=contact,
                full_name=cleaned["full_name"],
                business_name=(cleaned.get("business_name") or "").strip(),
                entity_type=(contact.entity_type or "").strip(),
                tin_type=cleaned["taxpayer_id_type"],
                tin_last4=str(cleaned["tin"])[-4:],
                address_line1=(cleaned["address1"] or "").strip(),
                address_line2=(cleaned.get("address2") or "").strip(),
                city=(cleaned.get("city") or "").strip(),
                state=(cleaned.get("state") or "").strip(),
                zip_code=(cleaned.get("zip_code") or "").strip(),
                signature_name=(cleaned.get("signature_name") or "").strip(),
                signature_data="",
                submitted_ip=request.META.get("REMOTE_ADDR") or None,
                submitted_ua=(request.META.get("HTTP_USER_AGENT") or "")[:255],
            )

            # Update Contact metadata (non-sensitive)
            contact.w9_status = "received"
            contact.w9_received_date = contact.w9_received_date or timezone.localdate()
            contact.tin_type = cleaned["taxpayer_id_type"]
            contact.tin_last4 = str(cleaned["tin"])[-4:]
            contact.is_1099_eligible = True

            # Optional sync back of basic info
            bn = (cleaned.get("business_name") or "").strip()
            if bn:
                contact.business_name = bn

            contact.address1 = (cleaned.get("address1") or "").strip()
            contact.address2 = (cleaned.get("address2") or "").strip()
            contact.city = (cleaned.get("city") or "").strip()
            contact.state = (cleaned.get("state") or "").strip()
            contact.zip_code = (cleaned.get("zip_code") or "").strip()

            contact.save()

            return render(request, "contractor/w9_thanks.html", {"contact": contact, "business": contact.business})
    else:
        form = W9PortalForm(initial={"full_name": contact.display_name or contact.legal_name})

    return render(request, "contractor/w9_portal.html", {"form": form, "contact": contact, "business": contact.business})


@login_required
def nec_1099_center(request: HttpRequest) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or default_tax_year())
    totals = nec_totals_for_year(business_id=business.id, year=year)
    return render(
        request,
        "contractor/1099_list.html",
        {
            "year": year,
            "year_form": ContractorYearForm(initial={"year": year}, year_choices=_year_choices()),
            "totals": totals,
        },
    )


@login_required
def nec_1099_preview(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or default_tax_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    total = nec_total_for_contact(business_id=business.id, contact_id=contact.id, year=year)

    return render(
        request,
        "contractor/1099-nec.html",
        {"business": business, "contractor": contact, "year": year, "amount_nonemployee_comp": total},
    )


@login_required
def nec_1099_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or default_tax_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    total = nec_total_for_contact(business_id=business.id, contact_id=contact.id, year=year)

    return render_1099nec_pdf_response(
        request=request,
        business=business,
        contractor=contact,
        year=year,
        nonemployee_comp=total,
    )


@login_required
def store_1099_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or default_tax_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)

    total = nec_total_for_contact(business_id=business.id, contact_id=contact.id, year=year)
    obj, _ = Contractor1099.objects.get_or_create(business=business, contact=contact, tax_year=year)

    # Always (re)generate on store to keep consistent with latest templates.
    b_bytes = render_1099nec_pdf_bytes(business=business, contractor=contact, year=year, nonemployee_comp=total, copy="b")
    one_bytes = render_1099nec_pdf_bytes(business=business, contractor=contact, year=year, nonemployee_comp=total, copy="1")

    obj.copy_b_pdf.save(f"1099-NEC_{year}_copyB.pdf", ContentFile(b_bytes), save=False)
    obj.copy_1_pdf.save(f"1099-NEC_{year}_copy1.pdf", ContentFile(one_bytes), save=False)
    obj.generated_at = timezone.now()
    obj.save()

    messages.success(request, f"Stored 1099 PDFs for tax year {year}.")
    return redirect("contractor:detail", pk=contact.pk)


@login_required
def email_1099_copy_b(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or default_tax_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)

    if not contact.email:
        messages.error(request, "This contractor has no email address.")
        return redirect("contractor:detail", pk=contact.pk)

    total = nec_total_for_contact(business_id=business.id, contact_id=contact.id, year=year)
    obj, _ = Contractor1099.objects.get_or_create(business=business, contact=contact, tax_year=year)

    # Ensure Copy B exists
    if not obj.copy_b_pdf:
        b_bytes = render_1099nec_pdf_bytes(business=business, contractor=contact, year=year, nonemployee_comp=total, copy="b")
        obj.copy_b_pdf.save(f"1099-NEC_{year}_copyB.pdf", ContentFile(b_bytes), save=False)

    subject = f"Your 1099-NEC for tax year {year}"
    body = f"Hi {contact.display_name},\n\nAttached is your 1099-NEC (Copy B) for tax year {year}.\n\nThank you."
    msg = EmailMessage(subject=subject, body=body, to=[contact.email])
    obj.copy_b_pdf.open('rb')
    msg.attach(filename=f"1099-NEC_{year}_copyB.pdf", content=obj.copy_b_pdf.read(), mimetype="application/pdf")
    obj.copy_b_pdf.close()
    msg.send(fail_silently=False)

    obj.emailed_at = timezone.now()
    obj.emailed_to = contact.email
    obj.email_count = (obj.email_count or 0) + 1
    obj.save(update_fields=["emailed_at", "emailed_to", "email_count", "copy_b_pdf"])

    messages.success(request, f"Emailed Copy B for tax year {year}.")
    return redirect("contractor:detail", pk=contact.pk)
