from datetime import timedelta

import pytest
from django.utils.timezone import now

from grandchallenge.challenges.costs import (
    allocate_storage_costs_for_challenge,
)
from grandchallenge.challenges.models import Challenge
from grandchallenge.invoices.models import Invoice
from tests.factories import ChallengeFactory
from tests.invoices_tests.factories import InvoiceFactory

GIGABYTE = 1024**3


def _invoice(
    *,
    challenge,
    expires_in_days=365,
    compute_costs_euros=1,
    storage_costs_euros=0,
    storage_price_euro_millicents_per_gb=1_000,
    **kwargs,
):
    # By default 1 euro of compute budget and a price of 1,000 per GB give
    # an invoice a capacity of 100 GB
    return InvoiceFactory(
        challenge=challenge,
        expires_on=now().date() + timedelta(days=expires_in_days),
        compute_costs_euros=compute_costs_euros,
        storage_costs_euros=storage_costs_euros,
        storage_price_euro_millicents_per_gb_per_year=storage_price_euro_millicents_per_gb,
        storage_retention_years=1,
        **kwargs,
    )


def _prefetched(*, challenge):
    return Challenge.objects.with_invoices_with_utilization_priority().get(
        pk=challenge.pk
    )


def _accounted_gb(*, invoices, new_costs=None):
    new_costs = new_costs or {}
    return sum(
        new_costs.get(invoice, invoice.storage_cost_euro_millicents)
        / invoice.storage_price_euro_millicents_per_gb_for_retention_period
        for invoice in invoices
    )


def _invoice_with_10_gb_capacity(*, challenge):
    return _invoice(
        challenge=challenge,
        compute_cost_euro_millicents=80_000,
        storage_cost_euro_millicents=10_000,
    )


def _invoice_with_100_gb_capacity(*, challenge):
    return _invoice(challenge=challenge)


@pytest.mark.django_db
def test_fills_authorized_invoices_in_priority_order():
    challenge = ChallengeFactory(size_in_storage=250 * GIGABYTE)
    later_invoice = _invoice(challenge=challenge, expires_in_days=200)
    earlier_invoice = _invoice(challenge=challenge, expires_in_days=100)
    cancelled_invoice = _invoice(
        challenge=challenge,
        expires_in_days=50,
        payment_status=Invoice.PaymentStatusChoices.CANCELLED,
    )
    # Authorized by the paid prepaid invoices, but not paid itself, so it
    # comes last even though it expires first
    postpaid_invoice = _invoice(
        challenge=challenge,
        expires_in_days=60,
        payment_type=Invoice.PaymentTypeChoices.POSTPAID,
        payment_status=Invoice.PaymentStatusChoices.INITIALIZED,
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {
        earlier_invoice: 100_000,
        later_invoice: 100_000,
        postpaid_invoice: 50_000,
    }
    assert cancelled_invoice not in new_costs


@pytest.mark.django_db
def test_allocation_makes_no_queries_for_a_prefetched_challenge(
    django_assert_num_queries,
):
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)
    _invoice(challenge=challenge)
    _invoice(challenge=challenge, expires_in_days=100)
    prefetched_challenge = _prefetched(challenge=challenge)

    with django_assert_num_queries(0):
        allocate_storage_costs_for_challenge(challenge=prefetched_challenge)


@pytest.mark.django_db
def test_unassigned_storage_gb_counts_authorized_invoices_expired_included():
    challenge = ChallengeFactory(size_in_storage=50 * GIGABYTE)
    _invoice(challenge=challenge, storage_cost_euro_millicents=10_000)
    _invoice(
        challenge=challenge,
        expires_in_days=-10,
        storage_cost_euro_millicents=5_000,
    )
    _invoice(
        challenge=challenge,
        payment_status=Invoice.PaymentStatusChoices.CANCELLED,
        storage_cost_euro_millicents=20_000,
    )

    # 50 GB in total, 10 GB and 5 GB on the authorized invoices, the
    # cancelled invoice does not count
    assert _prefetched(challenge=challenge).unassigned_storage_gb == 35


@pytest.mark.django_db
def test_unassigned_storage_gb_is_negative_when_data_has_shrunk():
    challenge = ChallengeFactory(size_in_storage=5 * GIGABYTE)
    _invoice(challenge=challenge, storage_cost_euro_millicents=10_000)

    assert _prefetched(challenge=challenge).unassigned_storage_gb == -5


@pytest.mark.django_db
def test_unassigned_storage_gb_ignores_registry_storage():
    challenge = ChallengeFactory(
        size_in_storage=10 * GIGABYTE, size_in_registry=5 * GIGABYTE
    )
    _invoice(challenge=challenge, storage_cost_euro_millicents=4_000)

    assert _prefetched(challenge=challenge).unassigned_storage_gb == 6


