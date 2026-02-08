# ledger/services.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.utils.text import slugify

from .models import Category, SubCategory


def _field_max_length(model, field_name: str, fallback: int) -> int:
    try:
        f = model._meta.get_field(field_name)
        return int(getattr(f, "max_length", None) or fallback)
    except Exception:
        return fallback


def _unique_slug(base: str, used: set[str], max_len: int) -> str:
    """
    Return a unique slug within the 'used' set.
    """
    base = slugify(base)[:max_len] or "item"
    slug = base
    i = 2
    while slug in used:
        suffix = f"-{i}"
        slug = (base[: (max_len - len(suffix))] + suffix)
        i += 1
    used.add(slug)
    return slug


def _model_has_field(model, field_name: str) -> bool:
    return any(f.name == field_name for f in model._meta.get_fields())


# ------------------------------------------------------------------------------
# Schedule C seeding (spreadsheet-friendly specs + conversion to enum keys)
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class CategorySpec:
    # Spreadsheet row
    name: str
    schedule_c_line: str  # spreadsheet code like "1", "16a", "27b"
    category_type: str    # "income" | "expense"
    book_reports: bool
    tax_reports: bool
    report_group: str     # "Part I" | "Part II" | "Part V"


CATEGORY_SPECS: list[CategorySpec] = [
    CategorySpec("Gross Receipts", "1", "income", True, True, "Part I"),
    CategorySpec("Returns & Allowances", "2", "income", False, True, "Part I"),  # Tax only per your list

    CategorySpec("Advertising", "8", "expense", True, True, "Part II"),
    CategorySpec("Car & Truck Expenses", "9", "expense", True, True, "Part II"),
    CategorySpec("Commissions & Fees", "10", "expense", True, True, "Part II"),
    CategorySpec("Contract Labor", "11", "expense", True, True, "Part II"),
    CategorySpec("Depletion", "12", "expense", True, True, "Part II"),
    CategorySpec("Depreciation & Section 179", "13", "expense", True, True, "Part II"),
    CategorySpec("Employee Benefits", "14", "expense", True, True, "Part II"),
    CategorySpec("Insurance", "15", "expense", True, True, "Part II"),
    CategorySpec("Interest: Mortgage", "16a", "expense", True, True, "Part II"),
    CategorySpec("Interest: Other", "16b", "expense", True, True, "Part II"),
    CategorySpec("Legal & Professional", "17", "expense", True, True, "Part II"),
    CategorySpec("Office Expenses", "18", "expense", True, True, "Part II"),
    CategorySpec("Pension & Profit Sharing", "19", "expense", True, True, "Part II"),
    CategorySpec("Rent or Lease: Vehicles & Machinery", "20a", "expense", True, True, "Part II"),
    CategorySpec("Rent or Lease: Other Business Property", "20b", "expense", True, True, "Part II"),
    CategorySpec("Repairs & Maintenance", "21", "expense", True, True, "Part II"),
    CategorySpec("Supplies", "22", "expense", True, True, "Part II"),
    CategorySpec("Taxes & Licenses", "23", "expense", True, True, "Part II"),
    CategorySpec("Travel & Meals: Travel", "24a", "expense", True, True, "Part II"),
    CategorySpec("Travel & Meals: Meals", "24b", "expense", True, True, "Part II"),
    CategorySpec("Utilities", "25", "expense", True, True, "Part II"),
    CategorySpec("Wages", "26", "expense", True, True, "Part II"),
    CategorySpec("Energy Efficient Buildings", "27a", "expense", True, True, "Part II"),

    # Your spreadsheet: 27b is Part V
    CategorySpec("Other Expenses", "27b", "expense", True, True, "Part V"),
]


# Spreadsheet Schedule C line code -> Category.ScheduleCLine enum key
SCHEDULE_C_LINE_TO_CHOICE: dict[str, str] = {
    # Part I
    "1": Category.ScheduleCLine.GROSS_RECEIPTS,
    "2": Category.ScheduleCLine.RETURNS_ALLOWANCES,

    # Part II
    "8": Category.ScheduleCLine.ADVERTISING,
    "9": Category.ScheduleCLine.CAR_TRUCK,
    "10": Category.ScheduleCLine.COMMISSIONS_FEES,
    "11": Category.ScheduleCLine.CONTRACT_LABOR,
    "12": Category.ScheduleCLine.DEPLETION,
    "13": Category.ScheduleCLine.DEPRECIATION,
    "14": Category.ScheduleCLine.EMPLOYEE_BENEFITS,
    "15": Category.ScheduleCLine.INSURANCE,
    "16a": Category.ScheduleCLine.INTEREST_MORTGAGE,
    "16b": Category.ScheduleCLine.INTEREST_OTHER,
    "17": Category.ScheduleCLine.LEGAL_PRO,
    "18": Category.ScheduleCLine.OFFICE,
    "19": Category.ScheduleCLine.PENSION_PROFIT,
    "20a": Category.ScheduleCLine.RENT_LEASE_VEHICLES,
    "20b": Category.ScheduleCLine.RENT_LEASE_OTHER,
    "21": Category.ScheduleCLine.REPAIRS,
    "22": Category.ScheduleCLine.SUPPLIES,
    "23": Category.ScheduleCLine.TAXES_LICENSES,
    "24a": Category.ScheduleCLine.TRAVEL,
    "24b": Category.ScheduleCLine.MEALS,
    "25": Category.ScheduleCLine.UTILITIES,
    "26": Category.ScheduleCLine.WAGES,
    "27a": Category.ScheduleCLine.ENERGY_EFFICIENT,

    # Part V
    "27b": Category.ScheduleCLine.OTHER_EXPENSES_V,
}


