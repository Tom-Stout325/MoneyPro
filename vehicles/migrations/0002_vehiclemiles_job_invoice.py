from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0001_initial"),
        ("ledger", "0001_initial"),
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclemiles",
            name="job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="mileage_entries",
                to="ledger.job",
            ),
        ),
        migrations.AddField(
            model_name="vehiclemiles",
            name="invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="mileage_entries",
                to="invoices.invoice",
            ),
        ),
    ]
