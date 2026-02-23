from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vehicles.forms import VehicleForm, VehicleMilesForm, VehicleYearForm
from vehicles.models import Vehicle, VehicleMiles, VehicleYear


def _parse_year(value: str | None) -> int:
    """Parse ?year=YYYY with a safe fallback to current year."""
    current = timezone.localdate().year
    if not value:
        return current
    try:
        y = int(value)
    except (TypeError, ValueError):
        return current
    # sanity bounds: keep it reasonable
    if y < 2000 or y > current + 1:
        return current
    return y


def _year_choices(min_year: int = 2023) -> list[int]:
    current = timezone.localdate().year
    return list(range(current, min_year - 1, -1))


def _get_transaction_model():
    """Return the Transaction model if installed, else None."""
    for app_label in ("ledger", "money"):
        try:
            return apps.get_model(app_label, "Transaction")
        except LookupError:
            continue
    return None


class VehiclesHomeView(TemplateView, LoginRequiredMixin):
    """Vehicles app dashboard at /vehicles/."""
    template_name = "vehicles/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        year = _parse_year(self.request.GET.get("year"))
        ctx["year"] = year
        ctx["year_choices"] = _year_choices()

        business = self.request.business

        vehicles_qs = Vehicle.objects.filter(business=business).order_by("-is_active", "sort_order", "label")
        ctx["vehicles"] = vehicles_qs
        ctx["vehicle_count"] = vehicles_qs.count()
        ctx["active_vehicle_count"] = vehicles_qs.filter(is_active=True).count()

        # Business miles (entered logs) for the selected year
        ytd_business_miles = (
            VehicleMiles.objects.filter(
                business=business,
                date__year=year,
                mileage_type=VehicleMiles.MileageType.BUSINESS,
            )
            .aggregate(total=Coalesce(Sum("total"), Value(Decimal("0.0"))))
            ["total"]
        )
        ctx["ytd_business_miles"] = ytd_business_miles

        # Total miles to date (estimated) = latest odometer end in year - VehicleYear.odometer_start
        # summed across vehicles that have a VehicleYear record.
        total_miles_to_date = Decimal("0.0")
        odometer_today = Decimal("0.0")

        years = {
            vy.vehicle_id: vy
            for vy in VehicleYear.objects.filter(business=business, year=year).select_related("vehicle")
        }

        # latest end per vehicle in year
        latest_ends = (
            VehicleMiles.objects.filter(business=business, date__year=year)
            .values("vehicle_id")
            .annotate(latest_end=Max("end"))
        )
        latest_by_vehicle = {row["vehicle_id"]: row["latest_end"] for row in latest_ends}

        for vehicle_id, vy in years.items():
            latest_end = latest_by_vehicle.get(vehicle_id)
            if latest_end is None:
                continue
            try:
                delta = (Decimal(str(latest_end)) - Decimal(str(vy.odometer_start))).quantize(Decimal("0.1"))
            except Exception:
                continue
            if delta < 0:
                delta = Decimal("0.0")
            total_miles_to_date += delta

        # overall odometer today = max end across all vehicles this year
        max_end = (
            VehicleMiles.objects.filter(business=business, date__year=year)
            .aggregate(v=Max("end"))["v"]
        )
        if max_end is not None:
            try:
                odometer_today = Decimal(str(max_end)).quantize(Decimal("0.1"))
            except Exception:
                odometer_today = Decimal("0.0")

        ctx["ytd_total_miles"] = total_miles_to_date
        ctx["ytd_other_miles"] = max(Decimal("0.0"), (total_miles_to_date - Decimal(str(ytd_business_miles)))).quantize(Decimal("0.1"))
        ctx["odometer_today"] = odometer_today

        # Recent mileage entries (last 5)
        ctx["recent_miles"] = (
            VehicleMiles.objects.filter(business=business, date__year=year)
            .select_related("vehicle")
            .order_by("-date", "-id")[:5]
        )

        return ctx


class VehicleListView(ListView, LoginRequiredMixin):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business).order_by("-is_active", "sort_order", "label")


