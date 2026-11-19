import pytest

from grandchallenge.invoices.models import (
    _capacity_gb,
    allocate_storage_costs,
)
from tests.factories import ChallengeFactory
from tests.invoices_tests.factories import InvoiceFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def challenge():
    return ChallengeFactory()


def _invoice(
    *,
    challenge,
    compute_costs_euros=1,
    storage_costs_euros=0,
    compute_cost_euro_millicents=0,
    storage_cost_euro_millicents=0,
    storage_price_euro_millicents_per_gb=1_000,
):
    return InvoiceFactory(
        challenge=challenge,
        compute_costs_euros=compute_costs_euros,
        storage_costs_euros=storage_costs_euros,
        compute_cost_euro_millicents=compute_cost_euro_millicents,
        storage_cost_euro_millicents=storage_cost_euro_millicents,
        storage_price_euro_millicents_per_gb=storage_price_euro_millicents_per_gb,
    )


def _invoice_with_10_gb_capacity(*, challenge):
    return _invoice(
        challenge=challenge,
        compute_cost_euro_millicents=80_000,
        storage_cost_euro_millicents=10_000,
    )


def _invoice_with_100_gb_capacity(*, challenge):
    return _invoice(challenge=challenge)


def _costs_after(*, invoices, new_costs):
    return [
        new_costs.get(invoice.pk, invoice.storage_cost_euro_millicents)
        for invoice in invoices
    ]


