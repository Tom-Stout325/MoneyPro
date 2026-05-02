# MoneyPro S3 Business Backups Patch

Adds:

- Dashboard Admin button between Reports and More
- `/dashboard/backups/` admin backup page
- Individual CSV table downloads
- Download All Excel workbook
- Save-to-S3/default-storage button
- Backup history table
- Backup cleanup button
- `BackupLog` model and admin registration
- `create_business_backups` management command for Heroku Scheduler
- `MONEYPRO_BACKUP_RETENTION_DAYS` setting, default `7`
- `openpyxl==3.1.5` in requirements

## Install

Unzip this patch over your project root, then run:

```bash
git add .
git commit -m "Add S3 business backup history and retention"
git push
heroku run -a moneypro -- python manage.py migrate
```

## Manual backup command

Back up all businesses:

```bash
heroku run -a moneypro -- python manage.py create_business_backups
```

Back up one business:

```bash
heroku run -a moneypro -- python manage.py create_business_backups --business-id 2
```

Use 5-day retention:

```bash
heroku run -a moneypro -- python manage.py create_business_backups --retention-days 5
```

Cleanup only:

```bash
heroku run -a moneypro -- python manage.py create_business_backups --cleanup-only --retention-days 5
```

## Heroku Scheduler

Create a daily Heroku Scheduler job, for example at 2:00 AM:

```bash
python manage.py create_business_backups --retention-days 5
```

Do not include `heroku run` inside the Scheduler command.

## Optional config var

```bash
heroku config:set -a moneypro MONEYPRO_BACKUP_RETENTION_DAYS=5
```

The UI button and command use Django's configured `default_storage`. In production with `USE_S3=True`, that saves to your S3 media bucket. Locally, it saves to local media storage.
