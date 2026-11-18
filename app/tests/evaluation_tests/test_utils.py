import datetime

import pytest

from grandchallenge.components.models import (
    ComponentInterface,
    ComponentInterfaceValue,
)
from grandchallenge.evaluation.models import Evaluation, Phase
from grandchallenge.evaluation.tasks import (
    calculate_ranks,
    filter_by_creators_best,
)
from grandchallenge.evaluation.utils import (
    EvaluationScore,
    Positions,
    is_valid_metric_score,
    rank_results,
)
from tests.evaluation_tests.factories import EvaluationFactory, PhaseFactory
from tests.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "score_method, a_order, b_order, expected_ranks, expected_rank_scores",
    (
        (
            Phase.ABSOLUTE,
            Phase.DESCENDING,
            Phase.DESCENDING,
            [5, 3, 1, 2, 3, 0, 0, 0],
            [5, 3, 1, 2, 3, 0, 0, 0],
        ),
        (
            Phase.ABSOLUTE,
            Phase.DESCENDING,
            Phase.ASCENDING,
            [5, 3, 1, 2, 3, 0, 0, 0],
            [5, 3, 1, 2, 3, 0, 0, 0],
        ),
        (
            Phase.MEDIAN,
            Phase.DESCENDING,
            Phase.DESCENDING,
            [5, 4, 1, 1, 1, 0, 0, 0],
            [5, 3.5, 2, 2, 2, 0, 0, 0],
        ),
        (
            Phase.MEDIAN,
            Phase.DESCENDING,
            Phase.ASCENDING,
            [3, 2, 1, 3, 5, 0, 0, 0],
            [3, 2.5, 2, 3, 4, 0, 0, 0],
        ),
        (
            Phase.MEAN,
            Phase.DESCENDING,
            Phase.DESCENDING,
            [5, 4, 1, 1, 1, 0, 0, 0],
            [5, 3.5, 2, 2, 2, 0, 0, 0],
        ),
        (
            Phase.MEAN,
            Phase.DESCENDING,
            Phase.ASCENDING,
            [3, 2, 1, 3, 5, 0, 0, 0],
            [3, 2.5, 2, 3, 4, 0, 0, 0],
        ),
        (
            Phase.ABSOLUTE,
            Phase.ASCENDING,
            Phase.DESCENDING,
            [1, 2, 5, 4, 2, 0, 0, 0],
            [1, 2, 5, 4, 2, 0, 0, 0],
        ),
        (
            Phase.ABSOLUTE,
            Phase.ASCENDING,
            Phase.ASCENDING,
            [1, 2, 5, 4, 2, 0, 0, 0],
            [1, 2, 5, 4, 2, 0, 0, 0],
        ),
        (
            Phase.MEDIAN,
            Phase.ASCENDING,
            Phase.DESCENDING,
            [2, 2, 5, 2, 1, 0, 0, 0],
            [3, 3, 4, 3, 1.5, 0, 0, 0],
        ),
        (
            Phase.MEDIAN,
            Phase.ASCENDING,
            Phase.ASCENDING,
            [1, 2, 4, 4, 3, 0, 0, 0],
            [1, 2, 4, 4, 3.5, 0, 0, 0],
        ),
        (
            Phase.MEAN,
            Phase.ASCENDING,
            Phase.DESCENDING,
            [2, 2, 5, 2, 1, 0, 0, 0],
            [3, 3, 4, 3, 1.5, 0, 0, 0],
        ),
        (
            Phase.MEAN,
            Phase.ASCENDING,
            Phase.ASCENDING,
            [1, 2, 4, 4, 3, 0, 0, 0],
            [1, 2, 4, 4, 3.5, 0, 0, 0],
        ),
    ),
)
def test_calculate_ranks(
    django_assert_max_num_queries,
    score_method,
    a_order,
    b_order,
    expected_ranks,
    expected_rank_scores,
):
    phase = PhaseFactory()

    results = [
        # Warning: Do not change these values without updating the
        # expected above.
        {"a": 0.0, "b": 0.0},
        {"a": 0.5, "b": 0.2},
        {"a": 1.0, "b": 0.3},
        {"a": 0.7, "b": 0.4},
        {"a": 0.5, "b": 0.5},
        # Following two are invalid as they are incomplete
        {"a": 1.0},
        {"b": 0.3},
        # Add a valid, but unpublished result
        {"a": 0.1, "b": 0.1},
    ]

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for _ in range(len(results))
    ]

    for e, r in zip(queryset, results, strict=True):
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value=r,
            )
        )

    # Unpublish the result
    queryset[-1].published = False
    queryset[-1].save()

    # Setup Phase
    phase.score_jsonpath = "a"
    phase.scoring_method_choice = score_method
    phase.score_default_sort = a_order
    phase.extra_results_columns = [
        {"path": "b", "title": "b", "order": b_order}
    ]
    phase.save()

    with django_assert_max_num_queries(10):
        calculate_ranks(phase_pk=phase.pk)

    assert_ranks(
        queryset,
        expected_ranks,
        expected_rank_scores,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "score_method, extra_results_columns, expected_ranks, expected_rank_scores",
    (
        (
            Phase.ABSOLUTE,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": False,
                }
            ],
            only_a_expected_ranks := [5, 3, 1, 2, 3, 0],
            only_a_expected_rank_score := [5, 3, 1, 2, 3, 0],
        ),
        (
            Phase.ABSOLUTE,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": True,
                }
            ],
            only_a_expected_ranks,
            only_a_expected_rank_score,
        ),
        (
            Phase.MEDIAN,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": False,
                }
            ],
            [5, 4, 1, 1, 1, 0],
            [5, 3.5, 2, 2, 2, 0],
        ),
        (
            Phase.MEDIAN,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": True,
                }
            ],
            only_a_expected_ranks,
            only_a_expected_rank_score,
        ),
        (
            Phase.MEAN,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": False,
                }
            ],
            [5, 4, 1, 1, 1, 0],
            [5, 3.5, 2, 2, 2, 0],
        ),
        (
            Phase.MEAN,
            [
                {
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                    "exclude_from_ranking": True,
                }
            ],
            only_a_expected_ranks,
            only_a_expected_rank_score,
        ),
        (
            Phase.MEAN,
            [
                {  # Check if by default it is not excluded from ranking
                    "path": "b",
                    "title": "b",
                    "order": Phase.DESCENDING,
                }
            ],
            [5, 4, 1, 1, 1, 0],
            [5, 3.5, 2, 2, 2, 0],
        ),
    ),
)
def test_calculate_ranks_with_exclusion(
    django_assert_max_num_queries,
    score_method,
    extra_results_columns,
    expected_ranks,
    expected_rank_scores,
):
    phase = PhaseFactory()

    results = [
        # Warning: Do not change this values without updating the
        # expected_ranks/expected_rank_scores above.
        {"a": 0.0, "b": 0.0},
        {"a": 0.5, "b": 0.2},
        {"a": 1.0, "b": 0.3},
        {"a": 0.7, "b": 0.4},
        {"a": 0.5, "b": 0.5},
        {"b": 0.3},  # Incomplete and should not be processed
    ]

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for _ in range(len(results))
    ]

    for e, r in zip(queryset, results, strict=True):
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value=r,
            )
        )

    phase.score_jsonpath = "a"
    phase.scoring_method_choice = score_method
    phase.score_default_sort = Phase.DESCENDING
    phase.extra_results_columns = extra_results_columns

    phase.save()

    with django_assert_max_num_queries(10):
        assert calculate_ranks(phase_pk=phase.pk) is None

    assert_ranks(
        queryset,
        expected_ranks,
        expected_rank_scores,
    )


