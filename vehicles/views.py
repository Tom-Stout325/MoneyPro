from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from vehicles.forms import VehicleForm, VehicleMilesForm, VehicleYearForm
from vehicles.models import Vehicle, VehicleMiles, VehicleYear


class VehicleListView(ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business).order_by("-is_active", "sort_order", "label")


class VehicleDetailView(DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)


class VehicleCreateView(CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleUpdateView(UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        return Vehicle.objects.filter(business=self.request.business)

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleDeleteView(DeleteView):
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


class VehicleYearListView(ListView):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_list.html"
    context_object_name = "vehicle_years"
    paginate_by = 25

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business).select_related("vehicle").order_by("-year", "vehicle__label")


class VehicleYearCreateView(CreateView):
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


class VehicleYearUpdateView(UpdateView):
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


class VehicleYearDeleteView(DeleteView):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_queryset(self):
        return VehicleYear.objects.filter(business=self.request.business)


# ---------------------------------------------------------------------
# VehicleMiles CRUD
# ---------------------------------------------------------------------


class VehicleMilesListView(ListView):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_list.html"
    context_object_name = "miles_entries"
    paginate_by = 25

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business).select_related("vehicle").order_by("-date", "-id")


class VehicleMilesCreateView(CreateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesUpdateView(UpdateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business).select_related("vehicle")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        return super().form_valid(form)


class VehicleMilesDeleteView(DeleteView):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(business=self.request.business)
