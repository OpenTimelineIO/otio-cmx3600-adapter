import opentimelineio as otio

from otio_cmx3600_adapter import cmx_3600_reader
from otio_cmx3600_adapter import edl_parser


def test_comment_processing_single_clip():
    comments_string = """M2      A009C022_210414B3                         012.0 16:39:36:18 
*FROM CLIP NAME:  102-21-8A* 
*ASC_SOP (1.0000 1.0000 1.0000)(0.0000 0.0000 0.0000)(1.0000 1.0000 1.0000) 
*ASC_SAT 1 
*SOURCE FILE: A009C022_210414B3
"""  # noqa: W291
    statement_gen = edl_parser.statements_from_string(comments_string)
    event_comments = cmx_3600_reader.EventComments(statement_gen, edl_rate=24)

    assert event_comments.handled == {
        "asc_sat": 1.0,
        "asc_sop": {
            "slope": [1.0, 1.0, 1.0],
            "offset": [0.0, 0.0, 0.0],
            "power": [1.0, 1.0, 1.0],
        },
        "clip_name": "102-21-8A*",
        # "media_reference": "A009C022_210414B3",
    }
    assert event_comments.unhandled == [
        "M2      A009C022_210414B3                         012.0 16:39:36:18",
        "SOURCE FILE: A009C022_210414B3",
    ]

    assert event_comments.malformed == []


def test_comment_processing_transition():
    comments_string = """M2      D001C003_210414A7                         048.0 19:37:19:18 
*FROM CLIP NAME:  102-21D-3D* 96FPS 
*TO CLIP NAME:  102-21F-1A*_02 
*ASC_SOP (1.0000 1.0000 1.0000)(0.0000 0.0000 0.0000)(1.0000 1.0000 1.0000) 
*ASC_SAT 1 
*SOURCE FILE: D001C003_210414A7
"""  # noqa: W291
    statement_gen = edl_parser.statements_from_string(comments_string)
    event_comments = cmx_3600_reader.EventComments(statement_gen, edl_rate=24)

    assert event_comments.handled == {
        "asc_sat": 1.0,
        "asc_sop": {
            "slope": [1.0, 1.0, 1.0],
            "offset": [0.0, 0.0, 0.0],
            "power": [1.0, 1.0, 1.0],
        },
        "clip_name": "102-21D-3D* 96FPS",
        "dest_clip_name": "102-21F-1A*_02",
        # "media_reference": "D001C003_210414A7",
    }
    assert event_comments.unhandled == [
        "M2      D001C003_210414A7                         048.0 19:37:19:18",
        "SOURCE FILE: D001C003_210414A7",
    ]

    assert event_comments.malformed == []
