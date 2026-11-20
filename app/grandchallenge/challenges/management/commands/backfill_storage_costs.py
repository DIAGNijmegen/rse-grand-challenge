import math
from typing import NamedTuple

from django.core.management import BaseCommand, CommandError

from grandchallenge.challenges.costs import (
    allocate_storage_costs_for_challenge,
)
from grandchallenge.challenges.models import Challenge
from grandchallenge.invoices.models import Invoice

EURO_MILLICENTS = 100_000
PROGRESS_INTERVAL = 50


class BudgetImpact(NamedTuple):
    before: int
    after: int


class UnallocatedStorage(NamedTuple):
    gb: float
    reason: str


class ChallengeResult(NamedTuple):
    short_name: str
    budget_before: int
    budget_after: int
    is_accepting_submissions: bool
    unallocated_gb: float
    unallocated_reason: str


def available_total_euro_millicents(*, invoice, storage_cost_euro_millicents):
    if invoice.is_budget_authorized and not invoice.is_expired:
        approved = (
            invoice.compute_costs_euros + invoice.storage_costs_euros
        ) * EURO_MILLICENTS
        consumed = (
            invoice.compute_cost_euro_millicents + storage_cost_euro_millicents
        )
        return max(approved - consumed, 0)
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


def unallocated_storage(*, challenge):
    """
    The storage the allocator had nowhere to put. Any overflow lands on the
    last authorized invoice, so storage is only left over if there is no
    authorized invoice.
    """
    invoices = challenge.invoices.all()
    unassigned_gb = challenge.unassigned_storage_gb

    if unassigned_gb <= 0:
        return UnallocatedStorage(gb=0, reason="")
    elif not invoices:
        return UnallocatedStorage(gb=unassigned_gb, reason="no invoices")
    elif not any(invoice.is_budget_authorized for invoice in invoices):
        return UnallocatedStorage(
            gb=unassigned_gb, reason="no authorized invoice"
        )
    else:
        return UnallocatedStorage(gb=0, reason="")


def euros(*, euro_millicents):
    return f"{euro_millicents / EURO_MILLICENTS:,.2f}"


def euro_change(*, euro_millicents):
    return f"{euro_millicents / EURO_MILLICENTS:+,.2f}"


def is_out_of_budget(*, result):
    return result.budget_before > 0 and result.budget_after <= 0


def top_up_euros(*, result):
    return math.ceil(result.budget_before / EURO_MILLICENTS)


def validate_simulated_price(*, simulated_price, dry_run):
    if simulated_price is None:
        pass
    elif not dry_run:
        raise CommandError(
            "--storage-price-euro-millicents-per-gb requires --dry-run"
        )
    elif simulated_price <= 0:
        raise CommandError(
            "--storage-price-euro-millicents-per-gb must be above 0"
        )
    else:
        pass


def allocate(*, challenge, simulated_price):
    """
    Allocates the storage of the challenge, expired invoices included. A
    simulated price replaces the price on the invoices in memory only.
    """
    if simulated_price is None:
        pass
    else:
        for invoice in challenge.invoices.all():
            invoice.storage_price_euro_millicents_per_gb = simulated_price

    return allocate_storage_costs_for_challenge(
        challenge=challenge, include_expired=True
    )


def challenge_result(*, challenge, new_costs):
    impact = budget_impact(challenge=challenge, new_costs=new_costs)
    unallocated = unallocated_storage(challenge=challenge)

    return ChallengeResult(
        short_name=challenge.short_name,
        budget_before=impact.before,
        budget_after=impact.after,
        is_accepting_submissions=is_accepting_submissions(challenge=challenge),
        unallocated_gb=unallocated.gb,
        unallocated_reason=unallocated.reason,
    )


def table(*, header, alignments, rows):
    lines = [
        f"| {' | '.join(header)} |",
        f"|{'|'.join(alignments)}|",
    ]
    lines.extend(f"| {' | '.join(row)} |" for row in rows)
    return lines


