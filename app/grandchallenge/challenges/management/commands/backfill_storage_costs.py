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
            self.style.MIGRATE_HEADING(
                f"{prefix}Backfilling storage costs for {total} challenges"
            )
        )

        changed = []
        authorized_without_allocation = 0
        not_authorized = 0
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

            out_of_budget_note = self.out_of_budget_note(
                challenge=challenge, impact=impact, out_of_budget=out_of_budget
            )
            self.stdout.write(
                f"[{count}/{total}] "
                f"{self.style.MIGRATE_LABEL(challenge.short_name)}: "
                f"available budget {impact.before / EURO_MILLICENTS:.2f} -> "
                f"{impact.after / EURO_MILLICENTS:.2f} EUR "
                f"{self.colored_change(change=change)}{out_of_budget_note}"
            )

            for invoice in challenge.invoices.all():
                if invoice in new_costs:
                    status = self.style.SUCCESS(
                        f"storage cost {invoice.storage_cost_euro_millicents}"
                        f" -> {new_costs[invoice]} euro millicents"
                    )
                    invoice.storage_cost_euro_millicents = new_costs[invoice]
                    changed.append(invoice)
                elif invoice.is_budget_authorized:
                    status = "no storage cost allocated"
                    authorized_without_allocation += 1
                else:
                    status = self.style.WARNING(
                        "not authorized, no storage cost allocated"
                    )
                    not_authorized += 1

                self.stdout.write(
                    f"    invoice {invoice.pk} "
                    f"({invoice.payment_type}/{invoice.payment_status}, "
                    f"expires {invoice.expires_on}): {status}"
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"{prefix}Nothing was saved.")
            )
        else:
            Invoice.objects.bulk_update(
                changed, ["storage_cost_euro_millicents"]
            )

        self.write_summary(
            updated=len(changed),
            authorized_without_allocation=authorized_without_allocation,
            not_authorized=not_authorized,
            gained=gained,
            lost=lost,
            out_of_budget=out_of_budget,
            prefix=prefix,
        )

    def colored_change(self, *, change):
        text = f"({change / EURO_MILLICENTS:+.2f})"

        if change > 0:
            return self.style.SUCCESS(text)
        elif change < 0:
            return self.style.ERROR(text)
        else:
            return text

    def out_of_budget_note(self, *, challenge, impact, out_of_budget):
        if impact.before > 0 and impact.after <= 0:
            top_up = math.ceil(impact.before / EURO_MILLICENTS)
            accepting = is_accepting_submissions(challenge=challenge)
            out_of_budget.append((top_up, accepting))

            note = self.style.ERROR(
                f" OUT OF BUDGET, top-up needed: {top_up} EUR"
            )
            if accepting:
                note += self.style.WARNING(" (accepting submissions)")
            else:
                pass

            return note
        else:
            return ""

    def write_summary(
        self,
        *,
        updated,
        authorized_without_allocation,
        not_authorized,
        gained,
        lost,
        out_of_budget,
        prefix,
    ):
        accepting_top_ups = [
            top_up for top_up, accepting in out_of_budget if accepting
        ]

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{prefix}Summary"))
        self.stdout.write(
            f"Invoices {'to update' if prefix else 'updated'}: {updated}"
        )
        self.stdout.write(
            "Invoices without allocation: "
            f"{authorized_without_allocation + not_authorized} "
            f"({authorized_without_allocation} authorized with nothing to "
            f"allocate, {not_authorized} not authorized)"
        )
        self.stdout.write(
            "Available budget gained: "
            + self.style.SUCCESS(f"{gained / EURO_MILLICENTS:.2f} EUR")
            + ", lost: "
            + self.style.ERROR(f"{lost / EURO_MILLICENTS:.2f} EUR")
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