@pytest.mark.django_db
def test_challenge_without_authorized_invoice_changes_nothing():
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)
    _invoice(
        challenge=challenge,
        payment_status=Invoice.PaymentStatusChoices.CANCELLED,
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {}


@pytest.mark.django_db
def test_expired_invoice_counts_as_accounted_but_is_not_filled_by_default():
    challenge = ChallengeFactory(size_in_storage=30 * GIGABYTE)
    _invoice(
        challenge=challenge,
        expires_in_days=-10,
        storage_cost_euro_millicents=10_000,
    )
    active_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # 30 GB in total, 10 GB are already on the expired invoice
    assert new_costs == {active_invoice: 20_000}


@pytest.mark.django_db
def test_include_expired_fills_expired_invoices_first():
    challenge = ChallengeFactory(size_in_storage=150 * GIGABYTE)
    expired_invoice = _invoice(challenge=challenge, expires_in_days=-10)
    active_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge), include_expired=True
    )

    assert new_costs == {expired_invoice: 100_000, active_invoice: 50_000}


@pytest.mark.django_db
def test_only_expired_invoices_receive_nothing_by_default():
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)
    _invoice(challenge=challenge, expires_in_days=-10)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {}


@pytest.mark.django_db
def test_allocating_again_after_saving_changes_nothing():
    challenge = ChallengeFactory(size_in_storage=150 * GIGABYTE)
    _invoice(challenge=challenge, expires_in_days=100)
    _invoice(challenge=challenge, expires_in_days=200)

    for invoice, new_cost in allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge), include_expired=True
    ).items():
        invoice.storage_cost_euro_millicents = new_cost
        invoice.save(update_fields=("storage_cost_euro_millicents",))

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge), include_expired=True
    )

    assert new_costs == {}


