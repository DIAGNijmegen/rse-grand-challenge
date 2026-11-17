import datetime
import math
from collections import OrderedDict
from typing import NamedTuple

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.db.models import F

from grandchallenge.evaluation.templatetags.evaluation_extras import (
    get_jsonpath,
)


class Metric(NamedTuple):
    path: str
    reverse: bool


class Positions(NamedTuple):
    ranks: dict[str, float]
    rank_scores: dict[str, float]
    rank_per_metric: dict[str, dict[str, float]]


class EvaluationMetric(NamedTuple):
    evaluation_pk: str
    creator: str
    created: datetime.datetime
    metric_scores: dict[Metric, float]


def get(inputs):
    """Substitute for queryset.get when the qs already exists."""
    if len(inputs) == 1:
        return inputs[0]
    elif len(inputs) == 0:
        raise ObjectDoesNotExist
    else:
        raise MultipleObjectsReturned


def is_valid_metric_score(*, score):
    # bool is a subclass of int, but is not a meaningful score
    if isinstance(score, bool):
        return False
    elif isinstance(score, int):
        # Checked separately as math.isfinite raises an OverflowError for
        # ints that are too large to be converted to a float
        return True
    elif isinstance(score, float):
        # NaN cannot be ordered or compared for ties, and infinity is not a
        # meaningful score
        return math.isfinite(score)
    else:
        return False


def get_valid_evaluation_metrics(*, evaluations, metric_lookups):
    from grandchallenge.components.models import ComponentInterfaceValue

    evaluation_metric_civs = ComponentInterfaceValue.objects.filter(
        interface__slug="metrics-json-file",
        evaluation_evaluations_as_output__in={
            evaluation.pk for evaluation in evaluations if evaluation.published
        },
    ).annotate(
        evaluation_pk=F("evaluation_evaluations_as_output"),
        creator=F("evaluation_evaluations_as_output__submission__creator"),
        created=F("evaluation_evaluations_as_output__submission__created"),
    )

    evaluation_metrics = []

    for evaluation_metric_civ in evaluation_metric_civs.iterator(
        chunk_size=100
    ):
        evaluation_metric_scores = {}

        for metric_lookup in metric_lookups:
            evaluation_metric_scores[metric_lookup] = get_jsonpath(
                evaluation_metric_civ.value,
                metric_lookup.path,
            )

        if all(
            is_valid_metric_score(score=score)
            for score in evaluation_metric_scores.values()
        ):
            evaluation_metrics.append(
                EvaluationMetric(
                    evaluation_pk=evaluation_metric_civ.evaluation_pk,
                    creator=evaluation_metric_civ.creator,
                    created=evaluation_metric_civ.created,
                    metric_scores=evaluation_metric_scores,
                )
            )

    return evaluation_metrics


def rank_results(*, evaluation_metrics, score_method) -> Positions:
    """Determine the overall rank for each result."""
    if not evaluation_metrics or not evaluation_metrics[0].metric_scores:
        # Nothing to rank, so no result is ranked. All of the evaluation
        # metrics have the same metrics extracted, so only check the first.
        return Positions(ranks={}, rank_scores={}, rank_per_metric={})

    rank_per_metric = _get_rank_per_metric(
        evaluation_metrics=evaluation_metrics
    )

    rank_scores = {
        pk: score_method([*metrics.values()])
        for pk, metrics in rank_per_metric.items()
    }

    return Positions(
        ranks=_scores_to_ranks(rank_scores=rank_scores, reverse=False),
        rank_scores=rank_scores,
        rank_per_metric=rank_per_metric,
    )


def _get_rank_per_metric(*, evaluation_metrics):
    """
    Takes results and calculates the rank for each of the individual metrics

    Returns a dictionary where the key is the pk of the result, and the
    values is another dictionary where the key is the path of the metric and
    the value is the rank of this result for this metric
    """
    metric_rank = {}

    for metric in evaluation_metrics[0].metric_scores.keys():
        rank_scores = {
            evaluation_metric.evaluation_pk: evaluation_metric.metric_scores[
                metric
            ]
            for evaluation_metric in evaluation_metrics
        }

        metric_rank[metric.path] = _scores_to_ranks(
            rank_scores=rank_scores,
            reverse=metric.reverse,
        )

    return {
        evaluation_metric.evaluation_pk: {
            metric_path: ranks[evaluation_metric.evaluation_pk]
            for metric_path, ranks in metric_rank.items()
        }
        for evaluation_metric in evaluation_metrics
    }


def _scores_to_ranks(*, rank_scores, reverse):
    """
    Go from a score (a scalar) to a rank (integer). If two scalars are the
    same then they will have the same rank.

    Takes a dictionary where the keys are the pk of the results and the values
    are the scores.

    Outputs a dictionary where they keys are the pk of the results and the
    values are the ranks.
    """
    scores = OrderedDict(
        sorted(
            rank_scores.items(),
            key=lambda t: t[1],
            reverse=reverse,
        )
    )

    ranks = {}
    current_score = current_rank = None

    for idx, (pk, score) in enumerate(scores.items()):
        if score != current_score:
            current_score = score
            current_rank = idx + 1

        ranks[pk] = current_rank

    return ranks


class StatusChoices(models.TextChoices):
    OPEN = "OPEN", "Accepting submissions now"
    OPENING_SOON = "OPEN_SOON", "Opening submissions soon"
    CLOSED = "CLOSED", "Not accepting submissions"
    COMPLETED = "COMPLETED", "Completed"


class SubmissionKindChoices(models.IntegerChoices):
    CSV = 1, "Predictions"
    # ZIP = 2, "ZIP"
    ALGORITHM = 3, "Algorithm"
