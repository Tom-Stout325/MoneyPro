from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from vehicles.models import VehicleMiles, VehicleYear


ZERO = Decimal("0.0")
ONE_TENTH = Decimal("0.1")


@dataclass(frozen=True)
class MileageYearSummary:
    year: int
    vehicle_id: int
    vehicle_year_id: int
    vehicle_label: str
    deduction_method: str
    is_locked: bool
    odometer_start: Decimal
    odometer_end: Decimal | None
    total_miles: Decimal | None
    business_miles: Decimal
    personal_miles: Decimal | None
    warnings: list[str]


def get_yearly_mileage_summary(*, user, vehicle_id: int, year: int) -> MileageYearSummary:
    vy = VehicleYear.objects.select_related("vehicle").get(
        user=user, vehicle_id=vehicle_id, year=year
    )

    agg = VehicleMiles.objects.filter(
        user=user,
        vehicle_id=vehicle_id,
        date__year=year,
        mileage_type=VehicleMiles.MileageType.BUSINESS,
    ).aggregate(total=Sum("total"))

    business_miles = (agg["total"] or ZERO).quantize(ONE_TENTH, rounding=ROUND_HALF_UP)

    total_miles = vy.total_miles  # Decimal | None
    if total_miles is not None:
        total_miles = total_miles.quantize(ONE_TENTH, rounding=ROUND_HALF_UP)

    personal_miles: Decimal | None = None
    warnings: list[str] = []

    if total_miles is None:
        warnings.append(
            "Missing odometer end for the year — total/personal miles can’t be calculated yet."
        )
    else:
        personal_miles = (total_miles - business_miles).quantize(
            ONE_TENTH, rounding=ROUND_HALF_UP
        )
        if personal_miles < 0:
            warnings.append(
                "Business miles exceed total miles. Check odometer readings or mileage logs."
            )
            personal_miles = ZERO

    return MileageYearSummary(
        year=vy.year,
        vehicle_id=vy.vehicle_id,
        vehicle_year_id=vy.pk,
        vehicle_label=vy.vehicle.label,
        deduction_method=vy.get_deduction_method_display(),
        is_locked=vy.is_locked,
        odometer_start=vy.odometer_start,
        odometer_end=vy.odometer_end,
        total_miles=total_miles,
        business_miles=business_miles,
        personal_miles=personal_miles,
        warnings=warnings,
    )
