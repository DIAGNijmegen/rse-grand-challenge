import zipfile
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from jinja2 import TemplateNotFound
from jinja2.exceptions import SecurityError

from grandchallenge.forge.generation_utils import (
    copy_and_render,
    get_jinja2_environment,
)
from tests.forge_tests.utils import TEST_RESOURCES


def test_jinja2_environment_sandbox():
    # Get the Jinja2 environment
    env = get_jinja2_environment()

    # Sanity
    template = env.from_string("Hello, {{ name }}!")
    assert template.render(name="World") == "Hello, World!"

    template = env.from_string("{{ [].__class__.__mro__ }}")
    with pytest.raises(SecurityError):
        template.render()


@pytest.mark.parametrize(
    "name,context",
    (
        (
            "working",
            nullcontext(),
        ),
        (
            "working_with_include",
            nullcontext(),
        ),
        (
            "allowed_symlinks",
            nullcontext(),
        ),
        (
            "missing",
            pytest.raises(TemplateNotFound),
        ),
        (
            "disallowed_dir_symlink",
            pytest.raises(PermissionError),
        ),
        (
            "disallowed_file_symlink",
            pytest.raises(PermissionError),
        ),
        (
            # Sanity: should hit the symlink restrictions
            "disallowed_symlink_include",
            pytest.raises(PermissionError),
        ),
    ),
)
def test_copy_and_render_source_restrictions(name, context):
    with patch(
        "grandchallenge.forge.generation_utils.FORGE_PARTIALS_PATH",
        new=TEST_RESOURCES / "partials",
    ):
        with context:
            with zipfile.ZipFile(BytesIO(), "w") as zip_file:
                copy_and_render(
                    templates_dir_name=name,
                    output_zip_file=zip_file,
                    target_zpath=Path(""),
                    context={},
                )
