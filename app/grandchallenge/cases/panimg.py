from pathlib import Path

from django.utils._os import safe_join
from panimg import convert as panimg_convert
from panimg import post_process as panimg_post_process
from panimg.image_builders import (
    image_builder_dicom,
    image_builder_fallback,
    image_builder_mhd,
    image_builder_nifti,
    image_builder_nrrd,
    image_builder_oct,
    image_builder_tiff,
)
from panimg.post_processors import tiff_to_dzi
from panimg_models import PanImgFile


def convert(*, input_directory, output_directory, builders):
    if not builders:
        builders = [
            image_builder_mhd,
            image_builder_nifti,
            image_builder_nrrd,
            image_builder_dicom,
            image_builder_tiff,
            image_builder_oct,
            image_builder_fallback,
        ]

    panimg_result = panimg_convert(
        input_directory=input_directory.resolve(),
        output_directory=output_directory.resolve(),
        builders=builders,
        post_processors=[],  # Do the post-processing later
    )

    return panimg_result


def post_process(*, image_file, output_directory):
    panimg_file = _download_image_file(
        image_file=image_file, output_directory=output_directory
    )

    post_processor_result = panimg_post_process(
        image_files={panimg_file},
        post_processors=[
            tiff_to_dzi,
        ],
    )

    return post_processor_result


def _download_image_file(*, image_file, output_directory):
    """
    Downloads an image file to a directory

    Returns a PanImgFiles that point to the local files
    """
    dest = safe_join(output_directory, image_file.file.name)

    panimg_file = PanImgFile(
        image_id=image_file.image.pk,
        image_type=image_file.image_type,
        file=dest,
    )

    # Safe to create directories as safe_join has been used
    Path(dest).parent.mkdir(parents=True, exist_ok=True)

    with image_file.file.open("rb") as fs, open(dest, "wb") as fd:
        for chunk in fs.chunks():
            fd.write(chunk)

    return panimg_file
