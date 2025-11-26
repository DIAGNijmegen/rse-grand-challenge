from contextlib import nullcontext

import pytest
from pydantic_core import ValidationError

from grandchallenge.forge.models import ForgeAlgorithm, ForgeChallenge
from tests.forge_tests.utils import (
    algorithm_template_context_factory,
    pack_context_factory,
)


@pytest.mark.parametrize(
    "json_context,condition",
    [
        [{}, pytest.raises(ValidationError)],
        [{"challenge": []}, pytest.raises(ValidationError)],
        [
            {"challenge": {}},
            pytest.raises(ValidationError),
        ],
        [
            pack_context_factory(),
            nullcontext(),
        ],
        [
            pack_context_factory(phases=[]),
            nullcontext(),
        ],
    ],
)
def test_pack_context_validity(json_context, condition):
    with condition:
        ForgeChallenge(**json_context)


@pytest.mark.parametrize(
    "json_context,condition",
    [
        [{}, pytest.raises(ValidationError)],
        [{"algorithm": []}, pytest.raises(ValidationError)],
        [
            {"algorithm": {}},
            pytest.raises(ValidationError),
        ],
        [
            algorithm_template_context_factory(),
            nullcontext(),
        ],
    ],
)
def test_algorithm_template_context_validity(json_context, condition):
    with condition:
        ForgeAlgorithm(**json_context)
