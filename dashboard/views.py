from __future__ import annotations

import json
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import BusinessMembership
from ledger.models import Transaction, Category
from invoices.models import Invoice
from ledger.services import seed_schedule_c_defaults


def _signed_amount_expr():
    """ORM expression: refunds become negative amounts."""
    return Case(
        When(is_refund=True, then=-F("amount")),
        default=F("amount"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def _first_day_n_months_ago(anchor: date, months_back: int) -> date:
    """Return the first day of the month, `months_back` months before `anchor`'s month."""
    y, m = anchor.year, anchor.month
    for _ in range(months_back):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return date(y, m, 1)


def _period_from_params(*, today: date, mode: str, year: int | None) -> tuple[date, date, str, str]:
    """Return (start_date, end_date, label, selected_year_value)."""
    if mode == "year" and year:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        return start_date, end_date, str(year), str(year)

    # default rolling 12 months inclusive of current month
    start_date = _first_day_n_months_ago(date(today.year, today.month, 1), 11)
    end_date = today
    return start_date, end_date, "Rolling 12 months", "rolling"


def _dashboard_payload(*, business, start_date: date, end_date: date) -> dict:
    signed_amount = _signed_amount_expr()

    base_qs = Transaction.objects.filter(business=business, date__gte=start_date, date__lte=end_date)

    income_total = (
        base_qs.filter(trans_type=Transaction.TransactionType.INCOME)
        .aggregate(total=Sum(signed_amount))["total"]
        or 0
    )
    expense_total = (
        base_qs.filter(trans_type=Transaction.TransactionType.EXPENSE)
        .aggregate(total=Sum(signed_amount))["total"]
        or 0
    )
    net_total = income_total - expense_total

    chart_qs = (
        base_qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            income=Sum(
                Case(
                    When(trans_type=Transaction.TransactionType.INCOME, then=signed_amount),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            expenses=Sum(
                Case(
                    When(trans_type=Transaction.TransactionType.EXPENSE, then=signed_amount),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
        )
        .order_by("month")
    )

    labels: list[str] = []
    income_series: list[float] = []
    expense_series: list[float] = []

    for row in chart_qs:
        m = row["month"]
        if not m:
            continue
        labels.append(m.strftime("%b %Y"))
        income_series.append(float(row["income"] or 0))
        expense_series.append(float(row["expenses"] or 0))

    return {
        "income_total": float(income_total),
        "expense_total": float(expense_total),
        "net_total": float(net_total),
        "labels": labels,
        "income": income_series,
        "expenses": expense_series,
    }



def _onboarding_gate_or_redirect(request):
    business = getattr(request, "business", None)
    if business is None:
        return redirect("accounts:onboarding")

    profile = getattr(business, "company_profile", None)
    if not profile or not profile.is_complete:
        return redirect("accounts:onboarding")

    return None




@login_required
def home(request):
    print("DASHBOARD HIT", request.path, "business:", getattr(request, "business", None))

    return redirect("dashboard:dashboard_home")


@login_required
def dashboard_home(request):
    gate = _onboarding_gate_or_redirect(request)
    if gate:
        return gate

    business = getattr(request, "business", None)
    if business is None:
        messages.error(request, "No active business is set for your account.")
        return render(request, "dashboard/home.html", {})

    today = timezone.localdate()

    # Default view is rolling; year dropdown still exists for switching via AJAX.
    start_date, end_date, period_label, selected_year_value = _period_from_params(
        today=today, mode="rolling", year=None
    )

    payload = _dashboard_payload(business=business, start_date=start_date, end_date=end_date)

    # Year dropdown options (from existing transactions)
    year_dates = Transaction.objects.filter(business=business).dates("date", "year", order="DESC")
    years = [d.year for d in year_dates]

    # Recent transactions (always full business scope; independent of chart period)
    recent_transactions = (
        Transaction.objects.filter(business=business)
        .select_related("subcategory")
        .order_by("-date", "-id")[:15]
    )

    recent_invoices = (
        Invoice.objects.filter(business=business)
        .select_related("job")
        .order_by("-issue_date", "-id")[:10]
    )

    context = {
        "period_label": period_label,
        "selected_year_value": selected_year_value,
        "years": years,
        "has_seeded": Category.objects.filter(business=business).exists(),
        "can_rebuild": not Transaction.objects.filter(business=business).exists(),
        "income_total": payload["income_total"],
        "expense_total": payload["expense_total"],
        "net_total": payload["net_total"],
        "chart_labels_json": json.dumps(payload["labels"]),
        "chart_income_json": json.dumps(payload["income"]),
        "chart_expense_json": json.dumps(payload["expenses"]),
        "recent_transactions": recent_transactions,
        "recent_invoices": recent_invoices,
    }
    return render(request, "dashboard/home.html", context)


@login_required
def dashboard_chart_data(request):
    """Return chart series + KPI totals for rolling 12 months or a selected year (AJAX)."""
    gate = _onboarding_gate_or_redirect(request)
    if gate:
        return JsonResponse({"error": "onboarding_required"}, status=403)

    business = getattr(request, "business", None)
    if business is None:
        return JsonResponse({"error": "no_business"}, status=400)

    today = timezone.localdate()
    mode = (request.GET.get("mode") or "rolling").strip().lower()

    year = None
    if mode == "year":
        try:
            year = int((request.GET.get("year") or "").strip())
        except ValueError:
            year = today.year

    start_date, end_date, period_label, selected_year_value = _period_from_params(
        today=today, mode=mode, year=year
    )
    payload = _dashboard_payload(business=business, start_date=start_date, end_date=end_date)
    payload.update(
        {
            "period_label": period_label,
            "selected_year_value": selected_year_value,
        }
    )
    return JsonResponse(payload)


@login_required
@require_POST
def seed_defaults(request):
    gate = _onboarding_gate_or_redirect(request)
    if gate:
        return gate

    business = getattr(request, "business", None)
    if business is None:
        messages.error(request, "No active business is set for your account.")
        return redirect("dashboard:home")

    # Idempotent: fills in missing defaults without deleting anything.
    already_seeded = Category.objects.filter(business=business).exists()
    seed_schedule_c_defaults(business)

    if already_seeded:
        messages.success(request, "Defaults re-seeded (missing items filled in).")
    else:
        messages.success(request, "Defaults seeded successfully.")

    return redirect("dashboard:home")




@login_required
@require_POST
def rebuild_defaults(request):
    """Destructively rebuild default categories/subcategories for a business.

    Safety rule:
    - Only allowed when the business has **no transactions**.
    """
    gate = _onboarding_gate_or_redirect(request)
    if gate:
        return gate

    business = getattr(request, "business", None)
    if business is None:
        messages.error(request, "No active business is set for your account.")
        return redirect("dashboard:home")

    if Transaction.objects.filter(business=business).exists():
        messages.error(
            request,
            "Rebuild Defaults is only allowed when there are no transactions. "
            "Use Re-Seed to fill in missing defaults instead.",
        )
        return redirect("dashboard:home")

    from ledger.models import SubCategory  # local import to avoid circulars

    # Wipe + re-seed in a single transaction
    from django.db import transaction as db_transaction
    with db_transaction.atomic():
        SubCategory.objects.filter(business=business).delete()
        Category.objects.filter(business=business).delete()
        seed_schedule_c_defaults(business)

    messages.success(request, "Defaults rebuilt successfully.")
    return redirect("dashboard:home")




def _period_from_params(*, today: date, mode: str, year: int | None) -> tuple[date, date, str, str]:
    """Return (start_date, end_date, label, selected_year_value)."""

    mode = (mode or "rolling").strip().lower()

    if mode == "year" and year:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        return start_date, end_date, str(year), str(year)

    if mode == "month":
        # Current month-to-date
        start_date = date(today.year, today.month, 1)
        end_date = today
        # Label can be "Current month" or "Feb 2026" — your call.
        return start_date, end_date, "Current month", "month"

    # default rolling 12 months inclusive of current month
    start_date = _first_day_n_months_ago(date(today.year, today.month, 1), 11)
    end_date = today
    return start_date, end_date, "Rolling 12 months", "rolling"