# vehicles/models.py
from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from ledger.models import OwnedModelMixin  




class Vehicle(OwnedModelMixin):
    label               = models.CharField(max_length=120, help_text="What you want to see in dropdowns (e.g., 2018 Ford F-150).")
    year                = models.PositiveIntegerField(blank=True, null=True)
    make                = models.CharField(max_length=60, blank=True)
    model               = models.CharField(max_length=60, blank=True)
    vin_last6           = models.CharField(max_length=6, blank=True)
    plate               = models.CharField(max_length=20, blank=True)
    in_service_date     = models.DateField(blank=True, null=True, default=None)
    in_service_mileage  = models.DecimalField(max_digits=10, decimal_places=1, validators=[MinValueValidator(0)], null=True, blank=True)
    sold_date           = models.DateField(blank=True, null=True, default=None)
    is_business         = models.BooleanField(default=True)
    is_active           = models.BooleanField(default=True)
    sort_order          = models.PositiveIntegerField(default=0)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "label"]
        constraints = [
            models.UniqueConstraint(fields=["user", "label"], name="uniq_vehicle_user_label")
        ]

    def __str__(self) -> str:
        return self.label


class VehicleYear(models.Model):
    class DeductionMethod(models.TextChoices):
        STANDARD_MILEAGE = "standard_mileage", "Standard mileage"
        ACTUAL_EXPENSES = "actual_expenses", "Actual expenses"

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle          = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="years")
    year             = models.PositiveIntegerField(default=timezone.now().year)
    odometer_start   = models.PositiveIntegerField(help_text="Odometer reading on Jan 1 (or start of year).")
    odometer_end     = models.PositiveIntegerField(null=True, blank=True, help_text="Odometer reading on Dec 31 (or end of year).")
    deduction_method = models.CharField(max_length=20, choices=DeductionMethod.choices, default=DeductionMethod.STANDARD_MILEAGE,)
    is_locked        = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
            ordering = ["-year", "vehicle__label"]
            constraints = [
                models.UniqueConstraint(fields=["user", "vehicle", "year"], name="uniq_vehicle_year_per_user"),
            ]

    def clean(self):
        super().clean()

        if self.vehicle_id and self.user_id and self.vehicle.user_id != self.user_id:
            raise ValidationError({"vehicle": "Vehicle does not belong to this user."})

        if self.odometer_end is not None and self.odometer_end < self.odometer_start:
            raise ValidationError({"odometer_end": "End odometer must be ≥ start odometer."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def total_miles(self) -> Decimal | None:
        if self.odometer_end is None:
            return None
        return (self.odometer_end - self.odometer_start).quantize(Decimal("0.1"))

    
    
    
    
class VehicleMiles(OwnedModelMixin):
    class MileageType(models.TextChoices):
        BUSINESS = "business", "Business"
        COMMUTING = "commuting", "Commuting"
        OTHER = "other", "Other"
        REIMBURSED = "reimbursed", "Reimbursed"

    date                = models.DateField(default=timezone.now)
    begin               = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    end                 = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    total               = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True, editable=False)
    vehicle             = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="miles_entries")
    mileage_type        = models.CharField(max_length=20, choices=MileageType.choices, default=MileageType.BUSINESS)
    notes               = models.CharField(max_length=255, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    
    class Meta:
            ordering = ["-date", "-id"]
            indexes = [
                models.Index(fields=["user", "date"]),
                models.Index(fields=["user", "vehicle"]),
                models.Index(fields=["user", "mileage_type"]),
            ]

    def clean(self):
        super().clean()

        if self.vehicle_id and self.user_id and self.vehicle.user_id != self.user_id:
            raise ValidationError({"vehicle": "Vehicle does not belong to this user."})

        if self.begin is not None and self.end is not None:
            if self.end < self.begin:
                raise ValidationError({"end": "End mileage must be ≥ begin mileage."})
            self.total = (self.end - self.begin).quantize(Decimal("0.1"))
        else:
            self.total = None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)