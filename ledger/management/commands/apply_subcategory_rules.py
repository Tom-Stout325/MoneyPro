from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from ledger.models import SubCategory


DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "subcategory_rules.json"


def _b(v) -> bool:
    return bool(v)


class Command(BaseCommand):
    help = "Apply SubCategory rules (account_type + requires_* flags) from a JSON rules file."

    def add_arguments(self, parser):
        parser.add_argument("--business-id", type=int, required=True)
        parser.add_argument(
            "--rules",
            type=str,
            default=str(DEFAULT_RULES_PATH),
            help="Path to subcategory_rules.json (defaults to ledger/data/subcategory_rules.json)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving.")

    def handle(self, *args, **options):
        business_id: int = options["business_id"]
        rules_path = Path(options["rules"]).expanduser().resolve()
        dry_run: bool = options["dry_run"]

        if not rules_path.exists():
            raise CommandError(f"Rules file not found: {rules_path}")

        data = json.loads(rules_path.read_text(encoding="utf-8"))
        rules: dict = data.get("rules") or {}
        if not isinstance(rules, dict) or not rules:
            raise CommandError("Rules JSON has no 'rules' object (or it is empty).")

        updated = 0
        unchanged = 0
        missing: list[str] = []
        multi_match: list[tuple[str, int]] = []

        def find_targets(rule_slug: str, rule_name: str):
            """Match subcategories for a business.

            Matching order:
            1) Exact name match (case-insensitive)
            2) Exact slug match
            3) Slug suffix match (because many slugs are category-name + '-' + subcat)
            """
            qs = SubCategory.objects.filter(business_id=business_id)

            by_name = qs.filter(name__iexact=rule_name)
            if by_name.exists():
                return by_name

            by_slug = qs.filter(slug__iexact=rule_slug)
            if by_slug.exists():
                return by_slug

            suffix = f"-{rule_slug}"
            return qs.filter(Q(slug__iendswith=suffix) | Q(slug__iexact=rule_slug))

        with transaction.atomic():
            for rule_slug, rule in rules.items():
                rule_name = (rule.get("name") or "").strip() or rule_slug
                targets = find_targets(rule_slug, rule_name)

                if not targets.exists():
                    missing.append(rule_name)
                    continue

                if targets.count() > 1:
                    multi_match.append((rule_name, targets.count()))

                for sc in targets:
                    before = {
                        "account_type": sc.account_type,
                        "requires_contact": sc.requires_contact,
                        "contact_role": sc.contact_role,
                        "requires_receipt": getattr(sc, "requires_receipt", False),
                        "requires_team": getattr(sc, "requires_team", False),
                        "requires_job": getattr(sc, "requires_job", False),
                        "requires_invoice_number": getattr(sc, "requires_invoice_number", False),
                        "requires_transport": sc.requires_transport,
                        "requires_vehicle": sc.requires_vehicle,
                        "requires_asset": getattr(sc, "requires_asset", False),
                        "is_capitalizable": getattr(sc, "is_capitalizable", False),
                    }

                    # Apply rule values
                    sc.account_type = (rule.get("account_type") or sc.account_type or "expense").lower()

                    if hasattr(sc, "requires_receipt"):
                        sc.requires_receipt = _b(rule.get("requires_receipt"))
                    if hasattr(sc, "requires_team"):
                        sc.requires_team = _b(rule.get("requires_team"))
                    if hasattr(sc, "requires_job"):
                        sc.requires_job = _b(rule.get("requires_job"))
                    if hasattr(sc, "requires_invoice_number"):
                        sc.requires_invoice_number = _b(rule.get("requires_invoice_number"))
                    if hasattr(sc, "requires_asset"):
                        sc.requires_asset = _b(rule.get("requires_asset"))

                    sc.requires_contact = _b(rule.get("requires_contact"))
                    if hasattr(sc, "contact_role") and rule.get("contact_role"):
                        sc.contact_role = str(rule.get("contact_role")).lower()

                    sc.requires_transport = _b(rule.get("requires_transport"))
                    sc.requires_vehicle = _b(rule.get("requires_vehicle"))

                    if hasattr(sc, "is_capitalizable"):
                        sc.is_capitalizable = _b(rule.get("is_capitalizable"))

                    after = {
                        "account_type": sc.account_type,
                        "requires_contact": sc.requires_contact,
                        "contact_role": sc.contact_role,
                        "requires_receipt": getattr(sc, "requires_receipt", False),
                        "requires_team": getattr(sc, "requires_team", False),
                        "requires_job": getattr(sc, "requires_job", False),
                        "requires_invoice_number": getattr(sc, "requires_invoice_number", False),
                        "requires_transport": sc.requires_transport,
                        "requires_vehicle": sc.requires_vehicle,
                        "requires_asset": getattr(sc, "requires_asset", False),
                        "is_capitalizable": getattr(sc, "is_capitalizable", False),
                    }

                    if before == after:
                        unchanged += 1
                        continue

                    updated += 1

                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[DRY-RUN] Would update: {sc.name} (slug={sc.slug})\n  {before} -> {after}"
                            )
                        )
                    else:
                        sc.full_clean()
                        sc.save()

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\nSubCategory rules applied."))
        self.stdout.write(f"Updated: {updated}")
        self.stdout.write(f"Unchanged: {unchanged}")
        self.stdout.write(f"Missing in DB: {len(missing)}")
        if missing:
            show = sorted(set(missing))
            self.stdout.write("  " + ", ".join(show[:25]) + (" ..." if len(show) > 25 else ""))
        if multi_match:
            self.stdout.write(self.style.WARNING(f"Multiple matches (applied to all): {len(multi_match)}"))
            for name, count in sorted(multi_match, key=lambda x: (-x[1], x[0]))[:15]:
                self.stdout.write(f"  {name}: {count}")
