# ledger/reporting_utils.py
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterable, Optional

LINE_RE = re.compile(r"^\s*(\d+)\s*([a-zA-Z]?)\s*$")


def schedule_c_sort_key(line: str | None) -> tuple[int, int]:
    """
    Sort Schedule C line codes in a human/IRS-friendly order.

    Examples:
      "1"   -> (1, 0)
      "16a" -> (16, 1)
      "16b" -> (16, 2)
      "24a" -> (24, 1)
      "24b" -> (24, 2)
      ""/None -> (9999, 0)  (pushes blanks to the end)

    This key is safe to use in Python sorting for report display order.
    """
    if not line:
        return (9999, 0)

    s = str(line).strip().lower()
    m = LINE_RE.match(s)
    if not m:
        # Unknown format goes after valid lines but before blanks if you want;
        # here we push unknowns near the end.
        return (9998, 0)

    num = int(m.group(1))
    suffix = m.group(2) or ""

    # a -> 1, b -> 2, c -> 3 ... (no suffix -> 0)
    suffix_rank = 0
    if suffix:
        suffix_rank = (ord(suffix) - ord("a")) + 1
        if suffix_rank < 1:
            suffix_rank = 0

    return (num, suffix_rank)


def normalize_returns_allowances(amount: Any) -> Decimal:
    """
    Returns & Allowances should ALWAYS reduce income in both book and tax reports.

    This helper:
      - converts input to Decimal (best-effort)
      - returns a NEGATIVE value (or zero)
      - does NOT mutate stored DB values (use only at report/calculation time)

    Examples:
      100   -> -100
      -100  -> -100
      0     -> 0
      "12.34" -> -12.34
    """
    if amount is None:
        return Decimal("0")

    # Best-effort conversion to Decimal (handles Decimal, int, float, str)
    try:
        dec = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except Exception:
        return Decimal("0")

    if dec == 0:
        return Decimal("0")

    return -abs(dec)


def is_returns_allowances_subcategory(
    subcategory_name: str | None,
    category_name: str | None = None,
) -> bool:
    """
    Lightweight predicate for the special handling. Use both checks when possible.

    Recommended usage: pass both category and subcategory names from the DB.
    """
    if not subcategory_name:
        return False

    sub = subcategory_name.strip().lower()
    if sub == "returns & allowances" or sub == "returns and allowances":
        return True

    # Optional extra guard if you prefer strict category match too
    if category_name:
        cat = category_name.strip().lower()
        if cat in ("returns & allowances", "returns and allowances") and "returns" in sub:
            return True

    return False



def is_other_expenses_category(
    category_name: str | None,
    schedule_c_line: str | None = None,
) -> bool:
    """
    True if this Category represents Schedule C 'Other Expenses' (line 27b).

    Use BOTH checks when possible for safety.
    """
    if schedule_c_line:
        if str(schedule_c_line).strip().lower() == "27b":
            return True

    if category_name:
        name = category_name.strip().lower()
        if name == "other expenses":
            return True

    return False


def route_category_for_report(
    *,
    category_name: str | None,
    schedule_c_line: str | None,
    report_group: str | None,
) -> str:
    """
    Determines where a category should appear in reports.

    Rules:
    - Other Expenses (27b):
        * TOTAL line appears in Part II
        * DETAIL breakdown appears in Part V
    - All others: use category.report_group as-is

    Returns:
        "Part I" | "Part II" | "Part III" | "Part IV" | "Part V"
    """
    if is_other_expenses_category(category_name, schedule_c_line):
        # Category total stays in Part II
        return "Part II"

    return report_group or ""


def route_subcategory_for_report(
    *,
    category_name: str | None,
    schedule_c_line: str | None,
    default_group: str | None,
) -> str:
    """
    Determines where a SUBCATEGORY should appear in reports.

    Rules:
    - Subcategories under Other Expenses (27b) render in Part V
    - All others follow their category's report group

    Returns:
        "Part I" | "Part II" | "Part III" | "Part IV" | "Part V"
    """
    if is_other_expenses_category(category_name, schedule_c_line):
        return "Part V"

    return default_group or ""