def test_fills_invoices_in_order(challenge):
    invoices = [
        _invoice_with_10_gb_capacity(challenge=challenge),
        _invoice_with_100_gb_capacity(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=40)

    # 10 GB fill the first invoice (10,000 existing + 10,000 new), the other
    # 30 GB go to the second
    assert new_costs == {invoices[0].pk: 20_000, invoices[1].pk: 30_000}


def test_overflow_lands_on_last_invoice(challenge):
    invoices = [
        _invoice_with_10_gb_capacity(challenge=challenge),
        _invoice_with_100_gb_capacity(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=150)

    # 10 GB fill the first invoice, 100 GB fill the second and the remaining
    # 40 GB overflow onto the second
    assert _costs_after(invoices=invoices, new_costs=new_costs) == [
        20_000,
        140_000,
    ]


def test_empty_invoice_list_returns_no_changes():
    assert allocate_storage_costs(invoices=[], unassigned_gb=10) == {}


@pytest.mark.parametrize("unassigned_gb", (0, -0.5, -35))
def test_non_positive_unassigned_gb_changes_nothing(challenge, unassigned_gb):
    invoices = [
        _invoice_with_10_gb_capacity(challenge=challenge),
        _invoice_with_100_gb_capacity(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(
        invoices=invoices, unassigned_gb=unassigned_gb
    )

    assert new_costs == {}


def test_invoices_from_different_challenges_raise_error():
    invoices = [InvoiceFactory(), InvoiceFactory()]

    with pytest.raises(ValueError):
        allocate_storage_costs(invoices=invoices, unassigned_gb=10)


def test_invoices_are_not_modified(challenge):
    invoices = [
        _invoice_with_10_gb_capacity(challenge=challenge),
        _invoice_with_100_gb_capacity(challenge=challenge),
    ]

    allocate_storage_costs(invoices=invoices, unassigned_gb=40)

    assert [invoice.storage_cost_euro_millicents for invoice in invoices] == [
        10_000,
        0,
    ]


def test_only_changed_invoices_are_returned(challenge):
    full_invoice = _invoice(
        challenge=challenge, compute_cost_euro_millicents=100_000
    )
    other_invoice = _invoice(challenge=challenge)

    new_costs = allocate_storage_costs(
        invoices=[full_invoice, other_invoice], unassigned_gb=10
    )

    assert new_costs == {other_invoice.pk: 10_000}


def test_existing_storage_cost_reduces_capacity(challenge):
    invoices = [
        _invoice(challenge=challenge, storage_cost_euro_millicents=80_000),
        _invoice(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=50)

    # Invoice 1 has 20,000 millicents (20 GB) left, the rest lands on invoice 2
    assert _costs_after(invoices=invoices, new_costs=new_costs) == [
        100_000,
        30_000,
    ]


def test_uncapped_compute_cost_reduces_capacity(challenge):
    invoices = [
        _invoice(challenge=challenge, compute_cost_euro_millicents=60_000),
        _invoice(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=50)

    # Invoice 1 has 40,000 millicents (40 GB) left, the rest lands on invoice 2
    assert _costs_after(invoices=invoices, new_costs=new_costs) == [
        40_000,
        10_000,
    ]


def test_compute_cost_above_approved_total_leaves_no_capacity(challenge):
    invoices = [
        _invoice(challenge=challenge, compute_cost_euro_millicents=250_000),
        _invoice(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=10)

    assert _costs_after(invoices=invoices, new_costs=new_costs) == [0, 10_000]


def test_storage_costs_euros_count_towards_approved_total(challenge):
    invoices = [
        _invoice(
            challenge=challenge, compute_costs_euros=0, storage_costs_euros=1
        ),
        _invoice(challenge=challenge),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=150)

    assert _costs_after(invoices=invoices, new_costs=new_costs) == [
        100_000,
        50_000,
    ]


def test_mixed_prices_overflow_priced_at_last_invoices_own_price(challenge):
    invoices = [
        _invoice(
            challenge=challenge, storage_price_euro_millicents_per_gb=4_000
        ),
        _invoice(challenge=challenge, compute_cost_euro_millicents=90_000),
    ]

    new_costs = allocate_storage_costs(invoices=invoices, unassigned_gb=50)

    # Invoice 1 takes 25 GB (100,000), invoice 2 takes 10 GB (10,000),
    # the remaining 15 GB overflow onto invoice 2 at 1,000 per GB
    assert _costs_after(invoices=invoices, new_costs=new_costs) == [
        100_000,
        25_000,
    ]


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


UNASSIGNED_GB_VALUES = (-5, 0, 0.5, 35, 80, 1_000.25)


def _accounted_gb(*, invoices, costs):
    return sum(
        cost / invoice.storage_price_euro_millicents_per_gb
        for invoice, cost in zip(invoices, costs, strict=True)
    )


@pytest.mark.parametrize("unassigned_gb", UNASSIGNED_GB_VALUES)
@pytest.mark.parametrize(
    "make_invoices",
    (_partially_consumed_invoices, _exhausted_credit_invoices),
)
def test_storage_costs_never_decrease(challenge, make_invoices, unassigned_gb):
    invoices = make_invoices(challenge=challenge)

    new_costs = allocate_storage_costs(
        invoices=invoices, unassigned_gb=unassigned_gb
    )

    for invoice, cost in zip(
        invoices,
        _costs_after(invoices=invoices, new_costs=new_costs),
        strict=True,
    ):
        assert cost >= invoice.storage_cost_euro_millicents


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
    challenge, make_invoices, unassigned_gb
):
    invoices = make_invoices(challenge=challenge)
    original_costs = [
        invoice.storage_cost_euro_millicents for invoice in invoices
    ]
    size_gb = (
        _accounted_gb(invoices=invoices, costs=original_costs) + unassigned_gb
    )

    new_costs = allocate_storage_costs(
        invoices=invoices, unassigned_gb=unassigned_gb
    )

    remaining_unassigned_gb = size_gb - _accounted_gb(
        invoices=invoices,
        costs=_costs_after(invoices=invoices, new_costs=new_costs),
    )

    # Only negative unassigned GB (a challenge's data has shrunk) can remain
    assert remaining_unassigned_gb <= 0


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
    challenge, make_invoices, unassigned_gb
):
    invoices = make_invoices(challenge=challenge)

    new_costs = allocate_storage_costs(
        invoices=invoices, unassigned_gb=unassigned_gb
    )

    for invoice in invoices:
        invoice.storage_cost_euro_millicents = new_costs.get(
            invoice.pk, invoice.storage_cost_euro_millicents
        )

    for index, invoice in enumerate(invoices):
        earlier_invoice_has_capacity_left = any(
            _capacity_gb(invoice=earlier_invoice) > 0
            for earlier_invoice in invoices[:index]
        )
        if earlier_invoice_has_capacity_left:
            assert invoice.pk not in new_costs
