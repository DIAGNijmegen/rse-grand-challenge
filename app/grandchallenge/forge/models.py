from typing import Any

from pydantic import BaseModel, computed_field


class ForgeArchive(BaseModel):
    slug: str
    url: str


class ForgeSocket(BaseModel):
    slug: str
    relative_path: str
    kind: str
    super_kind: str
    example_value: Any = None


class ForgeInterface(BaseModel):
    inputs: list[ForgeSocket]
    outputs: list[ForgeSocket]


class ForgeAlgorithmContext:
    algorithm_interfaces: list[ForgeInterface]

    @computed_field
    @property
    def algorithm_interface_names(self) -> list[str]:
        return [
            f"interf{idx}" for idx, _ in enumerate(self.algorithm_interfaces)
        ]

    @computed_field
    @property
    def algorithm_interface_keys(self) -> list[tuple[str]]:
        algorithm_interface_keys = []
        for interface in self.algorithm_interfaces:
            algorithm_interface_keys.append(
                tuple(sorted([socket.slug for socket in interface.inputs]))
            )
        return algorithm_interface_keys

    @computed_field
    @property
    def algorithm_input_sockets(self) -> list[ForgeSocket]:
        return [
            socket
            for interface in self.algorithm_interfaces
            for socket in interface.inputs
        ]

    @computed_field
    @property
    def algorithm_output_sockets(self) -> list[ForgeSocket]:
        return [
            socket
            for interface in self.algorithm_interfaces
            for socket in interface.outputs
        ]


class ForgePhase(ForgeAlgorithmContext, BaseModel):
    slug: str
    archive: ForgeArchive
    evaluation_additional_inputs: list[ForgeSocket]
    evaluation_additional_outputs: list[ForgeSocket]


class ForgeAlgorithm(ForgeAlgorithmContext, BaseModel):
    title: str
    slug: str
    url: str


class ForgeChallenge(BaseModel):
    slug: str
    url: str
    archives: list[ForgeArchive]
    phases: list[ForgePhase]
