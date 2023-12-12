from opentimelineio import opentime
from otio_cmx3600_adapter.cmx_3600_reader import from_timecode_approx


# TODO: we should add more tests for this
def test_approximated_timecode():
    time, was_approximated = from_timecode_approx(
        "00:03:42:25", 24, True
    )

    assert was_approximated
    # The algo should use the next nearest frame rate that fits the timecode
    assert time == opentime.from_timecode("00:03:42:25", rate=30)
