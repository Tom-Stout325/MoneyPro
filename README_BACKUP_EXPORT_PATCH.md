# MoneyPro Backup Export Patch

## What this patch adds

- Adds an **Admin** button on the MoneyPro Dashboard between **Reports** and **More**.
- Adds a new dashboard admin backup page at:

  `/dashboard/backups/`

- Lists all business-scoped MoneyPro tables detected in the project.
- Adds a **CSV download** button for each table.
- Adds a **Download All** button that downloads one `.xlsx` workbook with:
  - a `Manifest` tab
  - one worksheet per exported table
  - row counts for each table

## Files changed/added

- `core/business_backup_exports.py`
- `dashboard/views.py`
- `dashboard/urls.py`
- `dashboard/templates/dashboard/home.html`
- `dashboard/templates/dashboard/business_backup_admin.html`
- `requirements.txt`

## Dependency added

```txt
openpyxl>=3.1.5
```

After unzipping the patch, run:

```bash
pip install -r requirements.txt
```

For Heroku, commit and push as usual. No migrations are required.

## Heroku notes

After deploying, if needed:

```bash
heroku run -a moneypro -- python manage.py check
```
