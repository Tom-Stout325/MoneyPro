from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from core.models import Business
from ledger.models import Category, Job, Payee, SubCategory, Transaction

try:
    # Team is added in your later work; keep optional so this command doesn't explode if absent.
    from ledger.models import Team  # type: ignore
except Exception:  # pragma: no cover
    Team = None  # type: ignore

from vehicles.models import Vehicle


@dataclass
class RowError:
    row_num: int
    error: str


def _s(val: object) -> str:
    """Normalize CSV cell to stripped string (handles None)."""
    if val is None:
        return ""
    return str(val).strip()


def _parse_amount(raw: str) -> tuple[Decimal, bool]:
    """Return (amount_abs, is_refund). Refunds are represented by negative values."""
    raw = raw.replace("$", "").replace(",", "").strip()
    if raw == "":
        raise InvalidOperation("blank")
    amt = Decimal(raw)
    if amt < 0:
        return (-amt, True)
    return (amt, False)


def _parse_date_flex(raw: str):
    """Parse a date from common CSV formats.

    Accepts ISO (YYYY-MM-DD) and common US formats (M/D/YY, M/D/YYYY).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    # First try Django's ISO parser.
    dt = parse_date(raw)
    if dt:
        return dt

    # Then try common US formats.
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = "One-time importer for sample transactions CSV (business-scoped)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-id",
            type=int,
            required=True,
            help="Business ID to import into.",
        )
        parser.add_argument(
            "--csv",
            dest="csv_path",
            type=str,
            required=True,
            help="Path to the sample CSV file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate only; do not write to the database.",
        )
        parser.add_argument(
            "--errors-out",
            type=str,
            default="",
            help="Optional path for an errors CSV (defaults to <csv>.errors.csv).",
        )

    def handle(self, *args, **options):
        business_id: int = options["business_id"]
        csv_path = Path(options["csv_path"]).expanduser().resolve()
        dry_run: bool = bool(options["dry_run"])
        errors_out_opt: str = options["errors_out"] or ""

        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        try:
            business = Business.objects.get(pk=business_id)
        except Business.DoesNotExist as exc:
            raise CommandError(f"Business not found: id={business_id}") from exc

        errors_out = (
            Path(errors_out_opt).expanduser().resolve()
            if errors_out_opt
            else csv_path.with_suffix(csv_path.suffix + ".errors.csv")
        )

        created = 0
        skipped = 0
        errors: list[RowError] = []

        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise CommandError("CSV has no header row.")

            required_headers = {
                "Date",
                "Type",
                "Description",
                "Category",
                "SubCategory",
                "Amount",
                "Team",
                "Event",
                "Invoice Number",
            }
            missing_headers = required_headers - set(reader.fieldnames)
            if missing_headers:
                raise CommandError(f"Missing CSV columns: {', '.join(sorted(missing_headers))}")

            for idx, row in enumerate(reader, start=2):  # start=2 (row 1 is header)
                try:
                    self._import_row(business=business, row=row, row_num=idx, dry_run=dry_run)
                except Exception as exc:
                    skipped += 1
                    errors.append(RowError(row_num=idx, error=str(exc)))
                else:
                    created += 1

        # Write error report if any
        if errors:
            with errors_out.open("w", newline="", encoding="utf-8") as ef:
                w = csv.writer(ef)
                w.writerow(["row", "error"])
                for e in errors:
                    w.writerow([e.row_num, e.error])

        self.stdout.write(self.style.SUCCESS(f"Done. Imported={created} Skipped={skipped} DryRun={dry_run}"))
        if errors:
            self.stdout.write(self.style.WARNING(f"Errors written to: {errors_out}"))

    def _import_row(self, *, business: Business, row: dict, row_num: int, dry_run: bool) -> None:
        date_str = _s(row.get("Date"))
        dt = _parse_date_flex(date_str)
        if not dt:
            raise ValueError(f"Row {row_num}: invalid Date '{date_str}'")

        desc = _s(row.get("Description"))
        if not desc:
            raise ValueError(f"Row {row_num}: Description is required")

        type_str = _s(row.get("Type")).lower()
        # Map CSV values like "Income"/"Expense" to our internal enum values
        type_map = {"income": "income", "expense": "expense"}
        category_type = type_map.get(type_str)
        if not category_type:
            raise ValueError(f"Row {row_num}: invalid Type '{row.get('Type')}'")

        cat_name = _s(row.get("Category"))
        sub_name = _s(row.get("SubCategory"))
        if not cat_name or not sub_name:
            raise ValueError(f"Row {row_num}: Category and SubCategory are required")

        category = Category.objects.filter(
            business=business,
            name=cat_name,
            category_type=category_type,
        ).first()
        if not category:
            raise ValueError(f"Row {row_num}: Category not found: '{cat_name}' ({category_type})")

        subcategory = SubCategory.objects.filter(
            business=business,
            category=category,
            name=sub_name,
        ).first()
        if not subcategory:
            # helpful hint if subcategory exists under a different category
            other = SubCategory.objects.filter(business=business, name=sub_name).select_related("category").first()
            if other:
                raise ValueError(
                    f"Row {row_num}: SubCategory '{sub_name}' exists but under Category '{other.category.name}'"
                )
            raise ValueError(f"Row {row_num}: SubCategory not found: '{sub_name}'")

        amount_raw = _s(row.get("Amount"))
        try:
            amount, is_refund = _parse_amount(amount_raw)
        except (InvalidOperation, ValueError):
            raise ValueError(f"Row {row_num}: invalid Amount '{amount_raw}'")

        invoice_number = _s(row.get("Invoice Number"))

        # Optional Team
        team_obj = None
        team_name = _s(row.get("Team"))
        if team_name:
            if Team is None:
                raise ValueError(f"Row {row_num}: Team column provided but Team model is not available")
            team_obj, _ = Team.objects.get_or_create(business=business, name=team_name)

        # Optional Event -> Job
        job_obj = None
        event_title = _s(row.get("Event"))
        if event_title:
            job_obj, _ = Job.objects.get_or_create(business=business, year=dt.year, title=event_title)

        # Defaults for required rules
        payee_obj = None
        transport_type = ""
        vehicle_obj = None

        if subcategory.requires_payee:
            payee_obj = Payee.get_unknown(business=business)

        if subcategory.requires_vehicle:
            vehicle_obj = (
                Vehicle.objects.filter(business=business, is_active=True, is_business=True)
                .order_by("sort_order", "label")
                .first()
            )
            if not vehicle_obj:
                raise ValueError(
                    f"Row {row_num}: SubCategory '{sub_name}' requires a vehicle but no active business vehicle exists"
                )
            transport_type = "business_vehicle"
        elif subcategory.requires_transport:
            transport_type = "personal_vehicle"

        obj = Transaction(
            business=business,
            date=dt,
            amount=amount,
            is_refund=is_refund,
            description=desc,
            subcategory=subcategory,
            category=subcategory.category,
            trans_type=subcategory.category.category_type,
            payee=payee_obj,
            job=job_obj,
            invoice_number=invoice_number,
            transport_type=transport_type,
            vehicle=vehicle_obj,
        )

        # Attach Team if available on Transaction
        if team_obj is not None:
            # Transaction.team may not exist in older code; set only if present
            if hasattr(obj, "team"):
                setattr(obj, "team", team_obj)

        # Validate so you get clean data (and so later edits don't suddenly break)
        try:
            obj.full_clean()
        except ValidationError as ve:
            raise ValueError(f"Row {row_num}: validation failed: {ve.message_dict or ve.messages}")

        if dry_run:
            return

        # Save with an atomic block so a single bad row doesn't poison the connection.
        with transaction.atomic():
            obj.save()
