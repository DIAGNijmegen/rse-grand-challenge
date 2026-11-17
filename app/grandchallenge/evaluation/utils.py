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


def get(inputs):
    """Substitute for queryset.get when the qs already exists."""
    if len(inputs) == 1:
        return inputs[0]
    elif len(inputs) == 0:
        raise ObjectDoesNotExist
    else:
        raise MultipleObjectsReturned


def get_metric_scores(*, evaluation_pks, metrics):
    from grandchallenge.components.models import ComponentInterfaceValue

    evaluation_metric_civs = ComponentInterfaceValue.objects.filter(
        interface__slug="metrics-json-file",
        evaluation_evaluations_as_output__in=evaluation_pks,
    ).annotate(evaluation_pk=F("evaluation_evaluations_as_output"))

    metric_scores = {}

    for evaluation_metric_civ in evaluation_metric_civs.iterator(
        chunk_size=100
    ):
        evaluation_metric_scores = {}

        for metric in metrics:
            evaluation_metric_scores[metric] = get_jsonpath(
                evaluation_metric_civ.value,
                metric.path,
            )

        if all(
            isinstance(score, (int, float))
            for score in evaluation_metric_scores.values()
        ):
            metric_scores[evaluation_metric_civ.evaluation_pk] = (
                evaluation_metric_scores
            )

    return metric_scores


def rank_results(
    *, evaluations, metrics, metric_scores, score_method
) -> Positions:
    """Determine the overall rank for each result."""
    evaluations = _filter_valid_results(
        evaluations=evaluations, metric_scores=metric_scores
    )

    rank_per_metric = _get_rank_per_metric(
        evaluations=evaluations, metrics=metrics, metric_scores=metric_scores
    )

    rank_scores = {
        pk: score_method([*metrics.values()])
        for pk, metrics in rank_per_metric.items()
    }

    return Positions(
        ranks=_scores_to_ranks(
            evaluation_metric_score=rank_scores, reverse=False
        ),
        rank_scores=rank_scores,
        rank_per_metric=rank_per_metric,
    )


def _filter_valid_results(*, evaluations, metric_scores):
    """Ensure that all the metrics are in every result."""
    return [e for e in evaluations if e.pk in metric_scores]


def _get_rank_per_metric(*, evaluations, metrics, metric_scores):
    """
    Takes results and calculates the rank for each of the individual metrics

    Returns a dictionary where the key is the pk of the result, and the
    values is another dictionary where the key is the path of the metric and
    the value is the rank of this result for this metric
    """
    metric_rank = {}
    for metric in metrics:
        evaluation_metric_score = {
            evaluation_pk: evaluation_metric_scores[metric]
            for evaluation_pk, evaluation_metric_scores in metric_scores.items()
        }

        metric_rank[metric.path] = _scores_to_ranks(
            evaluation_metric_score=evaluation_metric_score,
            reverse=metric.reverse,
        )

    return {
        e.pk: {
            metric_path: ranks[e.pk]
            for metric_path, ranks in metric_rank.items()
        }
        for e in evaluations
    }


def _scores_to_ranks(*, evaluation_metric_score, reverse):
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
            evaluation_metric_score.items(),
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
