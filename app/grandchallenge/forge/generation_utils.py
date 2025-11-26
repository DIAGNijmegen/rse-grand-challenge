import json
import logging
import time
import uuid
import zipfile
from pathlib import Path

import black
from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

FORGE_MODULE_PATH = Path(__file__).parent
FORGE_RESOURCES_PATH = FORGE_MODULE_PATH / "resources"
FORGE_PARTIALS_PATH = FORGE_MODULE_PATH / "templates" / "forge" / "partials"


logger = logging.getLogger(__name__)


def is_json(socket):
    return socket["relative_path"].endswith(".json")


def is_image(socket):
    return socket["super_kind"] == "Image"


def is_file(socket):
    return socket["super_kind"] == "File" and not socket[
        "relative_path"
    ].endswith(".json")


def has_example_value(socket):
    return "example_value" in socket and socket["example_value"] is not None


def generate_socket_value_stub_file(*, output_zip_file, target_zpath, socket):
    """Creates a stub based on a component interface"""
    if has_example_value(socket):
        zinfo = zipfile.ZipInfo(str(target_zpath))
        output_zip_file.writestr(
            zinfo,
            json.dumps(
                socket["example_value"],
                indent=4,
            ),
        )
        return target_zpath

    # Copy over an example

    if is_json(socket):
        source = FORGE_RESOURCES_PATH / "example.json"
    elif is_image(socket):
        source = FORGE_RESOURCES_PATH / "example.mha"
        target_zpath = target_zpath / f"{str(uuid.uuid4())}.mha"
    else:
        source = FORGE_RESOURCES_PATH / "example.txt"

    output_zip_file.write(
        source,
        arcname=str(target_zpath),
    )

    return target_zpath


def socket_to_socket_value(socket):
    """Creates a stub dict repr of a socket valuee"""
    sv = {
        "file": None,
        "image": None,
        "value": None,
    }
    if socket["super_kind"] == "Image":
        sv["image"] = {
            "name": "the_original_filename_of_the_file_that_was_uploaded.suffix",
        }
    if socket["super_kind"] == "File":
        sv["file"] = (
            f"https://grand-challenge.org/media/some-link/"
            f"{socket['relative_path']}"
        )
    if socket["super_kind"] == "Value":
        sv["value"] = socket.get("example_value", {"some_key": "some_value"})
    return {
        **sv,
        "interface": socket,
    }


def copy_and_render(
    *,
    templates_dir_name,
    output_zip_file,
    target_zpath,
    context,
):
    source_path = FORGE_PARTIALS_PATH / templates_dir_name

    if not source_path.exists():
        raise TemplateDoesNotExist(source_path)

    for root, _, files in source_path.walk():
        check_allowed_source(path=root)

        # Create relative path
        rel_path = root.relative_to(source_path)
        current_zdir = target_zpath / rel_path

        for file in sorted(files):
            source_file = root / file
            output_file = current_zdir / file

            check_allowed_source(path=source_file)

            if file.endswith(".template"):
                rendered_content = render_to_string(
                    template_name=source_file,
                    context={
                        **context,
                        "grand_challenge_forge_version": settings.COMMIT_ID,
                        "no_gpus": settings.FORGE_DISABLE_GPUS,
                    },
                )

                targetfile_zpath = output_file.with_suffix("")

                if targetfile_zpath.suffix == ".py":
                    # Replace escaped characters
                    rendered_content = rendered_content.replace("&#x27;", "'")
                    rendered_content = apply_black(rendered_content)
                else:
                    rendered_content = f"{rendered_content.strip()}\n"

                # Collect information about the file to be written to the zip file
                # (permissions, et cetera)
                zinfo = zipfile.ZipInfo.from_file(
                    source_file,
                    arcname=str(targetfile_zpath),
                )

                # Update the date time of creation, since we are technically
                # creating a new file
                # Also (partially) addresses a problem where docker build injects
                # incorrect files:
                # https://github.com/moby/buildkit/issues/4817#issuecomment-2032551066
                zinfo.date_time = time.localtime()[0:6]

                output_zip_file.writestr(zinfo, rendered_content)
            else:
                output_zip_file.write(
                    str(source_file), arcname=str(output_file)
                )


def check_allowed_source(path):
    if FORGE_PARTIALS_PATH.resolve() not in path.resolve().parents:
        raise PermissionError(
            f"Only files under {FORGE_PARTIALS_PATH} are allowed "
            "to be copied or rendered"
        )


def apply_black(content):
    # Format rendered Python code string using black
    result = black.format_str(
        content,
        mode=black.Mode(),
    )
    return result
