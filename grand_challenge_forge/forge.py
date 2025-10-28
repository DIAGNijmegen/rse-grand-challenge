import json
import logging
import uuid
from copy import deepcopy
from importlib import metadata
from pathlib import Path

from grand_challenge_forge.generation_utils import (
    copy_and_render,
    generate_socket_value_stub_file,
    socket_to_socket_value,
)
from grand_challenge_forge.schemas import (
    validate_algorithm_template_context,
    validate_pack_context,
)

logger = logging.getLogger(__name__)


def generate_challenge_pack(
    *,
    output_zip_file,
    target_zpath,
    context,
):
    validate_pack_context(context)

    context["grand_challenge_forge_version"] = metadata.version(
        "grand-challenge-forge"
    )

    # Generate the README.md file
    copy_and_render(
        templates_dir_name="pack-readme",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )

    for phase in context["challenge"]["phases"]:
        phase_zpath = target_zpath / phase["slug"]
        phase_context = {"phase": phase}

        generate_upload_to_archive_script(
            context=phase_context,
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "upload-to-archive",
        )

        generate_example_algorithm(
            context=phase_context,
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "example-algorithm",
        )

        generate_example_evaluation(
            context=phase_context,
            output_zip_file=output_zip_file,
            target_zpath=phase_zpath / "example-evaluation-method",
        )


def generate_upload_to_archive_script(
    *,
    output_zip_file,
    target_zpath,
    context,
):
    context = deepcopy(context)

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

    all_algorithm_inputs = {}
    for interface in context["phase"]["algorithm_interfaces"]:
        for socket in interface["inputs"]:
            all_algorithm_inputs[socket["slug"]] = socket

    context.update(
        {
            "all_algorithm_inputs": all_algorithm_inputs,
            "expected_cases_per_interface": expected_cases_per_interface,
        }
    )

    copy_and_render(
        templates_dir_name="upload-to-archive-script",
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


def _interface_context(interfaces):
    # Build context
    algorithm_input_sockets = [
        socket for interface in interfaces for socket in interface["inputs"]
    ]
    algorithm_output_sockets = [
        socket for interface in interfaces for socket in interface["outputs"]
    ]

    algorithm_interface_keys = []
    for interface in interfaces:
        algorithm_interface_keys.append(
            tuple(sorted([socket["slug"] for socket in interface["inputs"]]))
        )

    interface_names = [f"interf{idx}" for idx, _ in enumerate(interfaces)]

    return {
        "algorithm_interface_names": interface_names,
        "algorithm_interface_keys": algorithm_interface_keys,
        "algorithm_input_sockets": algorithm_input_sockets,
        "algorithm_output_sockets": algorithm_output_sockets,
    }


def generate_example_algorithm(*, output_zip_file, target_zpath, context):
    context = deepcopy(context)

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

    context.update(
        _interface_context(interfaces=context["phase"]["algorithm_interfaces"])
    )

    copy_and_render(
        templates_dir_name="example-algorithm",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )


def generate_example_evaluation(*, output_zip_file, target_zpath, context):
    context = deepcopy(context)
    context.update(
        _interface_context(interfaces=context["phase"]["algorithm_interfaces"])
    )

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
        templates_dir_name="example-evaluation-method",
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
    context,
    output_zip_file,
    target_zpath,
):
    validate_algorithm_template_context(context)

    context["grand_challenge_forge_version"] = metadata.version(
        "grand-challenge-forge"
    )

    generate_example_algorithm(
        context={"phase": context["algorithm"]},
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
    )

    copy_and_render(
        templates_dir_name="algorithm-template-readme",
        output_zip_file=output_zip_file,
        target_zpath=target_zpath,
        context=context,
    )
