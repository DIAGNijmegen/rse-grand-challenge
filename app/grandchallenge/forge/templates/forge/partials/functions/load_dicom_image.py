import glob

import numpy
import pydicom


def load_dicom_image_set_as_array(*, location):

    # Get all DICOM files in the directory
    dicom_files = glob.glob(str(location / "*.dcm"))

    # Read all slices
    slices = [pydicom.dcmread(f, force=True) for f in dicom_files]
    decompressed_slices = [slice.decompress() for slice in slices]

    # Extracting pixel-data is non-trivial:
    # - Slices need to be sorted in case of a 3D volume or 4D volume
    # - Pixel data will need to be decompressed, supporting different transfer syntaxes
    # - Any required transformations need to be performed (e.g. scaling via RescaleIntercept/RescaleSlope)
    # - ... et cetera
    # Please refer to Pydicom's documentation: https://pydicom.github.io/pydicom/1.1/pydicom_user_guide.html

    # Here we'll just return a null array with an approximately correct shape
    if len(dicom_files) > 2:
        result = numpy.array([[[0]]])  # 3D
    else:
        result = numpy.array([[0]])  # 2D

    return result
