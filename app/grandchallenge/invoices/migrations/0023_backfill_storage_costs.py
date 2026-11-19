from django.db import migrations
from django.db.models import Prefetch, Q

from grandchallenge.invoices.models import allocate_storage_costs

GIGABYTE = 1024**3
PROGRESS_INTERVAL = 50


def is_budget_authorized(*, invoice, has_paid_prepaid_invoice):
    if invoice.payment_status == "CANCELLED":
        return False
    elif invoice.payment_type == "COMPLIMENTARY":
        return True
    elif invoice.payment_type == "PREPAID":
        return invoice.payment_status == "PAID"
    elif invoice.payment_type == "POSTPAID":
        return invoice.payment_status == "PAID" or has_paid_prepaid_invoice
    else:
        return False


def authorized_invoices(*, invoices):
    has_paid_prepaid_invoice = any(
        invoice.payment_type == "PREPAID"
        and invoice.payment_status == "PAID"
        and invoice.compute_costs_euros > 0
        for invoice in invoices
    )

    return [
        invoice
        for invoice in invoices
        if is_budget_authorized(
            invoice=invoice, has_paid_prepaid_invoice=has_paid_prepaid_invoice
        )
    ]


def unassigned_gb_for_challenge(*, challenge, invoices):
    size_gb = (
        challenge.size_in_storage + challenge.size_in_registry
    ) / GIGABYTE
    accounted_gb = sum(
        invoice.storage_cost_euro_millicents
        / invoice.storage_price_euro_millicents_per_gb
        for invoice in invoices
        if invoice.storage_price_euro_millicents_per_gb > 0
    )
    return size_gb - accounted_gb


def backfill(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")  # noqa: N806
    Challenge = apps.get_model("challenges", "Challenge")  # noqa: N806

    changed = []

    challenges = (
        Challenge.objects.filter(invoices__isnull=False)
        .distinct()
        .only("pk", "size_in_storage", "size_in_registry")
        # prefetch invoices in utlization priority order
        .prefetch_related(
            Prefetch(
                "invoices",
                queryset=Invoice.objects.annotate(
                    is_paid=Q(payment_status="PAID")
                ).order_by("-is_paid", "expires_on", "created"),
            )
        )
    )

    total = len(challenges)
    print(f"\nBackfilling storage costs for {total} challenges")

    for count, challenge in enumerate(challenges, start=1):
        if count % PROGRESS_INTERVAL == 0 or count == total:
            print(f"Processed {count}/{total} challenges")

        invoices = authorized_invoices(invoices=challenge.invoices.all())

        if not invoices:
            print(
                f"Challenge {challenge.pk} has no authorized invoices, "
                "skipping"
            )
            continue
        else:
            new_costs = allocate_storage_costs(
                invoices=invoices,
                unassigned_gb=unassigned_gb_for_challenge(
                    challenge=challenge, invoices=invoices
                ),
            )

            for invoice in invoices:
                if invoice.pk in new_costs:
                    invoice.storage_cost_euro_millicents = new_costs[
                        invoice.pk
                    ]
                    changed.append(invoice)

    print(f"Updating storage costs of {len(changed)} invoices")
    Invoice.objects.bulk_update(changed, ["storage_cost_euro_millicents"])
    print("Done")


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0022_invoice_storage_cost_euro_millicents_and_more"),
        (
            "challenges",
            "0083_alter_challengerequest_inference_time_average_minutes_for_tasks",
        ),
    ]

    operations = [
        migrations.RunPython(
            backfill, migrations.RunPython.noop, elidable=True
        ),
    ]
