from __future__ import annotations

from collections import defaultdict

from django.db import migrations, models
from django.db.models import Q


def populate_job_year_and_seq(apps, schema_editor):
    Job = apps.get_model("ledger", "Job")

    # Group jobs per (business_id, job_year) and assign sequential job_seq values.
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)

    # IMPORTANT: don't rely on the model's Meta.ordering here.
    # The Job model's ordering may reference fields that are being renamed in
    # this migration (e.g. title -> label), which can break queryset evaluation.
    for job in Job.objects.order_by("id").only("id", "business_id", "created_at"):
        year = job.created_at.year if getattr(job, "created_at", None) else 0
        groups[(job.business_id, year)].append(job.id)

    for (business_id, year), ids in groups.items():
        ids_sorted = sorted(ids)
        for i, job_id in enumerate(ids_sorted, start=1):
            Job.objects.filter(id=job_id).update(job_year=year, job_seq=i)


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0002_transaction_receipt"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="client_code",
            field=models.CharField(
                blank=True,
                help_text='Short code used for Job Numbers (locked once set). Example: "NHRA", "ESPN"',
                max_length=25,
            ),
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.UniqueConstraint(
                fields=("business", "client_code"),
                condition=Q(client_code__isnull=False) & ~Q(client_code=""),
                name="uniq_contact_client_code_per_business_nonblank",
            ),
        ),
        migrations.RenameField(
            model_name="job",
            old_name="title",
            new_name="label",
        ),
        migrations.AddField(
            model_name="job",
            name="job_year",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="job",
            name="job_seq",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AlterField(
            model_name="job",
            name="job_number",
            field=models.CharField(blank=True, editable=False, max_length=30),
        ),
        migrations.RunPython(populate_job_year_and_seq, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.UniqueConstraint(
                fields=("business", "job_year", "job_seq"),
                name="uniq_job_business_year_seq",
            ),
        ),
    ]
