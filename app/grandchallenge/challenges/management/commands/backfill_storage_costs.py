import math
from collections import namedtuple

from django.core.management import BaseCommand

from grandchallenge.challenges.costs import (
    allocate_storage_costs_for_challenge,
)
from grandchallenge.challenges.models import Challenge
from grandchallenge.invoices.models import Invoice

EURO_MILLICENTS = 100_000

BudgetImpact = namedtuple("BudgetImpact", ["before", "after"])


def available_total_euro_millicents(*, invoice, storage_cost_euro_millicents):
    if invoice.is_budget_authorized and not invoice.is_expired:
        approved = (
            invoice.compute_costs_euros + invoice.storage_costs_euros
        ) * EURO_MILLICENTS
        consumed = min(
            invoice.compute_cost_euro_millicents
            + storage_cost_euro_millicents,
            approved,
        )
        return approved - consumed
    else:
        return 0


def budget_impact(*, challenge, new_costs):
    """
    The available budget in euro millicents before (compute only, as used
    for gating today) and after (compute and storage, with the new costs).
    """
    invoices = challenge.invoices.all()

    return BudgetImpact(
        before=sum(
            invoice.available_compute_cost_euro_millicents
            for invoice in invoices
        ),
        after=sum(
            available_total_euro_millicents(
                invoice=invoice,
                storage_cost_euro_millicents=new_costs.get(
                    invoice, invoice.storage_cost_euro_millicents
                ),
            )
            for invoice in invoices
        ),
    )


def is_accepting_submissions(*, challenge):
    return any(
        phase.submission_period_is_open_now
        and phase.submissions_limit_per_user_per_period > 0
        for phase in challenge.phase_set.all()
    )


class Command(BaseCommand):
    help = (
        "Assigns the storage that challenges currently use to their "
        "authorized invoices, expired invoices included, and reports the "
        "effect on the available budget. Running it again changes nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the changes without saving them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        prefix = "[DRY RUN] " if dry_run else ""

        challenges = list(
            Challenge.objects.with_invoices_with_utilization_priority()
            .filter(invoices__isnull=False)
            .distinct()
            .order_by("pk")
            .prefetch_related("phase_set")
            .only("pk", "short_name", "size_in_storage", "size_in_registry")
        )
        total = len(challenges)

        self.stdout.write(
            f"{prefix}Backfilling storage costs for {total} challenges"
        )

        changed = []
        gained = 0
        lost = 0
        out_of_budget = []

        for count, challenge in enumerate(challenges, start=1):
            new_costs = allocate_storage_costs_for_challenge(
                challenge=challenge, include_expired=True
            )
            impact = budget_impact(challenge=challenge, new_costs=new_costs)
            change = impact.after - impact.before

            gained += max(change, 0)
            lost += max(-change, 0)

            line = (
                f"[{count}/{total}] {challenge.short_name}: available budget "
                f"{impact.before / EURO_MILLICENTS:.2f} -> "
                f"{impact.after / EURO_MILLICENTS:.2f} EUR "
                f"({change / EURO_MILLICENTS:+.2f})"
            )

            if impact.before > 0 and impact.after <= 0:
                top_up = math.ceil(impact.before / EURO_MILLICENTS)
                accepting = is_accepting_submissions(challenge=challenge)
                out_of_budget.append((top_up, accepting))
                line += f" OUT OF BUDGET, top-up needed: {top_up} EUR"
                if accepting:
                    line += " (accepting submissions)"
                else:
                    pass
            else:
                pass

            self.stdout.write(line)

            for invoice, new_cost in new_costs.items():
                self.stdout.write(
                    f"    invoice {invoice.pk} "
                    f"({invoice.payment_type}/{invoice.payment_status}, "
                    f"expires {invoice.expires_on}): storage cost "
                    f"{invoice.storage_cost_euro_millicents} -> {new_cost} "
                    "euro millicents"
                )
                invoice.storage_cost_euro_millicents = new_cost
                changed.append(invoice)

        if dry_run:
            self.stdout.write(f"{prefix}Nothing was saved.")
        else:
            Invoice.objects.bulk_update(
                changed, ["storage_cost_euro_millicents"]
            )

        self.write_summary(
            changed=changed,
            gained=gained,
            lost=lost,
            out_of_budget=out_of_budget,
            prefix=prefix,
        )

    def write_summary(self, *, changed, gained, lost, out_of_budget, prefix):
        accepting_top_ups = [
            top_up for top_up, accepting in out_of_budget if accepting
        ]

        self.stdout.write(f"\n{prefix}Summary")
        self.stdout.write(
            f"Invoices {'to update' if prefix else 'updated'}: {len(changed)}"
        )
        self.stdout.write(
            f"Available budget gained: {gained / EURO_MILLICENTS:.2f} EUR, "
            f"lost: {lost / EURO_MILLICENTS:.2f} EUR"
        )
        self.stdout.write(
            f"Challenges running out of budget: {len(out_of_budget)}, "
            f"of which accepting submissions: {len(accepting_top_ups)}"
        )
        self.stdout.write(
            f"Top-ups needed: {sum(top_up for top_up, _ in out_of_budget)} "
            f"EUR in total, {sum(accepting_top_ups)} EUR for challenges "
            "accepting submissions"
        )
