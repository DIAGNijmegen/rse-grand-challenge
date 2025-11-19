# pyvips should be imported before pycurl to reproduce error
try:
    import pyvips
except (ModuleNotFoundError, OSError):
    pyvips = None


def test_import_pycurl():
    import pycurl

    assert pyvips
    assert pycurl
