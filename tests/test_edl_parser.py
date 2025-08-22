import decimal
from pathlib import Path

import pytest

from otio_cmx3600_adapter import edl_statement, edl_parser


SAMPLE_DATA_PATH = Path(__file__).parent / "sample_data"


def test_transition():
    transition_events = """000003  D001C003_210414A7                V     C        19:37:19:18 19:37:19:18 01:00:19:05 01:00:19:05 
000003  A011C005_21041428                V     D    024 20:09:25:02 20:09:26:02 01:00:19:05 01:00:20:05 
002  TST V     W001    010 01:00:08:08 01:00:08:18 01:00:00:09 01:00:00:19
"""  # noqa: W291
    statement_1, statement_2, statement_3 = edl_parser.statements_from_string(
        transition_events
    )
    assert statement_1.edit_number == "000003"
    assert statement_1.source_identification == "D001C003_210414A7"
    assert statement_1.line_number == 1
    assert statement_1.channels == "V"
    assert statement_1.source_mode == edl_statement.SourceMode.VIDEO
    assert statement_1.edit_type == "C"
    assert statement_1.edit_parameter is None
    assert statement_1.effect.type == edl_statement.EffectType.CUT
    assert statement_1.source_entry == "19:37:19:18"
    assert statement_1.source_exit == "19:37:19:18"
    assert statement_1.sync_entry == "01:00:19:05"
    assert statement_1.sync_exit == "01:00:19:05"

    assert statement_2.edit_number == "000003"
    assert statement_2.source_identification == "A011C005_21041428"
    assert statement_2.line_number == 2
    assert statement_2.channels == "V"
    assert statement_2.source_mode == edl_statement.SourceMode.VIDEO
    assert statement_2.edit_type == "D"
    assert statement_2.edit_parameter == "024"
    assert statement_2.effect.type == edl_statement.EffectType.DISSOLVE
    assert statement_2.effect.transition_duration == 24
    assert statement_2.source_entry == "20:09:25:02"
    assert statement_2.source_exit == "20:09:26:02"
    assert statement_2.sync_entry == "01:00:19:05"
    assert statement_2.sync_exit == "01:00:20:05"

    assert statement_3.edit_number == "002"
    assert statement_3.source_identification == "TST"
    assert statement_3.line_number == 3
    assert statement_3.channels == "V"
    assert statement_3.source_mode == edl_statement.SourceMode.VIDEO
    assert statement_3.edit_type == "W001"
    assert statement_3.edit_parameter == "010"
    assert statement_3.effect.type == edl_statement.EffectType.WIPE
    assert statement_3.effect.transition_duration == 10
    assert statement_3.effect.wipe_type == "001"
    assert statement_3.source_entry == "01:00:08:08"
    assert statement_3.source_exit == "01:00:08:18"
    assert statement_3.sync_entry == "01:00:00:09"
    assert statement_3.sync_exit == "01:00:00:19"


def test_parse_25fps():
    with open(SAMPLE_DATA_PATH / "25fps.edl") as infile:
        statements = list(edl_parser.statements_from_string(infile.read()))

    # Check the line numbers
    expected_line_number = 2
    for statement in statements:
        assert statement.line_number == expected_line_number
        expected_line_number += 1

    expected_edit_numbers = [
        None,
        None,
        "001",
        "001",
        "001",
        "002",
        "002",
        "002",
        "003",
        "003",
        "003",
        "004",
        "004",
        "004",
    ]
    edit_numbers = [statement.edit_number for statement in statements]
    assert edit_numbers == expected_edit_numbers

    assert not any(statement.is_virtual_edit for statement in statements)
    assert not any(statement.is_recorded for statement in statements)

    expected_statement_types = [
        edl_statement.NoteFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.StandardFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.StandardFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.StandardFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.StandardFormStatement,
        edl_statement.NoteFormStatement,
        edl_statement.NoteFormStatement,
    ]

    statement_types = [type(statement) for statement in statements]
    assert statement_types == expected_statement_types


