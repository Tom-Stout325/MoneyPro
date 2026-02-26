from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from ledger.models import Contact, ContactTaxProfile, Transaction

from .forms import ContractorYearForm, W9PortalForm
from .models import ContractorW9Submission
from .renderer_1099nec import render_1099nec_pdf_response
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


def _contractor_total_for_year(*, business, contact: Contact, year: int) -> Decimal:
    total = (
        Transaction.objects.filter(
            business=business,
            contact=contact,
            date__year=year,
            trans_type="expense",
            is_refund=False,
            subcategory__is_1099_reportable_default=True,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0.00")
    )
    return total


class ContractorListView(LoginRequiredMixin, ListView):
    template_name = "contractor/contractor_list.html"
    context_object_name = "contractors"
    paginate_by = 50
    model = Contact  # IMPORTANT: gives ListView a base queryset

    def get_queryset(self):
        business = _get_business(self.request)
        return (
            Contact.objects.filter(business=business, is_contractor=True)
            .select_related("tax_profile")
            .order_by("display_name", "legal_name", "id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["year_form"] = ContractorYearForm(initial={"year": _current_year()}, year_choices=_year_choices())
        ctx["year"] = _current_year()
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

        year = int(self.request.GET.get("year") or _current_year())
        total = _contractor_total_for_year(business=business, contact=contractor, year=year)

        tax_profile = getattr(contractor, "tax_profile", None)
        if tax_profile is None:
            tax_profile = ContactTaxProfile.objects.create(business=business, contact=contractor)

        ctx.update(
            {
                "year": year,
                "year_form": ContractorYearForm(initial={"year": year}, year_choices=_year_choices()),
                "total_1099": total,
                "tax_profile": tax_profile,
            }
        )

        token = issue_portal_token(business_id=business.id, contact_id=contractor.id)
        ctx["w9_portal_url"] = build_portal_url(self.request, token)

        return ctx


@login_required
def mark_w9_requested(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)

    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    tax_profile = getattr(contact, "tax_profile", None)
    if tax_profile is None:
        tax_profile = ContactTaxProfile.objects.create(business=business, contact=contact)

    tax_profile.w9_status = "requested"
    tax_profile.save(update_fields=["w9_status"])
    messages.success(request, "W-9 marked as requested.")
    return redirect("contractor:detail", pk=contact.pk)


def w9_portal(request: HttpRequest, token: str) -> HttpResponse:
    verified = verify_portal_token(token)
    if not verified:
        raise Http404("Invalid or expired token")

    business_id = verified["business_id"]
    contact_id = verified["contact_id"]

    contact = get_object_or_404(Contact, business_id=business_id, pk=contact_id, is_contractor=True)

    tax_profile = getattr(contact, "tax_profile", None)
    if tax_profile is None:
        tax_profile = ContactTaxProfile.objects.create(business_id=business_id, contact=contact)

    if request.method == "POST":
        form = W9PortalForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data

            ContractorW9Submission.objects.create(
                business_id=business_id,
                contact=contact,
                full_name=cleaned["full_name"],
                business_name=cleaned.get("business_name") or "",
                address1=cleaned["address1"],
                address2=cleaned.get("address2") or "",
                city=cleaned["city"],
                state=cleaned["state"],
                zip_code=cleaned["zip_code"],
                taxpayer_id_type=cleaned["taxpayer_id_type"],
                tin_last4=str(cleaned["tin"])[-4:],
                signature_name=cleaned["signature_name"],
                signature_date=cleaned["signature_date"],
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            tax_profile.w9_status = "received"
            tax_profile.tin_last4 = str(cleaned["tin"])[-4:]
            tax_profile.is_1099_eligible = True
            tax_profile.save(update_fields=["w9_status", "tin_last4", "is_1099_eligible"])

            return render(request, "contractor/w9_thanks.html", {"contact": contact, "business": contact.business})
    else:
        form = W9PortalForm(initial={"full_name": contact.display_name or contact.legal_name})

    return render(request, "contractor/w9_portal.html", {"form": form, "contact": contact, "business": contact.business})


@login_required
def nec_1099_center(request: HttpRequest) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or _current_year())

    contractors = (
        Contact.objects.filter(business=business, is_contractor=True, tax_profile__is_1099_eligible=True)
        .select_related("tax_profile")
        .order_by("display_name", "legal_name", "id")
    )

    rows = [{"contact": c, "total": _contractor_total_for_year(business=business, contact=c, year=year)} for c in contractors]

    return render(
        request,
        "contractor/nec_1099_center.html",
        {"year": year, "year_form": ContractorYearForm(initial={"year": year}, year_choices=_year_choices()), "rows": rows},
    )


@login_required
def nec_1099_preview(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or _current_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    total = _contractor_total_for_year(business=business, contact=contact, year=year)

    return render(
        request,
        "contractor/1099-nec.html",
        {"business": business, "contractor": contact, "year": year, "amount_nonemployee_comp": total},
    )


@login_required
def nec_1099_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    business = _get_business(request)
    year = int(request.GET.get("year") or _current_year())
    contact = get_object_or_404(Contact, business=business, pk=pk, is_contractor=True)
    total = _contractor_total_for_year(business=business, contact=contact, year=year)

    return render_1099nec_pdf_response(
        request=request,
        business=business,
        contractor=contact,
        year=year,
        nonemployee_comp=total,
    )
