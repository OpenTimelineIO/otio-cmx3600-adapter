import re
from pathlib import Path

from pytest import fixture
from opentimelineio import adapters, plugins


@fixture
def cmx_adapter():
    manifest_path = (
        Path(__file__).parent.parent / "src/otio_cmx3600_adapter/plugin_manifest.json"
    )
    manifest = plugins.manifest.manifest_from_file(str(manifest_path))
    return next(adapter for adapter in manifest.adapters if adapter.name == "cmx_3600")


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
