import re
from pathlib import Path

from pytest import fixture
from opentimelineio import adapters, plugins

import otio_cmx3600_adapter.cmx_3600


@fixture
def cmx_adapter():
    # Use OTIO's native plugin loading system
    # This verifies that the adapter is being correctly registered and
    # discovered by OTIO.
    # But it also means the tests require you to install the adapter before
    # running the tests.
    manifest = plugins.ActiveManifest()

    adapter = next(
        adapter for adapter in manifest.adapters if adapter.name == "cmx_3600"
    )

    # Assert that the loaded adapter is the local one.
    assert Path(adapter.module_abs_path()) == Path(
        otio_cmx3600_adapter.cmx_3600.__file__
    )
    return adapter


@fixture
def assertJsonEqual():
    """Convert to json and compare that (more readable)."""

    def compare(known, test_result):
        known_str = adapters.write_to_string(known, "otio_json")
        test_str = adapters.write_to_string(test_result, "otio_json")

        def strip_trailing_decimal_zero(s):
            return re.sub(r'"(value|rate)": (\d+)\.0', r'"\1": \2', s)

        assert strip_trailing_decimal_zero(known_str) == strip_trailing_decimal_zero(
            test_str
        )

    return compare


@fixture
def assertIsOTIOEquivalentTo():
    """Test using the 'is equivalent to' method on SerializableObject"""

    return lambda known, test_result: known.is_equivalent_to(test_result) is True
