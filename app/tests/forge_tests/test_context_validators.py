from contextlib import nullcontext

import pytest
from pydantic_core import ValidationError

from grandchallenge.forge.models import ForgeAlgorithm, ForgePhase
from tests.forge_tests.utils import (
    algorithm_template_context_factory,
    phase_context_factory,
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
            phase_context_factory(),
            nullcontext(),
        ],
        [
            phase_context_factory(
                evaluation_additional_inputs=[],
                evaluation_additional_outputs=[],
            ),
            nullcontext(),
        ],
    ],
)
def test_pack_context_validity(json_context, condition):
    with condition:
        ForgePhase(**json_context)


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
