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


class EvaluationScore(NamedTuple):
    evaluation_pk: str
    creator: str
    created: datetime.datetime
    score_per_metric: dict[Metric, float]


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


def get_evaluation_scores(*, evaluations, metric_lookups):
    from grandchallenge.components.models import ComponentInterfaceValue

    evaluation_scores = []

    if not metric_lookups:
        # Nothing to do
        return evaluation_scores

    evaluation_metrics_civs = ComponentInterfaceValue.objects.filter(
        interface__slug="metrics-json-file",
        evaluation_evaluations_as_output__in={
            evaluation.pk for evaluation in evaluations if evaluation.published
        },
    ).annotate(
        evaluation_pk=F("evaluation_evaluations_as_output"),
        creator=F("evaluation_evaluations_as_output__submission__creator"),
        created=F("evaluation_evaluations_as_output__submission__created"),
    )

    for evaluation_metrics_civ in evaluation_metrics_civs.iterator(
        chunk_size=100
    ):
        score_per_metric = {}

        for metric_lookup in metric_lookups:
            score_per_metric[metric_lookup] = get_jsonpath(
                evaluation_metrics_civ.value,
                metric_lookup.path,
            )

        if all(
            is_valid_metric_score(score=score)
            for score in score_per_metric.values()
        ):
            evaluation_scores.append(
                EvaluationScore(
                    evaluation_pk=evaluation_metrics_civ.evaluation_pk,
                    creator=evaluation_metrics_civ.creator,
                    created=evaluation_metrics_civ.created,
                    score_per_metric=score_per_metric,
                )
            )

    return evaluation_scores


def rank_results(*, evaluation_scores, score_method) -> Positions:
    """Determine the overall rank for each result."""
    if not evaluation_scores or not evaluation_scores[0].score_per_metric:
        # Nothing to rank, so no result is ranked. All of the evaluation
        # metrics have the same metrics extracted, so only check the first.
        return Positions(ranks={}, rank_scores={}, rank_per_metric={})

    rank_per_metric = _get_rank_per_metric(evaluation_scores=evaluation_scores)

    rank_scores = {
        pk: score_method([*metrics.values()])
        for pk, metrics in rank_per_metric.items()
    }

    return Positions(
        ranks=_scores_to_ranks(rank_scores=rank_scores, reverse=False),
        rank_scores=rank_scores,
        rank_per_metric=rank_per_metric,
    )


def _get_rank_per_metric(*, evaluation_scores):
    """
    Takes results and calculates the rank for each of the individual metrics

    Returns a dictionary where the key is the pk of the result, and the
    values is another dictionary where the key is the path of the metric and
    the value is the rank of this result for this metric
    """
    metric_rank = {}

    for metric in evaluation_scores[0].score_per_metric.keys():
        rank_scores = {
            evaluation_score.evaluation_pk: evaluation_score.score_per_metric[
                metric
            ]
            for evaluation_score in evaluation_scores
        }

        metric_rank[metric.path] = _scores_to_ranks(
            rank_scores=rank_scores,
            reverse=metric.reverse,
        )

    return {
        evaluation_score.evaluation_pk: {
            metric_path: ranks[evaluation_score.evaluation_pk]
            for metric_path, ranks in metric_rank.items()
        }
        for evaluation_score in evaluation_scores
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


class SubmissionCommentsChoices(models.TextChoices):
    OFF = "off", "Off"
    OPTIONAL = "opt", "Optional"
    REQUIRED = "req", "Required"


class SubmissionKindChoices(models.IntegerChoices):
    CSV = 1, "Predictions"
    # ZIP = 2, "ZIP"
    ALGORITHM = 3, "Algorithm"
