from packaging.version import Version

from fritz_callhistory.version import installed_version


def test_installed_version_is_valid_pep440():
    parsed = Version(installed_version())

    assert parsed >= Version("0.0.0")
