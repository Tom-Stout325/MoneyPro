from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from assets.models import Asset
from vehicles.models import VehicleYear

from .profit_loss import ProfitLossSingle, build_profit_loss_single
from .schedule_c import LineRow, build_schedule_c_lines

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class VehicleTaxRow:
    vehicle_year_id: int
    vehicle_label: str
    deduction_method_label: str
    total_miles: Decimal | None
    business_miles: Decimal
    business_use_pct: Decimal | None
    standard_mileage_rate: Decimal | None
    standard_mileage_deduction: Decimal | None
    actual_expenses_total: Decimal
    annual_interest_paid: Decimal
    business_interest_amount: Decimal
    deduction_amount: Decimal | None
    warnings: list[str]


@dataclass(frozen=True)
class Section179Row:
    asset_id: int
    name: str
    asset_type: str
    placed_in_service_date: date | None
    purchase_price: Decimal
    section_179_amount: Decimal


@dataclass(frozen=True)
class TaxPacket:
    year: int
    as_of_date: date
    is_partial_year: bool
    pl: ProfitLossSingle
    schedule_c_lines: list[LineRow]
    schedule_c_total: Decimal
    vehicle_rows: list[VehicleTaxRow]
    total_business_miles: Decimal
    total_vehicle_interest_paid: Decimal
    total_vehicle_business_interest: Decimal
    section_179_rows: list[Section179Row]
    total_section_179: Decimal



def _money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(Decimal("0.01"))



def _safe_attr(obj, attr: str, default=ZERO):
    value = getattr(obj, attr, default)
    if value is None:
        return default
    return value



def build_tax_packet(*, business, year: int) -> TaxPacket:
    today = date.today()
    as_of_date = today if year == today.year else date(year, 12, 31)
    is_partial_year = year == today.year

    pl = build_profit_loss_single(business=business, year=year)
    schedule_c_lines, schedule_c_total = build_schedule_c_lines(
        business=business,
        year=year,
        meals_rate=Decimal("0.50"),
        mode="tax",
    )

    vehicle_rows: list[VehicleTaxRow] = []
    total_business_miles = ZERO
    total_vehicle_interest_paid = ZERO
    total_vehicle_business_interest = ZERO

    vehicle_years = (
        VehicleYear.objects.filter(business=business, year=year)
        .select_related("vehicle")
        .order_by("vehicle__label")
    )
    for vy in vehicle_years:
        annual_interest_paid = _money(_safe_attr(vy, "annual_interest_paid", ZERO))
        business_interest_amount = _money(_safe_attr(vy, "business_interest_amount", ZERO))
        row = VehicleTaxRow(
            vehicle_year_id=vy.id,
            vehicle_label=vy.vehicle.label,
            deduction_method_label=vy.get_deduction_method_display(),
            total_miles=vy.total_miles,
            business_miles=_money(vy.business_miles),
            business_use_pct=vy.business_use_pct,
            standard_mileage_rate=vy.standard_mileage_rate,
            standard_mileage_deduction=_money(vy.standard_mileage_deduction),
            actual_expenses_total=_money(vy.actual_expenses_total),
            annual_interest_paid=annual_interest_paid,
            business_interest_amount=business_interest_amount,
            deduction_amount=_money(vy.deduction_amount),
            warnings=list(vy.missing_data_flags),
        )
        vehicle_rows.append(row)
        total_business_miles += row.business_miles
        total_vehicle_interest_paid += row.annual_interest_paid
        total_vehicle_business_interest += row.business_interest_amount

    section_179_rows: list[Section179Row] = []
    total_section_179 = ZERO
    assets = Asset.objects.filter(business=business).order_by("placed_in_service_date", "purchase_date", "name")
    for asset in assets:
        service_date = asset.placed_in_service_date or asset.purchase_date
        if not service_date or service_date.year != year:
            continue
        elected = _money(asset.section_179_amount)
        if elected <= ZERO:
            continue
        row = Section179Row(
            asset_id=asset.id,
            name=asset.name,
            asset_type=asset.get_asset_type_display(),
            placed_in_service_date=service_date,
            purchase_price=_money(asset.purchase_price),
            section_179_amount=elected,
        )
        section_179_rows.append(row)
        total_section_179 += elected

    return TaxPacket(
        year=year,
        as_of_date=as_of_date,
        is_partial_year=is_partial_year,
        pl=pl,
        schedule_c_lines=schedule_c_lines,
        schedule_c_total=_money(schedule_c_total),
        vehicle_rows=vehicle_rows,
        total_business_miles=_money(total_business_miles),
        total_vehicle_interest_paid=_money(total_vehicle_interest_paid),
        total_vehicle_business_interest=_money(total_vehicle_business_interest),
        section_179_rows=section_179_rows,
        total_section_179=_money(total_section_179),
    )
