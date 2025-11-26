import json
import logging
import uuid
from pathlib import Path

from grandchallenge.forge.generation_utils import (
    copy_and_render,
    generate_socket_value_stub_file,
    socket_to_socket_value,
)
from grandchallenge.forge.models import (
    ForgeAlgorithm,
    ForgeChallenge,
    ForgePhase,
)

logger = logging.getLogger(__name__)


def generate_challenge_pack(
    *,
    challenge,
    target_zpath,
    output_zip_file,
):
    if not isinstance(challenge, ForgeChallenge):
        raise ValueError("challenge must be an instance of ForgeChallenge")

    context = {"challenge": challenge.model_dump()}

    # Generate the README.md file
    copy_and_render(
        templates_dir_name="pack_readme",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )

    for phase in context["challenge"]["phases"]:
        phase_zpath = target_zpath / phase["slug"]

        generate_upload_to_archive_script(
            context_object=ForgePhase(**phase),
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "upload_to_archive",
        )

        generate_example_algorithm(
            context_object=ForgePhase(**phase),
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "example_algorithm",
        )

        generate_example_evaluation(
            context_object=ForgePhase(**phase),
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "example_evaluation_method",
        )


def generate_upload_to_archive_script(
    *,
    context_object,
    target_zpath,
    output_zip_file,
):
    if not isinstance(context_object, ForgePhase | ForgeAlgorithm):
        raise ValueError(
            "context_object must be an instance of ForgePhase or ForgeAlgorithm"
        )

    context = {
        "phase": context_object.model_dump()
    }  # TODO both things are called phase?

    expected_cases_per_interface = {}
    for idx, interface in enumerate(context["phase"]["algorithm_interfaces"]):
        interface_name = f"interf{idx}"
        archive_cases = generate_archive_cases(
            inputs=interface["inputs"],
            output_zip_file=output_zip_file,
            target_zpath=target_zpath / interface_name,
            number_of_cases=3,
        )

        # Make cases relative to the script
        for case in archive_cases:
            for k, v in case.items():
                case[k] = Path(*v.parts[3:])

        expected_cases_per_interface[interface_name] = archive_cases

    context.update(
        {
            "expected_cases_per_interface": expected_cases_per_interface,
        }
    )

    copy_and_render(
        templates_dir_name="upload_to_archive_script",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )


def generate_archive_cases(
    *, inputs, output_zip_file, target_zpath, number_of_cases
):
    result = []
    for i in range(0, number_of_cases):
        item_files = {}
        for input_socket in inputs:
            # Use deep zpath to create the files
            zpath = (
                target_zpath / Path(f"case{i}") / input_socket["relative_path"]
            )

            # Report back relative to script paths
            zpath = generate_socket_value_stub_file(
                output_zip_file=output_zip_file,
                target_zpath=zpath,
                socket=input_socket,
            )

            item_files[input_socket["slug"]] = zpath

        result.append(item_files)

    return result


def generate_example_algorithm(
    *,
    context_object,
    target_zpath,
    output_zip_file,
):
    if not isinstance(context_object, ForgePhase | ForgeAlgorithm):
        raise ValueError(
            "context_object must be an instance of ForgePhase or ForgeAlgorithm"
        )

    context = {
        "phase": context_object.model_dump()
    }  # TODO both things are called phase?

    interface_names = []
    for idx, interface in enumerate(context["phase"]["algorithm_interfaces"]):
        interface_name = f"interf{idx}"
        interface_names.append(interface_name)

        input_zdir = target_zpath / "test" / "input" / interface_name
        inputs = interface["inputs"]

        # create inputs.json
        output_zip_file.writestr(
            str(input_zdir / "inputs.json"),
            json.dumps(
                [socket_to_socket_value(socket) for socket in inputs], indent=4
            ),
        )

        # Create actual input files
        for input in inputs:
            generate_socket_value_stub_file(
                output_zip_file=output_zip_file,
                target_zpath=input_zdir / input["relative_path"],
                socket=input,
            )

    copy_and_render(
        templates_dir_name="example_algorithm",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )


def generate_example_evaluation(
    *,
    context_object,
    target_zpath,
    output_zip_file,
):
    if not isinstance(context_object, ForgePhase | ForgeAlgorithm):
        raise ValueError(
            "context_object must be an instance of ForgePhase or ForgeAlgorithm"
        )

    context = {
        "phase": context_object.model_dump()
    }  # TODO both things are called phase?

    input_zdir = target_zpath / "test" / "input"

    predictions_json = []
    for interface in context["phase"]["algorithm_interfaces"]:
        predictions_json.extend(
            generate_predictions_json(
                inputs=interface["inputs"],
                outputs=interface["outputs"],
                number_of_jobs=3,
            )
        )

    output_zip_file.writestr(
        str(input_zdir / "predictions.json"),
        json.dumps(predictions_json, indent=4),
    )

    generate_prediction_files(
        output_zip_file=output_zip_file,
        target_zpath=target_zpath / "test" / "input",
        predictions=predictions_json,
    )

    for socket in context["phase"]["evaluation_additional_inputs"]:
        generate_socket_value_stub_file(
            output_zip_file=output_zip_file,
            target_zpath=input_zdir / socket["relative_path"],
            socket=socket,
        )

    copy_and_render(
        templates_dir_name="example_evaluation_method",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )


def generate_predictions_json(
    *,
    inputs,
    outputs,
    number_of_jobs,
):
    predictions = []
    for _ in range(0, number_of_jobs):
        predictions.append(
            {
                "pk": str(uuid.uuid4()),
                "inputs": [
                    socket_to_socket_value(socket) for socket in inputs
                ],
                "outputs": [
                    socket_to_socket_value(socket) for socket in outputs
                ],
                "exec_duration": "P0DT00H31M14S",
                "invoke_duration": None,
                "status": "Succeeded",
            }
        )
    return predictions


def generate_prediction_files(*, output_zip_file, target_zpath, predictions):
    for prediction in predictions:
        prediction_zpath = target_zpath / prediction["pk"]
        for socket_value in prediction["outputs"]:
            generate_socket_value_stub_file(
                output_zip_file=output_zip_file,
                target_zpath=prediction_zpath
                / "output"
                / socket_value["interface"]["relative_path"],
                socket=socket_value["interface"],
            )


def generate_algorithm_template(
    *,
    algorithm,
    target_zpath,
    output_zip_file,
):
    if not isinstance(algorithm, ForgeAlgorithm):
        raise ValueError("algorithm must be an instance of ForgeAlgorithm")

    context = {"algorithm": algorithm.model_dump()}

    generate_example_algorithm(
        context_object=ForgeAlgorithm(**context["algorithm"]),
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
    )

    copy_and_render(
        templates_dir_name="algorithm_template_readme",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )
