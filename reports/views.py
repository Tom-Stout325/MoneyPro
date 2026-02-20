from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from .pdf import render_pdf_from_template
from .schedule_c import build_schedule_c_lines, build_schedule_c_yoy
from .profit_loss import build_profit_loss_single, build_profit_loss_yoy

class ReportsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "reports/home.html"


@login_required
def schedule_c(request: HttpRequest) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    year_choices = list(range(2023, today.year + 1))

    business = getattr(request, "business", None)
    meals_rate = Decimal("0.50")

    mode = (request.GET.get("mode") or "tax").strip().lower()
    if mode not in {"tax", "books"}:
        mode = "tax"

    lines, grand_total = build_schedule_c_lines(
        business=business,
        year=selected_year,
        meals_rate=meals_rate,
        mode=mode,
    )

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "tax_mode": "single",
        "mode": mode,
        "selected_year": selected_year,
        "year_choices": year_choices,
        "lines": lines,
        "grand_total": grand_total,
        "meals_rate": meals_rate * Decimal("100"),
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }
    return render(request, "reports/schedule_c.html", ctx)


@login_required
def schedule_c_yoy(request: HttpRequest) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    year_choices = list(range(2023, today.year + 1))
    business = getattr(request, "business", None)
    meals_rate = Decimal("0.50")

    mode = (request.GET.get("mode") or "tax").strip().lower()
    if mode not in {"tax", "books"}:
        mode = "tax"

    years, rows, year_totals, grand_total = build_schedule_c_yoy(
        business=business,
        ending_year=selected_year,
        meals_rate=meals_rate,
        mode=mode,
    )

    ctx = {
        "tax_mode": "yoy",
        "mode": mode,
        "selected_year": selected_year,
        "year_choices": year_choices,
        "years": years,
        "lines": rows,
        "year_totals": year_totals,
        "grand_total": grand_total,
        "meals_rate": meals_rate * Decimal("100"),
    }
    return render(request, "reports/schedule_c_yoy.html", ctx)


@login_required
def schedule_c_pdf_preview(request: HttpRequest) -> HttpResponse:
    return _schedule_c_pdf(request, download=False)


@login_required
def schedule_c_pdf_download(request: HttpRequest) -> HttpResponse:
    return _schedule_c_pdf(request, download=True)


@login_required
def schedule_c_yoy_pdf_preview(request: HttpRequest) -> HttpResponse:
    return _schedule_c_yoy_pdf(request, download=False)


@login_required
def schedule_c_yoy_pdf_download(request: HttpRequest) -> HttpResponse:
    return _schedule_c_yoy_pdf(request, download=True)


def _schedule_c_pdf(request: HttpRequest, *, download: bool) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    # Optional metadata line: ?prepared=1
    show_prepared_by = (request.GET.get("prepared") or "").strip() in {"1", "true", "yes", "on"}

    mode = (request.GET.get("mode") or "tax").strip().lower()
    if mode not in {"tax", "books"}:
        mode = "tax"

    business = getattr(request, "business", None)
    meals_rate = Decimal("0.50")
    lines, grand_total = build_schedule_c_lines(
        business=business,
        year=selected_year,
        meals_rate=meals_rate,
        mode=mode,
    )

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "selected_year": selected_year,
        "lines": lines,
        "grand_total": grand_total,
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
        "show_prepared_by": show_prepared_by,
        "mode": mode,
    }

    result = render_pdf_from_template(
        request=request,
        template_name="reports/pdf/schedule_c_pdf.html",
        context=ctx,
        filename=f"operating-expenses-{selected_year}.pdf",
        download=download,
    )
    return result.response


def _schedule_c_yoy_pdf(request: HttpRequest, *, download: bool) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    show_prepared_by = (request.GET.get("prepared") or "").strip() in {"1", "true", "yes", "on"}
    mode = (request.GET.get("mode") or "tax").strip().lower()
    if mode not in {"tax", "books"}:
        mode = "tax"

    business = getattr(request, "business", None)
    meals_rate = Decimal("0.50")

    years, rows, year_totals, grand_total = build_schedule_c_yoy(
        business=business,
        ending_year=selected_year,
        meals_rate=meals_rate,
        mode=mode,
    )

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    # Logo: make absolute if needed
    logo_src = None
    if company_profile and getattr(company_profile, "logo", None):
        try:
            url = company_profile.logo.url
            if url and url.startswith("/"):
                logo_src = request.build_absolute_uri(url)
            else:
                logo_src = url
        except Exception:
            logo_src = None

    y2, y1, y0 = years
    pdf_rows = [
        {
            "category_label": r.category_label,
            "t2": r.totals.get(y2),
            "t1": r.totals.get(y1),
            "t0": r.totals.get(y0),
        }
        for r in rows
    ]

    ctx = {
        "selected_year": selected_year,
        "y2": y2,
        "y1": y1,
        "y0": y0,
        "rows": pdf_rows,
        "grand_total": grand_total,
        "logo_src": logo_src,
        "show_prepared_by": show_prepared_by,
        "mode": mode,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }

    result = render_pdf_from_template(
        request=request,
        template_name="reports/pdf/schedule_c_yoy_pdf.html",
        context=ctx,
        filename=f"operating-expenses-yoy-{selected_year}.pdf",
        download=download,
    )
    return result.response




@login_required
def profit_loss(request: HttpRequest) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    year_choices = list(range(2023, today.year + 1))
    business = getattr(request, "business", None)

    pl = build_profit_loss_single(business=business, year=selected_year)

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "view_mode": "single",
        "selected_year": selected_year,
        "year_choices": year_choices,
        "pl": pl,
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }
    return render(request, "reports/profit_loss.html", ctx)


@login_required
def profit_loss_yoy(request: HttpRequest) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    year_choices = list(range(2023, today.year + 1))
    business = getattr(request, "business", None)

    yoy = build_profit_loss_yoy(business=business, ending_year=selected_year, years=3)

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "view_mode": "yoy",
        "selected_year": selected_year,
        "year_choices": year_choices,
        "yoy": yoy,
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }
    return render(request, "reports/profit_loss_yoy.html", ctx)


@login_required
def profit_loss_pdf_preview(request: HttpRequest) -> HttpResponse:
    return _profit_loss_pdf(request, download=False)


@login_required
def profit_loss_pdf_download(request: HttpRequest) -> HttpResponse:
    return _profit_loss_pdf(request, download=True)


def _profit_loss_pdf(request: HttpRequest, *, download: bool) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    business = getattr(request, "business", None)
    pl = build_profit_loss_single(business=business, year=selected_year)

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "selected_year": selected_year,
        "pl": pl,
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }

    result = render_pdf_from_template(
        request=request,
        template_name="reports/pdf/profit_loss_pdf.html",
        context=ctx,
        filename=f"profit-loss-{selected_year}.pdf",
        download=download,
    )
    return result.response


@login_required
def profit_loss_yoy_pdf_preview(request: HttpRequest) -> HttpResponse:
    return _profit_loss_yoy_pdf(request, download=False)


@login_required
def profit_loss_yoy_pdf_download(request: HttpRequest) -> HttpResponse:
    return _profit_loss_yoy_pdf(request, download=True)


def _profit_loss_yoy_pdf(request: HttpRequest, *, download: bool) -> HttpResponse:
    today = date.today()
    try:
        selected_year = int(request.GET.get("year") or today.year)
    except ValueError:
        selected_year = today.year

    business = getattr(request, "business", None)
    yoy = build_profit_loss_yoy(business=business, ending_year=selected_year, years=3)

    company_profile = getattr(business, "company_profile", None)
    company_name = None
    if company_profile and getattr(company_profile, "company_name", None):
        company_name = company_profile.company_name

    ctx = {
        "selected_year": selected_year,
        "yoy": yoy,
        "business": business,
        "company_profile": company_profile,
        "company_name": company_name or getattr(business, "name", ""),
    }

    result = render_pdf_from_template(
        request=request,
        template_name="reports/pdf/profit_loss_yoy_pdf.html",
        context=ctx,
        filename=f"profit-loss-yoy-{yoy.years[0]}-{yoy.years[-1]}.pdf",
        download=download,
    )
    return result.response
