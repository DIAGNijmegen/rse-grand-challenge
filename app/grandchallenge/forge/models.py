from datetime import timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, HttpUrl, RootModel

from grandchallenge.components.models import (
    ComponentJob,
    InterfaceKindChoices,
    InterfaceSuperKindChoices,
)


class ForgeArchive(BaseModel):
    slug: str
    url: HttpUrl


ForgeKindEnum = Enum(
    "ForgeKindEnum", {str(m.name): str(m.label) for m in InterfaceKindChoices}
)

ForgeSuperKindEnum = Enum(
    "ForgeSuperKindEnum",
    {str(m.name): str(m.label) for m in InterfaceSuperKindChoices},
)


class ForgeSocket(BaseModel):
    slug: str
    relative_path: str
    kind: ForgeKindEnum
    super_kind: ForgeSuperKindEnum
    example_value: Any = None

    @property
    def is_json(self):
        return self.relative_path.endswith(".json")

    @property
    def is_image(self):
        return self.super_kind == ForgeSuperKindEnum.IMAGE

    @property
    def is_file(self):
        return (
            self.super_kind == ForgeSuperKindEnum.FILE
            and not self.relative_path.endswith(".json")
        )

    @property
    def has_example_value(self):
        # TODO this does not allow for NULL example values
        return self.example_value is not None


class ForgeInterface(BaseModel):
    inputs: list[ForgeSocket]
    outputs: list[ForgeSocket]


class ForgeAlgorithmContext:
    algorithm_interfaces: list[ForgeInterface]

    @property
    def algorithm_interface_names(self) -> list[str]:
        return [
            f"interf{idx}" for idx, _ in enumerate(self.algorithm_interfaces)
        ]

    @property
    def algorithm_interface_keys(self) -> list[tuple[str]]:
        algorithm_interface_keys = []
        for interface in self.algorithm_interfaces:
            algorithm_interface_keys.append(
                tuple(sorted([socket.slug for socket in interface.inputs]))
            )
        return algorithm_interface_keys

    @property
    def algorithm_input_sockets(self) -> list[ForgeSocket]:
        return [
            socket
            for interface in self.algorithm_interfaces
            for socket in interface.inputs
        ]

    @property
    def algorithm_output_sockets(self) -> list[ForgeSocket]:
        return [
            socket
            for interface in self.algorithm_interfaces
            for socket in interface.outputs
        ]


class ForgeChallenge(BaseModel):
    slug: str
    url: HttpUrl


class ForgePhase(ForgeAlgorithmContext, BaseModel):
    slug: str
    archive: ForgeArchive
    evaluation_additional_inputs: list[ForgeSocket]
    evaluation_additional_outputs: list[ForgeSocket]
    challenge: ForgeChallenge


class ForgeAlgorithm(ForgeAlgorithmContext, BaseModel):
    title: str
    slug: str
    url: HttpUrl


class ForgeSocketValue(BaseModel):
    socket: ForgeSocket
    file: str | None = None
    image: dict[str, str] | None = None
    value: Any = None


ForgeSocketValues = RootModel[list[ForgeSocketValue]]

ForgeStatusEnum = Enum(
    "ForgeStatusEnum",
    {str(value): str(label) for value, label in ComponentJob.STATUS_CHOICES},
)


class ForgePrediction(BaseModel):
    pk: UUID
    inputs: list[ForgeSocketValue]
    outputs: list[ForgeSocketValue]
    exec_duration: timedelta | None
    invoke_duration: timedelta | None
    status: ForgeStatusEnum


ForgePredictions = RootModel[list[ForgePrediction]]
