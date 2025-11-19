from contextlib import nullcontext

import pytest

from grandchallenge.forge.exceptions import InvalidContextError
from grandchallenge.forge.schemas import (
    validate_algorithm_template_context,
    validate_pack_context,
)
from tests.forge_tests.utils import (
    algorithm_template_context_factory,
    pack_context_factory,
)


@pytest.mark.parametrize(
    "json_context,condition",
    [
        [{}, pytest.raises(InvalidContextError)],
        ["", pytest.raises(InvalidContextError)],
        [{"challenge": []}, pytest.raises(InvalidContextError)],
        [
            {"challenge": {}},
            pytest.raises(InvalidContextError),
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
        validate_pack_context(json_context)


@pytest.mark.parametrize(
    "json_context,condition",
    [
        [{}, pytest.raises(InvalidContextError)],
        ["", pytest.raises(InvalidContextError)],
        [{"algorithm": []}, pytest.raises(InvalidContextError)],
        [
            {"algorithm": {}},
            pytest.raises(InvalidContextError),
        ],
        [
            algorithm_template_context_factory(),
            nullcontext(),
        ],
    ],
)
def test_algorithm_template_context_validity(json_context, condition):
    with condition:
        validate_algorithm_template_context(json_context)
