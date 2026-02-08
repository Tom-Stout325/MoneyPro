from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from vehicles.models import VehicleMiles, VehicleYear, Vehicle
from vehicles.forms import VehicleForm, VehicleMilesForm, VehicleYearForm









class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"

    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user).order_by("-is_active", "sort_order", "label")


class VehicleDetailView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)


class VehicleCreateView(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)



@login_required
@require_POST
def vehicle_archive(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    if vehicle.is_active:
        vehicle.is_active = False
        vehicle.save(update_fields=["is_active"])
        messages.success(request, f"Archived: {vehicle.label}")

    next_url = request.POST.get("next") or "vehicles:vehicle_list"
    return redirect(next_url)


@login_required
@require_POST
def vehicle_unarchive(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    if not vehicle.is_active:
        vehicle.is_active = True
        vehicle.save(update_fields=["is_active"])
        messages.success(request, f"Unarchived: {vehicle.label}")

    next_url = request.POST.get("next") or "vehicles:vehicle_list"
    return redirect(next_url)



class VehicleDeleteView(UserPassesTestMixin, DeleteView):
    model = Vehicle
    success_url = reverse_lazy("vehicles:vehicle_list")

    def get_queryset(self):
        # user must own the vehicle
        return Vehicle.objects.filter(user=self.request.user)

    def test_func(self):
        # admin only
        return self.request.user.is_staff
    
    
    
    
    
# -------------------------
# VehicleYear CRUD
# -------------------------

class VehicleYearListView(LoginRequiredMixin, ListView):
    model = VehicleYear
    template_name = "vehicles/vehicle_year_list.html"
    context_object_name = "rows"

    def get_queryset(self):
        return (
            VehicleYear.objects.filter(user=self.request.user)
            .select_related("vehicle")
            .order_by("-year", "vehicle__sort_order", "vehicle__label")
        )


class VehicleYearCreateView(LoginRequiredMixin, CreateView):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class VehicleYearUpdateView(LoginRequiredMixin, UpdateView):
    model = VehicleYear
    form_class = VehicleYearForm
    template_name = "vehicles/vehicle_year_form.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_queryset(self):
        return VehicleYear.objects.filter(user=self.request.user).select_related("vehicle")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw


class VehicleYearDeleteView(UserPassesTestMixin, DeleteView):
    model = VehicleYear
    template_name = "vehicles/confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_year_list")

    def get_queryset(self):
        return VehicleYear.objects.filter(user=self.request.user)

    def test_func(self):
        return self.request.user.is_staff


# -------------------------
# VehicleMiles CRUD
# -------------------------

class VehicleMilesListView(LoginRequiredMixin, ListView):
    model = VehicleMiles
    template_name = "vehicles/vehicle_miles_list.html"
    context_object_name = "rows"
    paginate_by = 25

    def get_queryset(self):
        qs = VehicleMiles.objects.filter(user=self.request.user).select_related("vehicle").order_by("-date", "-id")

        vehicle_id = self.request.GET.get("vehicle") or ""
        if vehicle_id.isdigit():
            qs = qs.filter(vehicle_id=int(vehicle_id))

        mileage_type = (self.request.GET.get("type") or "").strip()
        if mileage_type:
            qs = qs.filter(mileage_type=mileage_type)

        return qs


class VehicleMilesCreateView(LoginRequiredMixin, CreateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class VehicleMilesUpdateView(LoginRequiredMixin, UpdateView):
    model = VehicleMiles
    form_class = VehicleMilesForm
    template_name = "vehicles/vehicle_miles_form.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(user=self.request.user).select_related("vehicle")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw


class VehicleMilesDeleteView(UserPassesTestMixin, DeleteView):
    model = VehicleMiles
    template_name = "vehicles/confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle_miles_list")

    def get_queryset(self):
        return VehicleMiles.objects.filter(user=self.request.user)

    def test_func(self):
        return self.request.user.is_staff