@pytest.mark.django_db
def test_results_display():
    phase = PhaseFactory()

    user1 = UserFactory()
    user2 = UserFactory()

    metrics = "metrics"
    creator = "creator"

    results = [
        {metrics: {"b": 0.3}, creator: user1},  # Invalid result
        {metrics: {"a": 0.6}, creator: user1},
        {metrics: {"a": 0.4}, creator: user1},
        {metrics: {"a": 0.2}, creator: user1},
        {metrics: {"a": 0.1}, creator: user2},
        {metrics: {"a": 0.5}, creator: user2},
        {metrics: {"a": 0.3}, creator: user2},
    ]

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            submission__creator=r[creator],
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for r in results
    ]

    for e, r in zip(queryset, results, strict=True):
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value=r[metrics],
            )
        )

    phase.score_jsonpath = "a"
    phase.result_display_choice = Phase.ALL
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [0, 1, 3, 5, 6, 2, 4]
    assert_ranks(queryset, expected_ranks)

    phase.result_display_choice = Phase.MOST_RECENT
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [0, 0, 0, 2, 0, 0, 1]
    assert_ranks(queryset, expected_ranks)

    phase.result_display_choice = Phase.BEST
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [0, 1, 0, 0, 0, 2, 0]
    assert_ranks(queryset, expected_ranks)

    # now test reverse order
    phase.score_default_sort = phase.ASCENDING
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [0, 0, 0, 2, 1, 0, 0]
    assert_ranks(queryset, expected_ranks)

    phase.result_display_choice = Phase.MOST_RECENT
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [0, 0, 0, 1, 0, 0, 2]
    assert_ranks(queryset, expected_ranks)


@pytest.mark.django_db
def test_null_results():
    phase = PhaseFactory()

    results = [{"a": 0.6}, {"a": None}]

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for _ in range(len(results))
    ]

    for e, r in zip(queryset, results, strict=True):
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value=r,
            )
        )

    phase.score_jsonpath = "a"
    phase.result_display_choice = Phase.ALL
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    expected_ranks = [1, 0]
    assert_ranks(queryset, expected_ranks)


