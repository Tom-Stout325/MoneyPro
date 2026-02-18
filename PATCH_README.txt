MoneyPro: Harden Seeding + Rebuild Defaults Patch
=================================================

What this patch does
- Hardens Schedule C seeding by wrapping seed_schedule_c_defaults in a DB transaction (@transaction.atomic).
- Ensures Seed Defaults is POST-only.
- Adds a new Dashboard action: Rebuild Defaults (destructive).
  - Only allowed when there are NO transactions for the active business.
  - Deletes all Categories + SubCategories for the business, then re-seeds defaults.
- Adds a "Rebuild Defaults" button next to the existing Seed/Re-Seed button.

How to apply
1) Unzip this patch over your project root.
2) Restart server.
No migrations required.

Notes
- Rebuild Defaults is intentionally blocked once you have transactions to avoid orphaning data.
  Use Re-Seed to fill in missing defaults after that.
