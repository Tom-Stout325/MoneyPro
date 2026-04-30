# MoneyPro Mileage / Vehicle Requirement Patch

This patch makes mileage and vehicle-related expense entry consistent:

- Mileage entries explicitly require `VehicleMiles.vehicle`.
- Mileage entries do not reference or require an asset.
- Existing vehicle-related ledger subcategory rules are migrated from `requires_asset=True` to `requires_vehicle=True`.
- `ledger/data/subcategory_rules.json` is updated so future `apply_subcategory_rules` runs keep vehicle categories tied to vehicles instead of assets.

## Files changed

- `vehicles/forms.py`
- `ledger/data/subcategory_rules.json`
- `ledger/migrations/0003_vehicle_subcategory_requires_vehicle.py`

## After unzipping over the project

Run migrations locally and on Heroku:

```bash
python manage.py migrate
heroku run -a moneypro -- python manage.py migrate
```

The migration updates these subcategories across existing businesses:

- Vehicle: Equipment Purchases
- Vehicle: Gas
- Vehicle: Loan Interest
- Vehicle: Loan Payments
- Vehicle: Maintenance
- Vehicle: Other Expenses
- Vehicle: Repairs
