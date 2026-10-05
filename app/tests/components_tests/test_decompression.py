import io
import tarfile

import pytest
from django.core.exceptions import ValidationError

from grandchallenge.components.tasks import _decompress_tarball


def _build_tarball(*, members):
    """Build an in-memory uncompressed tarball.

    ``members`` is a list of ``(tarinfo, data)`` tuples. ``data`` may be
    ``None`` for members that do not carry file content (e.g. directories,
    symlinks).
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for tarinfo, data in members:
            if data is None:
                tar.addfile(tarinfo)
            else:
                tarinfo.size = len(data)
                tar.addfile(tarinfo, io.BytesIO(data))
    buffer.seek(0)
    return buffer


def test_decompress_tarball_copies_files_and_dirs():
    directory = tarfile.TarInfo(name="blobs")
    directory.type = tarfile.DIRTYPE
    regular = tarfile.TarInfo(name="manifest.json")

    in_fileobj = _build_tarball(
        members=[(directory, None), (regular, b'[{"Config": "c.json"}]')]
    )
    out_fileobj = io.BytesIO()

    _decompress_tarball(in_fileobj=in_fileobj, out_fileobj=out_fileobj)

    out_fileobj.seek(0)
    with tarfile.open(fileobj=out_fileobj, mode="r") as tar:
        names = {member.name for member in tar.getmembers()}
        manifest = tar.extractfile("manifest.json").read()

    assert names == {"blobs", "manifest.json"}
    assert manifest == b'[{"Config": "c.json"}]'


def test_decompress_tarball_flushes_to_disk(tmp_path):
    regular = tarfile.TarInfo(name="manifest.json")
    in_fileobj = _build_tarball(members=[(regular, b"data")])

    out_path = tmp_path / "out.tar"
    with open(out_path, "wb") as out_fileobj:
        _decompress_tarball(in_fileobj=in_fileobj, out_fileobj=out_fileobj)
        # The caller may read the file by path (e.g. via a subprocess)
        # immediately, so the data must already be on disk here.
        assert out_path.stat().st_size > 0


@pytest.mark.parametrize(
    "make_member",
    [
        pytest.param(
            lambda: _symlink_member(name="evil", linkname="/etc/passwd"),
            id="symlink",
        ),
        pytest.param(
            lambda: _hardlink_member(name="evil", linkname="manifest.json"),
            id="hardlink",
        ),
        pytest.param(
            lambda: _device_member(name="evil"),
            id="device",
        ),
    ],
)
def test_decompress_tarball_rejects_non_regular_members(make_member):
    regular = tarfile.TarInfo(name="manifest.json")
    in_fileobj = _build_tarball(
        members=[(regular, b"data"), (make_member(), None)]
    )
    out_fileobj = io.BytesIO()

    with pytest.raises(ValidationError):
        _decompress_tarball(in_fileobj=in_fileobj, out_fileobj=out_fileobj)


def _symlink_member(*, name, linkname):
    member = tarfile.TarInfo(name=name)
    member.type = tarfile.SYMTYPE
    member.linkname = linkname
    return member


def _hardlink_member(*, name, linkname):
    member = tarfile.TarInfo(name=name)
    member.type = tarfile.LNKTYPE
    member.linkname = linkname
    return member


def _device_member(*, name):
    member = tarfile.TarInfo(name=name)
    member.type = tarfile.CHRTYPE
    member.devmajor = 1
    member.devminor = 3
    return member
