import pydicom


def write_array_as_dicom_image_set(*, location, array):
    location.mkdir(parents=True, exist_ok=True)

    # Writing DICOM Image data correctly is non-trivial!

    # Below is a minimal and incomplete example that requires
    # many additional basic-image attributes to be added
    # still

    ds = pydicom.Dataset()

    # Required meta info
    ds.file_meta = pydicom.dataset.FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

    # Basic image attributes
    ds.Rows, ds.Columns = array.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = array.dtype.itemsize * 8
    ds.BitsStored = ds.BitsAllocated
    ds.HighBit = ds.BitsAllocated - 1
    ds.PixelRepresentation = 0  # 0 = unsigned

    # Pixel data
    ds.PixelData = array.tobytes()

    # Save
    pydicom.dcmwrite(location / "output.dcm", ds)
