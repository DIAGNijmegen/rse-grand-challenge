import factory

from grandchallenge.components.schemas import GPUTypeChoices
from grandchallenge.evaluation.models import (
    BatchJob,
    Evaluation,
    EvaluationGroundTruth,
    Method,
    Phase,
    Submission,
)
from tests.algorithms_tests.factories import (
    AlgorithmImageFactory,
    AlgorithmInterfaceFactory,
)
from tests.components_tests.factories import ComponentInterfaceValueFactory
from tests.factories import ChallengeFactory, UserFactory, hash_sha256


class PhaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Phase

    challenge = factory.SubFactory(ChallengeFactory)
    title = factory.sequence(lambda n: f"Phase {n}")


class MethodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Method

    creator = factory.SubFactory(UserFactory)
    phase = factory.SubFactory(PhaseFactory)
    image = factory.django.FileField()
    image_sha256 = factory.sequence(lambda n: hash_sha256(f"image{n}"))


class SubmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Submission

    phase = factory.SubFactory(PhaseFactory)
    predictions_file = factory.django.FileField()
    creator = factory.SubFactory(UserFactory)
    algorithm_requires_memory_gb = 4
    algorithm_requires_gpu_type = GPUTypeChoices.NO_GPU


class EvaluationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Evaluation

    method = factory.SubFactory(MethodFactory)
    submission = factory.SubFactory(SubmissionFactory)
    requires_memory_gb = 4
    requires_gpu_type = GPUTypeChoices.NO_GPU


class EvaluationGroundTruthFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EvaluationGroundTruth

    phase = factory.SubFactory(PhaseFactory)
    creator = factory.SubFactory(UserFactory)
    ground_truth = factory.django.FileField()
    checksum = factory.sequence(lambda n: hash_sha256(f"ground_truth{n}"))


class BatchJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchJob

    submission = factory.SubFactory(SubmissionFactory)
    algorithm_image = factory.SubFactory(AlgorithmImageFactory)
    requires_memory_gb = 4
    requires_gpu_type = GPUTypeChoices.NO_GPU

    @classmethod
    def _create(
        cls,
        model_class,
        *,
        input_civ_sets=None,
        algorithm_interface=None,
        **kwargs,
    ):
        # BatchJobManager.create requires input CIV sets and an interface, and
        # derives the tasks and time limit from them. Default to a single task
        # whose inputs match the interface so a bare BatchJobFactory() produces
        # a valid, inputs-complete job.
        if algorithm_interface is None:
            algorithm_interface = AlgorithmInterfaceFactory()

        if input_civ_sets is None:
            input_civ_sets = [
                {
                    ComponentInterfaceValueFactory(interface=interface_input)
                    for interface_input in algorithm_interface.inputs.all()
                }
            ]

        return model_class.objects.create(
            input_civ_sets=input_civ_sets,
            algorithm_interface=algorithm_interface,
            **kwargs,
        )