class Command(BaseCommand):
    help = (
        "Assigns the storage that challenges currently use to their "
        "authorized invoices, expired invoices included, and prints a "
        "Markdown report of the effect on the available budget. Progress "
        "goes to stderr, so the report can be redirected to a file. Running "
        "it again changes nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the changes without saving them",
        )
        parser.add_argument(
            "--storage-price-euro-millicents-per-gb",
            type=int,
            help=(
                "Only with --dry-run: simulate this storage price instead of "
                "the price on each invoice"
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        simulated_price = options["storage_price_euro_millicents_per_gb"]
        self.stderr.style_func = None

        validate_simulated_price(
            simulated_price=simulated_price, dry_run=dry_run
        )

        challenges = list(
            Challenge.objects.with_invoices_with_utilization_priority()
            .order_by("short_name")
            .prefetch_related("phase_set")
            .only("pk", "short_name", "size_in_storage", "size_in_registry")
        )
        total = len(challenges)

        changed = []
        results = []

        for count, challenge in enumerate(challenges, start=1):
            new_costs = allocate(
                challenge=challenge, simulated_price=simulated_price
            )
            results.append(
                challenge_result(challenge=challenge, new_costs=new_costs)
            )

            for invoice, new_cost in new_costs.items():
                invoice.storage_cost_euro_millicents = new_cost
                changed.append(invoice)

            if count % PROGRESS_INTERVAL == 0 or count == total:
                self.stderr.write(f"Processed {count}/{total} challenges")
            else:
                pass

        if dry_run:
            pass
        else:
            Invoice.objects.bulk_update(
                changed, ["storage_cost_euro_millicents"]
            )

        for line in self.report(
            results=results,
            updated=len(changed),
            dry_run=dry_run,
            simulated_price=simulated_price,
        ):
            self.stdout.write(line)

    def report(self, *, results, updated, dry_run, simulated_price):
        out_of_budget = sorted(
            (result for result in results if is_out_of_budget(result=result)),
            key=lambda result: -result.budget_before,
        )
        reduced = sorted(
            (
                result
                for result in results
                if result.budget_after < result.budget_before
                and not is_out_of_budget(result=result)
            ),
            key=lambda result: result.budget_after - result.budget_before,
        )
        increased = sorted(
            (
                result
                for result in results
                if result.budget_after > result.budget_before
            ),
            key=lambda result: result.budget_before - result.budget_after,
        )
        unchanged = [
            result
            for result in results
            if result.budget_after == result.budget_before
        ]
        unallocated = sorted(
            (result for result in results if result.unallocated_reason),
            key=lambda result: -result.unallocated_gb,
        )

        if dry_run:
            mode = (
                f"**Dry run, nothing was saved.** {updated} invoices would "
                "get storage costs."
            )
        else:
            mode = f"**Applied.** {updated} invoices got storage costs."

        if simulated_price is None:
            price = "Storage price: the price frozen on each invoice."
        else:
            price = (
                f"**Simulated storage price: {simulated_price:,} euro "
                f"millicents per GB ({simulated_price / EURO_MILLICENTS:.2f} "
                "EUR)**, instead of the price on each invoice."
            )

        top_ups = sum(top_up_euros(result=result) for result in out_of_budget)
        accepting_top_ups = sum(
            top_up_euros(result=result)
            for result in out_of_budget
            if result.is_accepting_submissions
        )
        accepting_count = sum(
            1 for result in out_of_budget if result.is_accepting_submissions
        )
        reduced_total = sum(
            result.budget_after - result.budget_before
            for result in reduced + out_of_budget
        )
        increased_total = sum(
            result.budget_after - result.budget_before for result in increased
        )

        lines = [
            "# Storage cost backfill report",
            "",
            mode,
            "",
            price,
            "",
            "Budget before is the available compute budget. Budget after is the available compute "
            "and storage budget with the new storage costs. Amounts are in EUR.",
            "",
            "## Summary",
            "",
            f"- Challenges processed: {len(results)}",
            f"- Out of budget: {len(out_of_budget)} challenges, "
            f"{accepting_count} of them accepting submissions",
            f"- Top-ups needed: {top_ups} EUR in total, "
            f"{accepting_top_ups} EUR for challenges accepting submissions",
            f"- Budget reduced: {len(reduced) + len(out_of_budget)} "
            "challenges (including the ones out of budget), "
            f"{euro_change(euro_millicents=reduced_total)} EUR in total",
            f"- Budget increased: {len(increased)} challenges, "
            f"{euro_change(euro_millicents=increased_total)} EUR in total",
            f"- Budget unchanged: {len(unchanged)} challenges",
            f"- Unallocated storage: {len(unallocated)} challenges, "
            f"{sum(result.unallocated_gb for result in unallocated):,.2f} GB "
            "in total",
            "",
        ]

        lines += self.section(
            title=f"Out of budget ({len(out_of_budget)})",
            description=(
                "Challenges that had budget before and have none after. The "
                "top-up is the budget before rounded up to whole euros, to "
                "put on a complimentary invoice."
            ),
            header=(
                "Challenge",
                "Budget before",
                "Budget after",
                "Top-up",
                "Accepting submissions",
            ),
            alignments=(":---", "---:", "---:", "---:", ":---"),
            rows=[
                (
                    result.short_name,
                    euros(euro_millicents=result.budget_before),
                    euros(euro_millicents=result.budget_after),
                    str(top_up_euros(result=result)),
                    str(result.is_accepting_submissions),
                )
                for result in out_of_budget
            ],
        )
        lines += self.section(
            title=f"Budget reduced ({len(reduced)})",
            description=(
                "Challenges that still have budget after, but less than "
                "before. Largest reduction first."
            ),
            header=("Challenge", "Budget before", "Budget after", "Change"),
            alignments=(":---", "---:", "---:", "---:"),
            rows=[
                (
                    result.short_name,
                    euros(euro_millicents=result.budget_before),
                    euros(euro_millicents=result.budget_after),
                    euro_change(
                        euro_millicents=result.budget_after
                        - result.budget_before
                    ),
                )
                for result in reduced
            ],
        )
        lines += self.section(
            title=f"Budget increased ({len(increased)})",
            description=(
                "Challenges whose reserved storage budget is larger than the "
                "storage costs they get. Largest increase first."
            ),
            header=("Challenge", "Budget before", "Budget after", "Change"),
            alignments=(":---", "---:", "---:", "---:"),
            rows=[
                (
                    result.short_name,
                    euros(euro_millicents=result.budget_before),
                    euros(euro_millicents=result.budget_after),
                    euro_change(
                        euro_millicents=result.budget_after
                        - result.budget_before
                    ),
                )
                for result in increased
            ],
        )
        lines += self.section(
            title=f"Unallocated storage ({len(unallocated)})",
            description=(
                "Challenges with data that could not be put on any invoice. "
                "It will be charged to their next authorized invoice. "
                "Largest first."
            ),
            header=("Challenge", "Unallocated", "Reason"),
            alignments=(":---", "---:", ":---"),
            rows=[
                (
                    result.short_name,
                    f"{result.unallocated_gb:,.2f} GB",
                    result.unallocated_reason,
                )
                for result in unallocated
            ],
        )

        return lines

    def section(self, *, title, description, header, alignments, rows):
        lines = [f"## {title}", "", description, ""]

        if rows:
            lines += table(header=header, alignments=alignments, rows=rows)
        else:
            lines.append("None.")

        lines.append("")
        return lines
