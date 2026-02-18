from django.db import migrations


class Migration(migrations.Migration):
    """Rename Payee -> Contact at the Django *state* level.

    Database tables/columns are intentionally left unchanged for stability:
    - Contact uses db_table='ledger_payee'
    - ContactTaxProfile uses db_table='ledger_payeetaxprofile'
    - ContactTaxProfile.contact uses db_column='payee_id'

    This avoids cross-app FK churn (e.g., invoices.Invoice.payee) while letting the codebase
    consistently use the 'Contact' naming.
    """

    dependencies = [
        ("ledger", "0002_job_upgrade"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="Payee", new_name="Contact"),
                migrations.RenameModel(old_name="PayeeTaxProfile", new_name="ContactTaxProfile"),
                migrations.RenameField(model_name="contacttaxprofile", old_name="payee", new_name="contact"),
            ],
        ),
    ]
