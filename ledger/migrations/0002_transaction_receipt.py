from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="receipt",
            field=models.FileField(blank=True, null=True, upload_to="receipts/transactions/"),
        ),
    ]