@pytest.mark.parametrize(
    "evaluation_metrics",
    (
        [],
        [
            EvaluationScore(
                evaluation_pk="1",
                creator="a",
                created=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
                score_per_metric={},
            )
        ],
    ),
    ids=("no_evaluation_metrics", "no_metrics_per_evaluation"),
)
def test_rank_results_nothing_to_rank(evaluation_metrics):
    positions = rank_results(
        evaluation_scores=evaluation_metrics,
        score_method=max,
    )

    assert positions == Positions(ranks={}, rank_scores={}, rank_per_metric={})


@pytest.mark.parametrize(
    "score, expected",
    (
        (1, True),
        (0.5, True),
        (0, True),
        (-1.5, True),
        (True, False),
        (False, False),
        (float("nan"), False),
        (float("inf"), False),
        (float("-inf"), False),
        (10**400, True),  # Too large for a float, but still a valid int
        (None, False),
        ("1", False),
        ([1], False),
    ),
)
def test_is_valid_metric_score(score, expected):
    assert is_valid_metric_score(score=score) is expected


@pytest.mark.django_db
def test_boolean_results_are_invalid():
    phase = PhaseFactory()

    results = [{"a": 0.6}, {"a": True}, {"a": False}]

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for _ in range(len(results))
    ]

    for e, r in zip(queryset, results, strict=True):
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value=r,
            )
        )

    phase.score_jsonpath = "a"
    phase.result_display_choice = Phase.ALL
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    assert_ranks(queryset, [1, 0, 0])
    assert [e.invalid_metrics for e in queryset[:2]] == [set(), {"a"}]


@pytest.mark.django_db
def test_no_published_evaluations_resets_ranks():
    phase = PhaseFactory()

    evaluation = EvaluationFactory(
        submission__phase=phase,
        status=Evaluation.SUCCESS,
        time_limit=phase.evaluation_time_limit,
        rank=1,
        rank_score=1.0,
        rank_per_metric={"a": 1},
    )
    evaluation.published = False
    evaluation.save()
    evaluation.outputs.add(
        ComponentInterfaceValue.objects.create(
            interface=ComponentInterface.objects.get(slug="metrics-json-file"),
            value={"a": 0.6},
        )
    )

    phase.score_jsonpath = "a"
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    evaluation.refresh_from_db()
    assert evaluation.rank == 0
    assert evaluation.rank_score == 0.0
    assert evaluation.rank_per_metric == {}


@pytest.mark.django_db
def test_unknown_result_display_choice_raises(monkeypatch):
    phase = PhaseFactory()
    phase.result_display_choice = Phase.ALL
    phase.save()

    # Simulate the phase having a choice that calculate_ranks does not handle
    monkeypatch.setattr(Phase, "ALL", "unhandled")

    with pytest.raises(ValueError, match="result display choice"):
        calculate_ranks(phase_pk=phase.pk)


@pytest.mark.parametrize("reverse_input", (False, True))
def test_filter_by_creators_best_older_wins_ties(reverse_input):
    older = EvaluationScore(
        evaluation_pk="older",
        creator="a",
        created=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
        score_per_metric={},
    )
    newer = EvaluationScore(
        evaluation_pk="newer",
        creator="a",
        created=datetime.datetime(2020, 1, 2, tzinfo=datetime.UTC),
        score_per_metric={},
    )
    newest_but_better = EvaluationScore(
        evaluation_pk="newest_but_better",
        creator="b",
        created=datetime.datetime(2020, 1, 3, tzinfo=datetime.UTC),
        score_per_metric={},
    )
    older_but_worse = EvaluationScore(
        evaluation_pk="older_but_worse",
        creator="b",
        created=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
        score_per_metric={},
    )
    evaluation_metrics = [older, newer, newest_but_better, older_but_worse]

    if reverse_input:
        evaluation_metrics.reverse()

    best = filter_by_creators_best(
        evaluation_scores=evaluation_metrics,
        ranks={
            "older": 1,
            "newer": 1,
            "newest_but_better": 1,
            "older_but_worse": 2,
        },
    )

    assert {metric.evaluation_pk for metric in best} == {
        "older",
        "newest_but_better",
    }


@pytest.mark.django_db
def test_best_result_ties_won_by_older_submission():
    phase = PhaseFactory()
    user = UserFactory()

    queryset = [
        EvaluationFactory(
            submission__phase=phase,
            submission__creator=user,
            status=Evaluation.SUCCESS,
            time_limit=phase.evaluation_time_limit,
        )
        for _ in range(3)
    ]

    for e in queryset:
        e.outputs.add(
            ComponentInterfaceValue.objects.create(
                interface=ComponentInterface.objects.get(
                    slug="metrics-json-file"
                ),
                value={"a": 0.5},
            )
        )

    phase.score_jsonpath = "a"
    phase.result_display_choice = Phase.BEST
    phase.save()

    calculate_ranks(phase_pk=phase.pk)

    assert_ranks(queryset, [1, 0, 0])


def assert_ranks(queryset, expected_ranks, expected_rank_scores=None):
    for r in queryset:
        r.refresh_from_db()

    assert [r.rank for r in queryset] == expected_ranks

    if expected_rank_scores:
        assert [r.rank_score for r in queryset] == expected_rank_scores
