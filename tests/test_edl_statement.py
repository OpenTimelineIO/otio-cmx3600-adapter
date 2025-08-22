from decimal import Decimal

import pytest

from otio_cmx3600_adapter import edl_statement


@pytest.mark.parametrize(
    "directive_string,expected",
    [
        # Apparently sometimes the frame count isn't zero-padded - We've seen this in the wild, not sure why
        (
            "B_0260C009_250224_215612_h1ERX 024.0                      21:00:02:6",
            edl_statement.MotionDirective(
                reel="B_0260C009_250224_215612_h1ERX",
                speed=Decimal("24.0"),
                trigger="21:00:02:6",
            ),
        ),
        (
            "Z682_156       000.0                01:00:10:21",
            edl_statement.MotionDirective(
                reel="Z682_156", speed=Decimal("0.0"), trigger="01:00:10:21"
            ),
        ),
        (
            "Z682_157       000.0                01:00:10:20",
            edl_statement.MotionDirective(
                reel="Z682_157", speed=Decimal("0.0"), trigger="01:00:10:20"
            ),
        ),
        (
            "Z686_5A.       047.6                01:00:06:00",
            edl_statement.MotionDirective(
                reel="Z686_5A.", speed=Decimal("47.6"), trigger="01:00:06:00"
            ),
        ),
        (
            "Z694_51B       068.0                01:00:15:13",
            edl_statement.MotionDirective(
                reel="Z694_51B", speed=Decimal("68.0"), trigger="01:00:15:13"
            ),
        ),
        (
            "Z694_51B       047.8                01:00:16:05",
            edl_statement.MotionDirective(
                reel="Z694_51B", speed=Decimal("47.8"), trigger="01:00:16:05"
            ),
        ),
        (
            "Z694_54.       048.0                01:00:16:15",
            edl_statement.MotionDirective(
                reel="Z694_54.", speed=Decimal("48.0"), trigger="01:00:16:15"
            ),
        ),
        (
            "Z694_SHI       047.9                01:00:25:01",
            edl_statement.MotionDirective(
                reel="Z694_SHI", speed=Decimal("47.9"), trigger="01:00:25:01"
            ),
        ),
        (
            "Z700_303       052.6                01:00:07:18",
            edl_statement.MotionDirective(
                reel="Z700_303", speed=Decimal("52.6"), trigger="01:00:07:18"
            ),
        ),
    ],
)
def test_motion_directive_parsing(directive_string, expected):
    directive = edl_statement.MotionDirective.from_string(directive_string)
    assert directive == expected
