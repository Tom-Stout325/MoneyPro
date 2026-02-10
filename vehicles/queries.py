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


def _q1(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(ONE_TENTH, rounding=ROUND_HALF_UP)


def get_yearly_mileage_summary(*, business, vehicle_id: int, year: int) -> MileageYearSummary:
    vy = (
        VehicleYear.objects.filter(business=business, vehicle_id=vehicle_id, year=year)
        .select_related("vehicle")
        .first()
    )
    if not vy:
        raise VehicleYear.DoesNotExist("VehicleYear not found for business/year/vehicle.")

    business_miles = (
        VehicleMiles.objects.filter(
            business=business,
            vehicle_id=vehicle_id,
            date__year=year,
            mileage_type=VehicleMiles.MileageType.BUSINESS,
        ).aggregate(total=Sum("total"))["total"]
        or ZERO
    )

    # All non-business miles (commuting/other/reimbursed) as 'personal/other' bucket
    non_business = (
        VehicleMiles.objects.filter(
            business=business,
            vehicle_id=vehicle_id,
            date__year=year,
        )
        .exclude(mileage_type=VehicleMiles.MileageType.BUSINESS)
        .aggregate(total=Sum("total"))["total"]
        or ZERO
    )

    total_miles = _q1(vy.total_miles)
    business_miles_q = _q1(business_miles) or ZERO

    warnings: list[str] = []
    if vy.odometer_end is None:
        warnings.append("Odometer end is blank; total miles cannot be computed from odometer.")
    if total_miles is not None and business_miles_q > total_miles:
        warnings.append("Business miles exceed odometer total miles; check entries and odometer readings.")

    personal_miles = None
    if total_miles is not None:
        personal_miles = _q1(max(total_miles - business_miles_q, ZERO))

    return MileageYearSummary(
        year=year,
        vehicle_id=vy.vehicle_id,
        vehicle_year_id=vy.id,
        vehicle_label=vy.vehicle.label,
        deduction_method=vy.deduction_method,
        is_locked=vy.is_locked,
        odometer_start=vy.odometer_start,
        odometer_end=vy.odometer_end,
        total_miles=total_miles,
        business_miles=business_miles_q,
        personal_miles=personal_miles,
        warnings=warnings,
    )