def _schedule_c_choice(line_code: str) -> str:
    k = (line_code or "").strip().lower()
    try:
        return SCHEDULE_C_LINE_TO_CHOICE[k]
    except KeyError as e:
        raise ValueError(f"Unknown Schedule C line code: {line_code!r}") from e


# ------------------------------------------------------------------------------
# Subcategory seed list (name -> parent category name)
# NOTE: SubCategory names are unique per user (per your UniqueConstraint on user+category+name
# AND your seed sanity check below also expects global uniqueness by name for safety).
# ------------------------------------------------------------------------------

SUBCATEGORY_SPECS: list[tuple[str, str]] = [
    # Income
    ("Sales", "Gross Receipts"),
    ("Sales Tax Collected", "Gross Receipts"),
    ("Drone Services", "Gross Receipts"),
    ("Photography Services", "Gross Receipts"),

    # Returns & Allowances
    ("Returns & Allowances", "Returns & Allowances"),

    # Advertising
    ("Advertising", "Advertising"),

    # Car & Truck
    ("Gas", "Car & Truck Expenses"),
    ("Vehicle Loan Interest", "Car & Truck Expenses"),
    ("Vehicle Maintenance", "Car & Truck Expenses"),
    ("Vehicle Loan Payments", "Car & Truck Expenses"),
    ("Vehicle Equipment Purchases", "Car & Truck Expenses"),
    ("Vehicle Repairs", "Car & Truck Expenses"),
    ("Vehicle Other Expenses", "Car & Truck Expenses"),

    # Commissions & Fees
    ("Commissions & Fees", "Commissions & Fees"),

    # Contract Labor
    ("Contractors", "Contract Labor"),

    # Depletion
    ("Depletion", "Depletion"),

    # Depreciation & Section 179
    ("Depreciation", "Depreciation & Section 179"),
    ("Section 179", "Depreciation & Section 179"),

    # Employee Benefits
    ("Accident Insurance", "Employee Benefits"),

    # Insurance
    ("Aviation Insurance", "Insurance"),
    ("Liability Insurance", "Insurance"),

    # Interest
    ("Mortgage Interest", "Interest: Mortgage"),
    ("Other Interest", "Interest: Other"),

    # Legal & Professional
    ("Accounting Services", "Legal & Professional"),
    ("Legal Services", "Legal & Professional"),

    # Office Expenses
    ("Office Supplies", "Office Expenses"),
    ("Postage & Shipping", "Office Expenses"),

    # Pension & Profit Sharing
    ("Employee Retirement Contributions", "Pension & Profit Sharing"),

    # Rent or Lease
    ("Machinery Rental", "Rent or Lease: Vehicles & Machinery"),
    ("Drone Equipment Rental", "Rent or Lease: Other Business Property"),
    ("Photography Equipment Rental", "Rent or Lease: Other Business Property"),

    # Repairs
    ("Drone Equipment Repairs", "Repairs & Maintenance"),

    # Supplies
    ("Materials & Supplies", "Supplies"),

    # Taxes & Licenses
    ("Sales Tax Paid", "Taxes & Licenses"),

    # Travel
    ("Hotels", "Travel & Meals: Travel"),
    ("Car Rental", "Travel & Meals: Travel"),
    ("Airfare", "Travel & Meals: Travel"),
    ("Parking & Tolls", "Travel & Meals: Travel"),

    # Meals
    ("Travel Meals", "Travel & Meals: Meals"),

    # Utilities
    ("Cell Phone", "Utilities"),
    ("Internet", "Utilities"),

    # Wages
    ("Wages", "Wages"),

    # 27a
    ("Energy Efficient Buildings", "Energy Efficient Buildings"),

    # Other Expenses (Part V detail)
    ("Bank Fees", "Other Expenses"),
    ("Computer Equipment", "Other Expenses"),
    ("Drone Equipment", "Other Expenses"),
    ("Education", "Other Expenses"),
    ("Office Equipment", "Other Expenses"),
    ("Photography Equipment", "Other Expenses"),
    ("Software", "Other Expenses"),
    ("Web Hosting", "Other Expenses"),
    ("Cloud Services", "Other Expenses"),
    ("Business Meals", "Other Expenses"),
]


# ------------------------------------------------------------------------------
# Main seeding function
# ------------------------------------------------------------------------------

