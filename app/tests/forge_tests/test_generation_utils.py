import zipfile
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.template import TemplateDoesNotExist

from grandchallenge.forge.generation_utils import copy_and_render


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
            pytest.raises(TemplateDoesNotExist),
        ),
        (
            "disallowed_dir_symlink",
            pytest.raises(PermissionError),
        ),
        (
            "disallowed_file_symlink",
            pytest.raises(PermissionError),
        ),
    ),
)
def test_copy_and_render_source_restrictions(name, context, settings):
    with patch(
        "grandchallenge.forge.generation_utils.FORGE_PARTIALS_PATH",
        new=settings.SITE_ROOT / "tests" / "templates" / "forge" / "partials",
    ):
        with context:
            with zipfile.ZipFile(BytesIO(), "w") as zip_file:
                copy_and_render(
                    templates_dir_name=name,
                    output_zip_file=zip_file,
                    target_zpath=Path(""),
                    context={},
                )
