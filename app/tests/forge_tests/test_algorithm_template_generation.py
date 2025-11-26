from pathlib import Path
from uuid import uuid4

import pytest

from grandchallenge.forge.forge import generate_algorithm_template
from grandchallenge.forge.models import ForgeAlgorithm
from tests.forge_tests.utils import (
    _test_script_run,
    algorithm_template_context_factory,
    zipfile_to_filesystem,
)


def test_for_algorithm_template_content(tmp_path):
    testrun_zpath = Path(str(uuid4()))

    with zipfile_to_filesystem(
        output_path=tmp_path, preserve_permissions=False
    ) as zip_file:
        generate_algorithm_template(
            algorithm=ForgeAlgorithm(**algorithm_template_context_factory()),
            output_zip_file=zip_file,
            target_zpath=testrun_zpath,
        )

    template_path = tmp_path / testrun_zpath

    for filename in [
        "Dockerfile",
        "README.md",
        "inference.py",
        "requirements.txt",
        "do_build.sh",
        "do_save.sh",
        "do_test_run.sh",
        "test/input/interf0",
        "test/input/interf1",
    ]:
        assert (template_path / filename).exists()


@pytest.mark.forge_integration
def test_algorithm_template_run(tmp_path):
    testrun_zpath = Path(str(uuid4()))
    algorithm_template_context = algorithm_template_context_factory()

    with zipfile_to_filesystem(output_path=tmp_path) as zip_file:
        generate_algorithm_template(
            algorithm=ForgeAlgorithm(**algorithm_template_context),
            output_zip_file=zip_file,
            target_zpath=testrun_zpath,
        )

    template_path = tmp_path / testrun_zpath

    _test_script_run(
        script_path=template_path / "do_test_run.sh",
    )