class VehicleDetailView(DetailView, LoginRequiredMixin):
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
        ctx["year"] = year
        ctx["year_choices"] = _year_choices()

        # VehicleYear record (if present)
        vy = VehicleYear.objects.filter(business=business, vehicle=vehicle, year=year).first()
        ctx["vehicle_year"] = vy

        # Mileage logs for this vehicle/year
        miles_qs = (
            VehicleMiles.objects.filter(business=business, vehicle=vehicle, date__year=year)
            .select_related("job", "invoice")
            .order_by("-date", "-id")
        )
        ctx["miles_entries"] = miles_qs[:25]

        # Odometer today (latest end in year)
        latest_end = miles_qs.aggregate(v=Max("end"))["v"]
        if latest_end is None:
            odometer_today = None
            total_miles_to_date = Decimal("0.0")
        else:
            try:
                odometer_today = Decimal(str(latest_end)).quantize(Decimal("0.1"))
            except Exception:
                odometer_today = None

            total_miles_to_date = Decimal("0.0")
            if vy and odometer_today is not None:
                try:
                    total_miles_to_date = (odometer_today - Decimal(str(vy.odometer_start))).quantize(Decimal("0.1"))
                except Exception:
                    total_miles_to_date = Decimal("0.0")
                if total_miles_to_date < 0:
                    total_miles_to_date = Decimal("0.0")

        ctx["odometer_today"] = odometer_today
        ctx["total_miles_to_date"] = total_miles_to_date

        # Business miles from logs
        business_miles = (
            miles_qs.filter(mileage_type=VehicleMiles.MileageType.BUSINESS)
            .aggregate(total=Coalesce(Sum("total"), Value(Decimal("0.0"))))
            ["total"]
        )
        ctx["business_miles"] = business_miles

        # Other miles estimate
        ctx["other_miles"] = max(Decimal("0.0"), (Decimal(str(total_miles_to_date)) - Decimal(str(business_miles)))).quantize(Decimal("0.1"))

        # Transactions for this vehicle (expenses only, year filtered)
        Transaction = _get_transaction_model()
        transactions = []
        expenses_total = Decimal("0.00")

        if Transaction is not None and hasattr(Transaction, "vehicle"):
            tx_qs = Transaction.objects.filter(
                business=business,
                vehicle=vehicle,
                date__year=year,
            ).select_related("subcategory", "category", "contact", "job")

            # Show all tx in table, but compute expenses KPI on Expense type
            transactions = tx_qs.order_by("-date", "-id")[:50]

            expense_qs = tx_qs.filter(trans_type=Transaction.TransactionType.EXPENSE)
            # Net refunds out
            expenses_total = expense_qs.aggregate(
                total=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("amount") * (Value(-1) if False else Value(1)),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                    Value(Decimal("0.00")),
                )
            )["total"]
            # If you use is_refund=True to indicate reversing amounts, subtract those
            refund_total = expense_qs.filter(is_refund=True).aggregate(
                r=Coalesce(Sum("amount"), Value(Decimal("0.00")))
            )["r"]
            non_refund_total = expense_qs.filter(is_refund=False).aggregate(
                n=Coalesce(Sum("amount"), Value(Decimal("0.00")))
            )["n"]
            expenses_total = (Decimal(str(non_refund_total)) - Decimal(str(refund_total))).quantize(Decimal("0.01"))

        ctx["transactions"] = transactions
        ctx["expenses_total"] = expenses_total

        return ctx


class VehicleCreateView(CreateView, LoginRequiredMixin):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleUpdateView(UpdateView, LoginRequiredMixin):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleDeleteView(DeleteView, LoginRequiredMixin):
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


# ---------------------------------------------------------------------
# VehicleYear CRUD
# ---------------------------------------------------------------------


class VehicleYearListView(ListView, LoginRequiredMixin):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_list.html"
    context_object_name = "vehicle_years"
    paginate_by = 25

    def get_queryset(self):
        return (
            VehicleYear.objects.filter(business=self.request.business)
            .select_related("vehicle")
            .order_by("-year", "vehicle__label")
        )


class VehicleYearCreateView(CreateView, LoginRequiredMixin):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleYearUpdateView(UpdateView, LoginRequiredMixin):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business).select_related("vehicle")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleYearDeleteView(DeleteView, LoginRequiredMixin):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business)


# ---------------------------------------------------------------------
# VehicleMiles CRUD
# ---------------------------------------------------------------------


class VehicleMilesListView(ListView, LoginRequiredMixin):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_list.html"
    context_object_name = "miles_entries"
    paginate_by = 25

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
        ctx["year"] = year
        ctx["year_choices"] = _year_choices()
        ctx["vehicles"] = Vehicle.objects.filter(business=self.request.business).order_by("label")
        ctx["vehicle_filter"] = self.request.GET.get("vehicle") or ""
        return ctx


class VehicleMilesCreateView(CreateView, LoginRequiredMixin):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def get_initial(self):
        """Support pre-filling invoice/job from query params."""
        initial = super().get_initial()

        invoice_id = self.request.GET.get("invoice")
        if invoice_id:
            try:
                initial["invoice"] = int(invoice_id)
            except (TypeError, ValueError):
                pass

        job_id = self.request.GET.get("job")
        if job_id:
            try:
                initial["job"] = int(job_id)
            except (TypeError, ValueError):
                pass

        vehicle_id = self.request.GET.get("vehicle")
        if vehicle_id:
            try:
                initial["vehicle"] = int(vehicle_id)
            except (TypeError, ValueError):
                pass

        return initial

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesUpdateView(UpdateView, LoginRequiredMixin):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business).select_related("vehicle", "job", "invoice")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesDeleteView(DeleteView, LoginRequiredMixin):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business)