@pytest.mark.parametrize(
    "event, expected_fields",
    [

        (
            "002  Start_4K_Full Aperture_24fps V     C        00:00:00:00 00:00:08:00 01:05:23:18 01:05:31:18",
            ("002", "Start_4K_Full Aperture_24fps", "V", edl_statement.EffectType.CUT, None, "00:00:00:00", "00:00:08:00", "01:05:23:18", "01:05:31:18"),
        ),
        (
            "003197                                   V     C        00:31:45:01 00:31:53:01 03:00:39:21 03:00:47:21",
            ("003197", "", "V", edl_statement.EffectType.CUT, None, "00:31:45:01", "00:31:53:01", "03:00:39:21", "03:00:47:21"),
        ),
        (
            "000020  A010C002_210414GF                V     D    024 17:30:43:06 17:30:44:06 01:01:07:13 01:01:08:13",
            ("000020", "A010C002_210414GF", "V", edl_statement.EffectType.DISSOLVE, "024", "17:30:43:06", "17:30:44:06", "01:01:07:13", "01:01:08:13"),
        )
    ]
)
def test_line_variants(event, expected_fields):

    statement_generator = edl_parser.statements_from_string(event)
    parsed_statement = next(statement_generator)

    assert isinstance(parsed_statement, edl_statement.StandardFormStatement)
    statement: edl_statement.StandardFormStatement = parsed_statement

    assert statement.edit_number == expected_fields[0]
    assert statement.source_identification == expected_fields[1]
    assert statement.channels == expected_fields[2]
    assert statement.effect.type == expected_fields[3]
    assert statement.edit_parameter == expected_fields[4]
    assert statement.source_entry == expected_fields[5]
    assert statement.source_exit == expected_fields[6]
    assert statement.sync_entry == expected_fields[7]
    assert statement.sync_exit == expected_fields[8]


def test_freezeframe():
    event = """000183  Z682_156 V     C        01:00:10:21 01:00:10:22 01:08:30:00 01:08:30:17 
M2   Z682_156       000.0                01:00:10:21 
* FROM CLIP NAME:  Z682_156 (LAY3) FF 
* * FREEZE FRAME
"""  # noqa: W291
    (
        statement_1,
        statement_2,
        statement_3,
        statement_4,
    ) = edl_parser.statements_from_string(event)
    assert (
        statement_2.statement_identifier
        == edl_statement.NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY
    )
    assert (
        statement_3.statement_identifier
        == edl_statement.NoteFormStatement.NoteFormIdentifiers.FROM_CLIP_NAME
    )
    assert (
        statement_4.statement_identifier
        == edl_statement.NoteFormStatement.NoteFormIdentifiers.FREEZE_FRAME
    )


@pytest.mark.parametrize(
    "directive,expected_reel,expected_speed,expected_trigger",
    [
        (
            "D001C003_210414A7                         048.0 19:37:19:18",
            "D001C003_210414A7",
            decimal.Decimal("48.0"),
            "19:37:19:18",
        ),
        (
            "CYAN           000.0    MSTR     I +00:00:00:15",
            "CYAN",
            decimal.Decimal("0.0"),
            "00:00:00:15",
        ),
        (
            "Z682_156 (LAY3)		0.0			01:00:10:21",
            "Z682_156 (LAY3)",
            decimal.Decimal("0.0"),
            "01:00:10:21",
        ),
        (
            "B095C001_191129RQ                        -024.0 08:53:21:07",
            "B095C001_191129RQ",
            decimal.Decimal("-024.0"),
            "08:53:21:07",
        ),
        (
            "B001_C003_1016BW 036.0                      09:08:13:11",
            "B001_C003_1016BW",
            decimal.Decimal("036.0"),
            "09:08:13:11",
        ),
    ],
)
def test_m2_processing(directive, expected_reel, expected_speed, expected_trigger):
    motion_directive = edl_statement.MotionDirective.from_string(directive)
    assert motion_directive.reel == expected_reel
    assert motion_directive.speed == expected_speed
    assert motion_directive.trigger == expected_trigger


@pytest.mark.parametrize(
    "edl_path",
    [edl_path for edl_path in SAMPLE_DATA_PATH.iterdir() if edl_path.suffix == ".edl"],
)
def test_all_edls_handled(edl_path):
    with open(edl_path) as infile:
        for statement in edl_parser.statements_from_string(infile.read()):
            assert type(statement) is not edl_statement.UnsupportedStatement
