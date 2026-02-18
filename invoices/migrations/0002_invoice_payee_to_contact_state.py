from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """State-only update: Invoice.payee now points to ledger.Contact.

    Database remains unchanged because ledger.Contact maps to the existing
    ledger_payee table via db_table.
    """

    dependencies = [
        ("ledger", "0003_contacts_state_rename"),
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="invoice",
                    name="payee",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="ledger.contact",
                    ),
                ),
            ],
        ),
    ]