@transaction.atomic
def seed_schedule_c_defaults(user) -> None:
    """
    Seeds a fixed Schedule C category set + default subcategories for a user.

    - Categories are seeded from spreadsheet-friendly specs (line codes like "16a"),
      but stored as enum keys (e.g. "interest_mortgage") to satisfy choices validation.
    - Users select SubCategory only; Category is derived from SubCategory.category.
    - Idempotent: safe to run multiple times.
    """

    # Slug max lengths from models (falls back safely)
    cat_slug_max = _field_max_length(Category, "slug", 120)
    sub_slug_max = _field_max_length(SubCategory, "slug", 140)

    # Track existing slugs to avoid collisions within the user's namespace
    used_cat_slugs = set(
        Category.objects.filter(user=user)
        .exclude(slug__isnull=True)
        .exclude(slug="")
        .values_list("slug", flat=True)
    )
    used_sub_slugs = set(
        SubCategory.objects.filter(user=user)
        .exclude(slug__isnull=True)
        .exclude(slug="")
        .values_list("slug", flat=True)
    )

    # ---- Create / update Categories ----
    categories_by_name: dict[str, Category] = {}

    for idx, spec in enumerate(CATEGORY_SPECS, start=1):
        desired_line = _schedule_c_choice(spec.schedule_c_line)
        cat, _created = Category.objects.get_or_create(
            user=user,
            name=spec.name,
            defaults={
                "slug": _unique_slug(spec.name, used_cat_slugs, cat_slug_max),
                "category_type": spec.category_type,
                "book_reports": spec.book_reports,
                "tax_reports": spec.tax_reports,
                "schedule_c_line": desired_line,
                "report_group": spec.report_group,
                "is_active": True,
                "sort_order": idx,
            },
        )

        # Keep seeded categories aligned with the spec (idempotent updates)
        updates: dict[str, object] = {}

        if cat.sort_order != idx:
            updates["sort_order"] = idx

        if not cat.slug:
            updates["slug"] = _unique_slug(spec.name, used_cat_slugs, cat_slug_max)

        if cat.category_type != spec.category_type:
            updates["category_type"] = spec.category_type

        if cat.book_reports != spec.book_reports:
            updates["book_reports"] = spec.book_reports

        if cat.tax_reports != spec.tax_reports:
            updates["tax_reports"] = spec.tax_reports

        if (cat.schedule_c_line or "") != (desired_line or ""):
            updates["schedule_c_line"] = desired_line

        if (cat.report_group or "") != (spec.report_group or ""):
            updates["report_group"] = spec.report_group

        if cat.is_active is not True:
            updates["is_active"] = True

        if updates:
            Category.objects.filter(pk=cat.pk).update(**updates)
            for k, v in updates.items():
                setattr(cat, k, v)

        categories_by_name[spec.name] = cat

    # ---- Seed list sanity: ensure SubCategory names are unique within the seed list ----
    # (Your DB constraint is unique per (user, category, name). This is a stricter safety check
    # to prevent identical names across categories in your seed list.)
    seen: set[str] = set()
    dupes: set[str] = set()
    for n, _parent in SUBCATEGORY_SPECS:
        if n in seen:
            dupes.add(n)
        seen.add(n)
    if dupes:
        raise ValueError(f"Duplicate SubCategory names in SUBCATEGORY_SPECS: {sorted(dupes)}")

    # ---- Create / update SubCategories ----
    has_requires_payee = _model_has_field(SubCategory, "requires_payee")
    has_payee_role = _model_has_field(SubCategory, "payee_role")

    existing_subs = {
        s.name: s for s in SubCategory.objects.filter(user=user).select_related("category")
    }

    to_create: list[SubCategory] = []

    for sub_name, parent_cat_name in SUBCATEGORY_SPECS:
        parent = categories_by_name.get(parent_cat_name)
        if not parent:
            raise ValueError(
                f"Missing parent Category '{parent_cat_name}' for SubCategory '{sub_name}'"
            )

        existing = existing_subs.get(sub_name)
        if existing:
            updates: dict[str, object] = {}

            if existing.category_id != parent.id:
                updates["category_id"] = parent.id

            if not existing.slug:
                updates["slug"] = _unique_slug(f"{parent.name}-{sub_name}", used_sub_slugs, sub_slug_max)

            if getattr(existing, "is_active", True) is not True:
                updates["is_active"] = True

            if updates:
                SubCategory.objects.filter(pk=existing.pk).update(**updates)
            continue

        kwargs: dict[str, object] = {
            "user": user,
            "category": parent,
            "name": sub_name,
            "slug": _unique_slug(f"{parent.name}-{sub_name}", used_sub_slugs, sub_slug_max),
            "is_active": True,
        }

        # Optional fields: if your SubCategory model includes these, keep defaults consistent.
        if has_requires_payee:
            kwargs["requires_payee"] = False
        if has_payee_role:
            kwargs["payee_role"] = "any"

        to_create.append(SubCategory(**kwargs))

    if to_create:
        SubCategory.objects.bulk_create(to_create)
