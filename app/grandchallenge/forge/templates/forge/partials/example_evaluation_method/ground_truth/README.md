You can upload your method's ground truth separately from the container image as a tarball (.tar.gz) on Grand Challenge (Phase settings > Ground Truths). Alternatively, you can include it in the container-image build by adding it to the `resources/`.

A tarball is easier to update than the entire container image.

If provided, the tarball will be extracted to `/opt/ml/input/data/ground_truth/` at runtime.
