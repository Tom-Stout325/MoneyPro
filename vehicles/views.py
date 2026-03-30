from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vehicles.forms import VehicleForm, VehicleMilesForm, VehicleYearForm
from vehicles.models import Vehicle, VehicleMiles, VehicleYear
from vehicles.queries import get_yearly_mileage_summary


ZERO_DECIMAL = Decimal("0.0")
ZERO_MONEY = Decimal("0.00")


def _parse_year(value: str | None) -> int:
    current = timezone.localdate().year
    if not value:
        return current
    try:
        y = int(value)
    except (TypeError, ValueError):
        return current
    if y < 2000 or y > current + 1:
        return current
    return y


def _year_choices(min_year: int = 2023) -> list[int]:
    current = timezone.localdate().year
    return list(range(current, min_year - 1, -1))


def _get_transaction_model():
    for app_label in ("ledger", "money"):
        try:
            return apps.get_model(app_label, "Transaction")
        except LookupError:
            continue
    return None


def _decimal(value, default: str = "0.0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _vehicle_year_summaries(*, business, year: int, vehicles_qs=None):
    vehicles_qs = vehicles_qs or Vehicle.objects.filter(business=business)
    summaries = []
    missing_setup = []
    for vehicle in vehicles_qs.order_by("sort_order", "label"):
        try:
            summaries.append(get_yearly_mileage_summary(business=business, vehicle_id=vehicle.id, year=year))
        except VehicleYear.DoesNotExist:
            missing_setup.append(vehicle)
    return summaries, missing_setup


class VehiclesHomeView(LoginRequiredMixin, TemplateView):
    template_name = "vehicles/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = _parse_year(self.request.GET.get("year"))
        business = self.request.business

        vehicles_qs = Vehicle.objects.filter(business=business).order_by("-is_active", "sort_order", "label")
        active_vehicles = vehicles_qs.filter(is_active=True)
        vehicle_years = VehicleYear.objects.filter(business=business, year=year).select_related("vehicle")
        summaries, missing_setup = _vehicle_year_summaries(business=business, year=year, vehicles_qs=active_vehicles)

        ytd_business_miles = (
            VehicleMiles.objects.filter(
                business=business,
                date__year=year,
                mileage_type=VehicleMiles.MileageType.BUSINESS,
            ).aggregate(total=Coalesce(Sum("total"), Value(ZERO_DECIMAL)))["total"]
        )

        ytd_total_miles = sum((summary.total_miles or ZERO_DECIMAL for summary in summaries), ZERO_DECIMAL)
        ytd_other_miles = max(ZERO_DECIMAL, ytd_total_miles - _decimal(ytd_business_miles)).quantize(Decimal("0.1"))

        recent_miles = (
            VehicleMiles.objects.filter(business=business, date__year=year)
            .select_related("vehicle", "job", "invoice")
            .order_by("-date", "-id")[:5]
        )

        ctx.update(
            {
                "year": year,
                "year_choices": _year_choices(),
                "vehicles": vehicles_qs,
                "vehicle_count": vehicles_qs.count(),
                "active_vehicle_count": active_vehicles.count(),
                "vehicle_year_count": vehicle_years.count(),
                "missing_vehicle_year_count": len(missing_setup),
                "recent_vehicle_years": vehicle_years.order_by("vehicle__label")[:5],
                "ytd_business_miles": _decimal(ytd_business_miles),
                "ytd_total_miles": ytd_total_miles,
                "ytd_other_miles": ytd_other_miles,
                "recent_miles": recent_miles,
                "home_summaries": summaries[:4],
            }
        )
        return ctx


class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"

    def get_queryset(self):
        qs = Vehicle.objects.filter(business=self.request.business)
        if self.request.GET.get("show_archived") != "1":
            qs = qs.filter(is_active=True)
        return qs.order_by("-is_active", "sort_order", "label")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_archived"] = self.request.GET.get("show_archived") == "1"
        ctx["year"] = _parse_year(self.request.GET.get("year"))
        return ctx


class VehicleDetailView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        business = self.request.business
        vehicle = self.object
        year = _parse_year(self.request.GET.get("year"))

        vy = VehicleYear.objects.filter(business=business, vehicle=vehicle, year=year).first()
        miles_qs = (
            VehicleMiles.objects.filter(business=business, vehicle=vehicle, date__year=year)
            .select_related("job", "invoice")
            .order_by("-date", "-id")
        )

        business_miles = miles_qs.filter(mileage_type=VehicleMiles.MileageType.BUSINESS).aggregate(
            total=Coalesce(Sum("total"), Value(ZERO_DECIMAL))
        )["total"]
        non_business_miles = miles_qs.exclude(mileage_type=VehicleMiles.MileageType.BUSINESS).aggregate(
            total=Coalesce(Sum("total"), Value(ZERO_DECIMAL))
        )["total"]
        latest_end = miles_qs.aggregate(v=Max("end"))["v"]
        odometer_today = _decimal(latest_end) if latest_end is not None else None

        total_miles_for_year = vy.total_miles if vy and vy.total_miles is not None else None
        if total_miles_for_year is None and vy and odometer_today is not None:
            total_miles_for_year = max(ZERO_DECIMAL, odometer_today - _decimal(vy.odometer_start)).quantize(Decimal("0.1"))

        other_miles = None
        if total_miles_for_year is not None:
            other_miles = max(ZERO_DECIMAL, _decimal(total_miles_for_year) - _decimal(business_miles)).quantize(Decimal("0.1"))

        Transaction = _get_transaction_model()
        transactions = []
        expenses_total = ZERO_MONEY
        if Transaction is not None and hasattr(Transaction, "vehicle"):
            tx_qs = Transaction.objects.filter(
                business=business,
                vehicle=vehicle,
                date__year=year,
            ).select_related("subcategory", "category", "contact", "job")
            transactions = tx_qs.order_by("-date", "-id")[:50]
            expense_qs = tx_qs.filter(trans_type=Transaction.TransactionType.EXPENSE)
            refund_total = expense_qs.filter(is_refund=True).aggregate(r=Coalesce(Sum("amount"), Value(ZERO_MONEY)))["r"]
            non_refund_total = expense_qs.filter(is_refund=False).aggregate(n=Coalesce(Sum("amount"), Value(ZERO_MONEY)))["n"]
            expenses_total = (_decimal(non_refund_total, "0.00") - _decimal(refund_total, "0.00")).quantize(Decimal("0.01"))

        ctx.update(
            {
                "year": year,
                "year_choices": _year_choices(),
                "vehicle_year": vy,
                "miles_entries": miles_qs[:25],
                "odometer_today": odometer_today,
                "total_miles_to_date": total_miles_for_year,
                "business_miles": _decimal(business_miles),
                "non_business_miles": _decimal(non_business_miles),
                "other_miles": other_miles,
                "transactions": transactions,
                "expenses_total": expenses_total,
            }
        )
        return ctx


class VehicleCreateView(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleDeleteView(LoginRequiredMixin, DeleteView):
    model = Vehicle
    template_name = "vehicles/vehicle_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)


@login_required
@require_POST
def vehicle_archive(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = get_object_or_404(Vehicle, pk=pk, business=request.business)
    if vehicle.is_active:
        vehicle.is_active = False
        vehicle.save(update_fields=["is_active"])
        messages.success(request, f"Archived: {vehicle.label}")
    next_url = request.POST.get("next") or "vehicles:vehicle_list"
    return redirect(next_url)


@login_required
@require_POST
def vehicle_unarchive(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = get_object_or_404(Vehicle, pk=pk, business=request.business)
    if not vehicle.is_active:
        vehicle.is_active = True
        vehicle.save(update_fields=["is_active"])
        messages.success(request, f"Unarchived: {vehicle.label}")
    next_url = request.POST.get("next") or "vehicles:vehicle_list"
    return redirect(next_url)


class VehicleYearListView(LoginRequiredMixin, ListView):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_list.html"
    context_object_name = "vehicle_years"
    paginate_by = 50

    def get_queryset(self):
        year = _parse_year(self.request.GET.get("year"))
        return (
            VehicleYear.objects.filter(business=self.request.business, year=year)
            .select_related("vehicle")
            .order_by("vehicle__label")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = _parse_year(self.request.GET.get("year"))
        active_vehicles = Vehicle.objects.filter(business=self.request.business, is_active=True)
        summaries, missing_setup = _vehicle_year_summaries(business=self.request.business, year=year, vehicles_qs=active_vehicles)
        ctx.update(
            {
                "year": year,
                "year_choices": _year_choices(),
                "rows": summaries,
                "missing_setup": missing_setup,
            }
        )
        return ctx


class VehicleYearCreateView(LoginRequiredMixin, CreateView):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("year", _parse_year(self.request.GET.get("year")))
        vehicle_id = self.request.GET.get("vehicle")
        if vehicle_id:
            try:
                initial["vehicle"] = int(vehicle_id)
            except (TypeError, ValueError):
                pass
        return initial

    def get_success_url(self):
        year = getattr(self.object, "year", None) or _parse_year(self.request.GET.get("year"))
        return f"{reverse_lazy('vehicles:vehicle_year_list')}?year={year}"

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleYearUpdateView(LoginRequiredMixin, UpdateView):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business).select_related("vehicle")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def get_success_url(self):
        return f"{reverse_lazy('vehicles:vehicle_year_list')}?year={self.object.year}"

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleYearDeleteView(LoginRequiredMixin, DeleteView):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_confirm_delete.html"

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business)

    def get_success_url(self):
        year = getattr(self.object, "year", timezone.localdate().year)
        return f"{reverse_lazy('vehicles:vehicle_year_list')}?year={year}"


class VehicleMilesListView(LoginRequiredMixin, ListView):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_list.html"
    context_object_name = "miles_entries"
    paginate_by = 50

    def get_queryset(self):
        year = _parse_year(self.request.GET.get("year"))
        qs = (
            VehicleMiles.objects.filter(business=self.request.business, date__year=year)
            .select_related("vehicle", "job", "invoice")
            .order_by("-date", "-id")
        )
        vehicle_id = self.request.GET.get("vehicle")
        if vehicle_id:
            try:
                qs = qs.filter(vehicle_id=int(vehicle_id))
            except (TypeError, ValueError):
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = _parse_year(self.request.GET.get("year"))
        entries = ctx["miles_entries"]
        business_total = entries.object_list.filter(mileage_type=VehicleMiles.MileageType.BUSINESS).aggregate(
            total=Coalesce(Sum("total"), Value(ZERO_DECIMAL))
        )["total"]
        other_total = entries.object_list.exclude(mileage_type=VehicleMiles.MileageType.BUSINESS).aggregate(
            total=Coalesce(Sum("total"), Value(ZERO_DECIMAL))
        )["total"]
        total_miles = entries.object_list.aggregate(total=Coalesce(Sum("total"), Value(ZERO_DECIMAL)))["total"]
        ctx.update(
            {
                "year": year,
                "year_choices": _year_choices(),
                "vehicles": Vehicle.objects.filter(business=self.request.business).order_by("label"),
                "vehicle_filter": self.request.GET.get("vehicle") or "",
                "business_total": _decimal(business_total),
                "other_total": _decimal(other_total),
                "total_miles": _decimal(total_miles),
            }
        )
        return ctx


class VehicleMilesCreateView(LoginRequiredMixin, CreateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        for field_name in ("invoice", "job", "vehicle"):
            value = self.request.GET.get(field_name)
            if value:
                try:
                    initial[field_name] = int(value)
                except (TypeError, ValueError):
                    pass
        return initial

    def get_success_url(self):
        year = self.object.date.year if self.object and self.object.date else _parse_year(self.request.GET.get("year"))
        return f"{reverse_lazy('vehicles:vehicle_miles_list')}?year={year}&vehicle={self.object.vehicle_id}"

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesUpdateView(LoginRequiredMixin, UpdateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business).select_related("vehicle", "job", "invoice")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def get_success_url(self):
        return f"{reverse_lazy('vehicles:vehicle_miles_list')}?year={self.object.date.year}&vehicle={self.object.vehicle_id}"

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesDeleteView(LoginRequiredMixin, DeleteView):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business)
