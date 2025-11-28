import pytest

from grandchallenge.components.models import ComponentInterface
from grandchallenge.evaluation.utils import SubmissionKindChoices
from tests.algorithms_tests.factories import (
    AlgorithmFactory,
    AlgorithmInterfaceFactory,
)
from tests.archives_tests.factories import ArchiveFactory
from tests.components_tests.factories import (
    ComponentInterfaceExampleValueFactory,
    ComponentInterfaceFactory,
)
from tests.evaluation_tests.factories import PhaseFactory
from tests.factories import ChallengeFactory


@pytest.mark.django_db
def test_get_challenge_pack_context():
    challenge = ChallengeFactory()
    inputs = [
        ComponentInterfaceFactory(kind=ComponentInterface.Kind.INTEGER),
        ComponentInterfaceFactory(kind=ComponentInterface.Kind.PANIMG_IMAGE),
    ]
    outputs = ComponentInterfaceFactory.create_batch(3)

    interface1 = AlgorithmInterfaceFactory(inputs=inputs, outputs=outputs)
    interface2 = AlgorithmInterfaceFactory(
        inputs=[inputs[1]], outputs=[outputs[2]]
    )

    # Add an example
    ComponentInterfaceExampleValueFactory(
        interface=inputs[0],
        value=87,
    )

    archive = ArchiveFactory()
    phase_1 = PhaseFactory(
        challenge=challenge,
        archive=archive,
        submission_kind=SubmissionKindChoices.ALGORITHM,
    )
    phase_2 = PhaseFactory(
        challenge=challenge,
        archive=archive,
        submission_kind=SubmissionKindChoices.ALGORITHM,
    )
    for phase in phase_1, phase_2:
        phase.algorithm_interfaces.set([interface1, interface2])
        phase.additional_evaluation_inputs.set([inputs[0]])
        phase.evaluation_outputs.add(outputs[0], outputs[1])

    # Setup phases that should not pass the filters
    phase_3 = PhaseFactory(
        challenge=challenge,
        archive=None,  # Hence should not be included
        submission_kind=SubmissionKindChoices.ALGORITHM,
    )
    PhaseFactory(
        challenge=challenge,
        submission_kind=SubmissionKindChoices.CSV,  # Hence should not be included
    )

    for phase in {phase_1, phase_2}:
        assert phase.forge_model.challenge.slug == challenge.slug

        algorithm_interface = phase.forge_model.algorithm_interfaces[0]

        # Test assigned example value
        example_values = [
            input.example_value
            for input in algorithm_interface.inputs
            if input.example_value
        ]
        assert example_values == [87]

        # Quick check on CI input and outputs
        input_slugs = [input.slug for input in algorithm_interface.inputs]
        assert len(input_slugs) == 2
        assert inputs[0].slug in input_slugs
        assert inputs[1].slug in input_slugs

        output_slugs = [output.slug for output in algorithm_interface.outputs]
        assert len(output_slugs) == len(outputs)
        assert outputs[0].slug in output_slugs
        assert outputs[1].slug in output_slugs
        assert outputs[2].slug in output_slugs

    with pytest.raises(NotImplementedError):
        phase_3.forge_model


@pytest.mark.django_db
def test_get_algorithm_template_context():
    algorithm = AlgorithmFactory()

    inputs = [
        ComponentInterfaceFactory(kind=ComponentInterface.Kind.INTEGER),
        ComponentInterfaceFactory(kind=ComponentInterface.Kind.STRING),
    ]
    outputs = ComponentInterfaceFactory.create_batch(3)
    interface1 = AlgorithmInterfaceFactory(inputs=inputs, outputs=outputs)
    interface2 = AlgorithmInterfaceFactory(
        inputs=[inputs[1]], outputs=[outputs[2]]
    )
    algorithm.interfaces.set([interface1, interface2])

    forge_model = algorithm.forge_model

    inputs = forge_model.algorithm_interfaces[0].inputs
    outputs = forge_model.algorithm_interfaces[0].inputs

    input_slugs = [input.slug for input in inputs]
    assert len(input_slugs) == len(inputs)
    assert inputs[0].slug in input_slugs
    assert inputs[1].slug in input_slugs

    output_slugs = [output.slug for output in outputs]
    assert output_slugs == [outputs[0].slug, outputs[1].slug]

    # Test adding default examples
    assert inputs[0].example_value == 42
