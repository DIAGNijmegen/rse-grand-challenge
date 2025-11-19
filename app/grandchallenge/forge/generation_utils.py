import json
import logging
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import black
from django.conf import settings
from jinja2 import FileSystemLoader, StrictUndefined, TemplateNotFound
from jinja2.sandbox import ImmutableSandboxedEnvironment

FORGE_MODULE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
FORGE_RESOURCES_PATH = FORGE_MODULE_PATH / "resources"
FORGE_PARTIALS_PATH = FORGE_MODULE_PATH / "partials"


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


def get_jinja2_environment(searchpath=None):
    from grandchallenge.forge.partials.filters import custom_filters

    if searchpath:
        searchpath = [searchpath, FORGE_PARTIALS_PATH]
    else:
        searchpath = FORGE_PARTIALS_PATH

    env = ImmutableSandboxedEnvironment(
        loader=FileSystemLoader(
            searchpath=searchpath,
            followlinks=True,
        ),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters = custom_filters
    env.filters["zip"] = zip
    env.globals["now"] = datetime.now(timezone.utc)

    return env


def copy_and_render(
    *,
    templates_dir_name,
    output_zip_file,
    target_zpath,
    context,
):
    source_path = FORGE_PARTIALS_PATH / templates_dir_name

    if not source_path.exists():
        raise TemplateNotFound(source_path)

    env = get_jinja2_environment(searchpath=source_path)

    for root, _, files in os.walk(source_path, followlinks=True):
        root = Path(root)

        check_allowed_source(path=root)

        # Create relative path
        rel_path = root.relative_to(source_path)
        current_zdir = target_zpath / rel_path

        for file in sorted(files):
            source_file = root / file
            output_file = current_zdir / file

            check_allowed_source(path=source_file)

            if file.endswith(".j2"):  # Jinja2 template
                template = env.get_template(
                    name=str(source_file.relative_to(source_path))
                )
                rendered_content = template.render(
                    **context,
                    _no_gpus=settings.FORGE_DISABLE_GPUS,
                )

                targetfile_zpath = output_file.with_suffix("")

                if targetfile_zpath.suffix == ".py":
                    rendered_content = apply_black(rendered_content)

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