@pytest.mark.django_db
def test_fills_invoices_in_order():
    challenge = ChallengeFactory(size_in_storage=50 * GIGABYTE)
    first_invoice = _invoice_with_10_gb_capacity(challenge=challenge)
    second_invoice = _invoice_with_100_gb_capacity(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # 50 GB in total, 10 GB are already on the first invoice. 10 GB fill the
    # first invoice (10,000 existing + 10,000 new), the other 30 GB go to the
    # second
    assert new_costs == {first_invoice: 20_000, second_invoice: 30_000}


@pytest.mark.django_db
def test_overflow_lands_on_last_invoice():
    challenge = ChallengeFactory(size_in_storage=160 * GIGABYTE)
    first_invoice = _invoice_with_10_gb_capacity(challenge=challenge)
    second_invoice = _invoice_with_100_gb_capacity(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # 160 GB in total, 10 GB are already on the first invoice. 10 GB fill the
    # first invoice, 100 GB fill the second and the remaining 40 GB overflow
    # onto the second
    assert new_costs == {first_invoice: 20_000, second_invoice: 140_000}


@pytest.mark.django_db
def test_challenge_without_invoices_changes_nothing():
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "size_in_storage_gb",
    (
        # The first invoice already carries 10 GB, so this is exactly what is
        # accounted for, a bit less, and nothing
        10,
        9,
        0,
    ),
)
def test_size_at_or_below_accounted_gb_changes_nothing(size_in_storage_gb):
    challenge = ChallengeFactory(
        size_in_storage=size_in_storage_gb * GIGABYTE,
    )
    _invoice_with_10_gb_capacity(challenge=challenge)
    _invoice_with_100_gb_capacity(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {}


@pytest.mark.django_db
def test_only_changed_invoices_are_returned():
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)
    _invoice(challenge=challenge, compute_cost_euro_millicents=100_000)
    other_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {other_invoice: 10_000}


@pytest.mark.django_db
def test_existing_storage_cost_reduces_capacity():
    challenge = ChallengeFactory(size_in_storage=130 * GIGABYTE)
    first_invoice = _invoice(
        challenge=challenge, storage_cost_euro_millicents=80_000
    )
    second_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # 130 GB in total, 80 GB are already on the first invoice, which has
    # 20,000 millicents (20 GB) left, the rest lands on the second
    assert new_costs == {first_invoice: 100_000, second_invoice: 30_000}


@pytest.mark.django_db
def test_uncapped_compute_cost_reduces_capacity():
    challenge = ChallengeFactory(size_in_storage=50 * GIGABYTE)
    first_invoice = _invoice(
        challenge=challenge, compute_cost_euro_millicents=60_000
    )
    second_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # The first invoice has 40,000 millicents (40 GB) left, the rest lands on
    # the second
    assert new_costs == {first_invoice: 40_000, second_invoice: 10_000}


@pytest.mark.django_db
def test_compute_cost_above_approved_total_leaves_no_capacity():
    challenge = ChallengeFactory(size_in_storage=10 * GIGABYTE)
    _invoice(challenge=challenge, compute_cost_euro_millicents=250_000)
    second_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # The first invoice is unchanged, so it is not returned
    assert new_costs == {second_invoice: 10_000}


@pytest.mark.django_db
def test_storage_costs_euros_count_towards_approved_total():
    challenge = ChallengeFactory(size_in_storage=150 * GIGABYTE)
    first_invoice = _invoice(
        challenge=challenge, compute_costs_euros=0, storage_costs_euros=1
    )
    second_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    assert new_costs == {first_invoice: 100_000, second_invoice: 50_000}


@pytest.mark.django_db
def test_mixed_prices_overflow_priced_at_last_invoices_own_price():
    challenge = ChallengeFactory(size_in_storage=50 * GIGABYTE)
    first_invoice = _invoice(
        challenge=challenge, storage_price_euro_millicents_per_gb=4_000
    )
    second_invoice = _invoice(
        challenge=challenge, compute_cost_euro_millicents=90_000
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    # The first invoice takes 25 GB (100,000), the second takes 10 GB
    # (10,000), the remaining 15 GB overflow onto the second at 1,000 per GB
    assert new_costs == {first_invoice: 100_000, second_invoice: 25_000}


def _partially_consumed_invoices(*, challenge):
    return [
        _invoice(challenge=challenge, storage_cost_euro_millicents=30_000),
        _invoice(challenge=challenge, compute_cost_euro_millicents=50_000),
        _invoice(challenge=challenge),
    ]


def _mixed_price_invoices(*, challenge):
    return [
        _invoice(
            challenge=challenge, storage_price_euro_millicents_per_gb=2_000
        ),
        _invoice(
            challenge=challenge,
            compute_cost_euro_millicents=40_000,
            storage_price_euro_millicents_per_gb=2_500,
        ),
        _invoice(
            challenge=challenge, storage_price_euro_millicents_per_gb=4_000
        ),
    ]


def _exhausted_credit_invoices(*, challenge):
    return [
        _invoice(challenge=challenge, storage_cost_euro_millicents=100_000),
        _invoice(challenge=challenge, compute_cost_euro_millicents=100_000),
        _invoice(challenge=challenge),
    ]


def _over_consumed_invoices(*, challenge):
    return [
        _invoice(challenge=challenge, compute_cost_euro_millicents=250_000),
        _invoice(challenge=challenge, compute_cost_euro_millicents=130_000),
    ]


# Negative values mean that the data of the challenge has shrunk
UNASSIGNED_GB_VALUES = (-5, 0, 0.5, 35, 80, 1_000.25)


@pytest.mark.django_db
@pytest.mark.parametrize("unassigned_gb", UNASSIGNED_GB_VALUES)
@pytest.mark.parametrize(
    "make_invoices",
    (_partially_consumed_invoices, _exhausted_credit_invoices),
)
def test_storage_costs_never_decrease(make_invoices, unassigned_gb):
    challenge = ChallengeFactory()
    invoices = make_invoices(challenge=challenge)
    size_in_bytes = round(
        max(_accounted_gb(invoices=invoices) + unassigned_gb, 0) * GIGABYTE
    )
    Challenge.objects.filter(pk=challenge.pk).update(
        size_in_storage=size_in_bytes,
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    for invoice in invoices:
        assert (
            new_costs.get(invoice, invoice.storage_cost_euro_millicents)
            >= invoice.storage_cost_euro_millicents
        )


@pytest.mark.django_db
@pytest.mark.parametrize("unassigned_gb", UNASSIGNED_GB_VALUES)
@pytest.mark.parametrize(
    "make_invoices",
    (
        _partially_consumed_invoices,
        _mixed_price_invoices,
        _exhausted_credit_invoices,
        _over_consumed_invoices,
    ),
)
def test_no_unassigned_gb_remain_after_allocation(
    make_invoices, unassigned_gb
):
    challenge = ChallengeFactory()
    invoices = make_invoices(challenge=challenge)
    size_in_bytes = round(
        max(_accounted_gb(invoices=invoices) + unassigned_gb, 0) * GIGABYTE
    )
    Challenge.objects.filter(pk=challenge.pk).update(
        size_in_storage=size_in_bytes,
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    remaining_unassigned_gb = size_in_bytes / GIGABYTE - _accounted_gb(
        invoices=invoices, new_costs=new_costs
    )

    # Only negative unassigned GB (a challenge's data has shrunk) can remain
    assert remaining_unassigned_gb <= 1e-9


@pytest.mark.django_db
@pytest.mark.parametrize("unassigned_gb", UNASSIGNED_GB_VALUES)
@pytest.mark.parametrize(
    "make_invoices",
    (
        _partially_consumed_invoices,
        _mixed_price_invoices,
        _exhausted_credit_invoices,
    ),
)
def test_invoice_receives_gb_only_after_earlier_invoices_are_full(
    make_invoices, unassigned_gb
):
    challenge = ChallengeFactory()
    # The invoices are created in priority order: same expiry, same status
    invoices = make_invoices(challenge=challenge)
    size_in_bytes = round(
        max(_accounted_gb(invoices=invoices) + unassigned_gb, 0) * GIGABYTE
    )
    Challenge.objects.filter(pk=challenge.pk).update(
        size_in_storage=size_in_bytes,
    )

    new_costs = allocate_storage_costs_for_challenge(
        challenge=_prefetched(challenge=challenge)
    )

    for invoice in invoices:
        invoice.storage_cost_euro_millicents = new_costs.get(
            invoice, invoice.storage_cost_euro_millicents
        )

    for index, invoice in enumerate(invoices):
        earlier_invoice_has_capacity_left = any(
            earlier_invoice.capacity_gb > 0
            for earlier_invoice in invoices[:index]
        )
        if earlier_invoice_has_capacity_left:
            assert invoice not in new_costs
