#!/usr/bin/env python
#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the OpenTimelineIO project

"""Test the CMX 3600 EDL adapter."""

# python
import os
from pathlib import Path

import pytest
import opentimelineio as otio


# List of sample files used in tests
SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
SCREENING_EXAMPLE_PATH = os.path.join(SAMPLE_DATA_DIR, "screening_example.edl")
AVID_EXAMPLE_PATH = os.path.join(SAMPLE_DATA_DIR, "avid_example.edl")
NUCODA_EXAMPLE_PATH = os.path.join(SAMPLE_DATA_DIR, "nucoda_example.edl")
PREMIERE_EXAMPLE_PATH = os.path.join(SAMPLE_DATA_DIR, "premiere_example.edl")
EXEMPLE_25_FPS_PATH = os.path.join(SAMPLE_DATA_DIR, "25fps.edl")
NO_SPACES_PATH = os.path.join(SAMPLE_DATA_DIR, "no_spaces_test.edl")
DISSOLVE_TEST = os.path.join(SAMPLE_DATA_DIR, "dissolve_test.edl")
DISSOLVE_TEST_2 = os.path.join(SAMPLE_DATA_DIR, "dissolve_test_2.edl")
DISSOLVE_TEST_3 = os.path.join(SAMPLE_DATA_DIR, "dissolve_test_3.edl")
DISSOLVE_TEST_4 = os.path.join(SAMPLE_DATA_DIR, "dissolve_test_4.edl")
GAP_TEST = os.path.join(SAMPLE_DATA_DIR, "gap_test.edl")
WIPE_TEST = os.path.join(SAMPLE_DATA_DIR, "wipe_test.edl")
TIMECODE_MISMATCH_TEST = os.path.join(SAMPLE_DATA_DIR, "timecode_mismatch.edl")
SPEED_EFFECTS_TEST = os.path.join(SAMPLE_DATA_DIR, "speed_effects.edl")
SPEED_EFFECTS_TEST_SMALL = os.path.join(SAMPLE_DATA_DIR, "speed_effects_small.edl")
MULTIPLE_TARGET_AUDIO_PATH = os.path.join(SAMPLE_DATA_DIR, "multi_audio.edl")
TRANSITION_DURATION_TEST = os.path.join(SAMPLE_DATA_DIR, "transition_duration.edl")
ENABLED_TEST = os.path.join(SAMPLE_DATA_DIR, "enabled.otio")

DISSOLVE_TESTS = [DISSOLVE_TEST, DISSOLVE_TEST_2, DISSOLVE_TEST_3, DISSOLVE_TEST_4]


def test_edl_read(cmx_adapter):
    edl_path = SCREENING_EXAMPLE_PATH
    fps = 24
    timeline = cmx_adapter.read_from_file(edl_path)
    assert timeline is not None
    assert len(timeline.tracks) == 1
    assert len(timeline.tracks[0]) == 9
    assert timeline.tracks[0][0].name == "ZZ100_501 (LAY3)"
    assert timeline.tracks[0][0].source_range.duration == otio.opentime.from_timecode(
        "00:00:01:07", fps
    )
    assert timeline.tracks[0][1].name == "ZZ100_502A (LAY3)"
    assert timeline.tracks[0][1].source_range.duration == otio.opentime.from_timecode(
        "00:00:02:02", fps
    )
    assert timeline.tracks[0][2].name == "ZZ100_503A (LAY1)"
    assert timeline.tracks[0][2].source_range.duration == otio.opentime.from_timecode(
        "00:00:01:04", fps
    )
    assert timeline.tracks[0][3].name == "ZZ100_504C (LAY1)"
    assert timeline.tracks[0][3].source_range.duration == otio.opentime.from_timecode(
        "00:00:04:19", fps
    )

    assert len(timeline.tracks[0][3].markers) == 2
    marker = timeline.tracks[0][3].markers[0]
    assert marker.name == "ANIM FIX NEEDED"
    assert marker.metadata.get("cmx_3600").get("color") == "RED"
    assert marker.marked_range.start_time == otio.opentime.from_timecode(
        "01:00:01:14", fps
    )
    assert marker.color == otio.schema.MarkerColor.RED

    unnamed_marker = timeline.tracks[0][6].markers[0]
    assert unnamed_marker.name == ""

    assert timeline.tracks[0][4].name == "ZZ100_504B (LAY1)"
    assert timeline.tracks[0][4].source_range.duration == otio.opentime.from_timecode(
        "00:00:04:05", fps
    )
    assert timeline.tracks[0][5].name == "ZZ100_507C (LAY2)"
    assert timeline.tracks[0][5].source_range.duration == otio.opentime.from_timecode(
        "00:00:06:17", fps
    )
    assert timeline.tracks[0][6].name == "ZZ100_508 (LAY2)"
    assert timeline.tracks[0][6].source_range.duration == otio.opentime.from_timecode(
        "00:00:07:02", fps
    )
    assert timeline.tracks[0][7].name == "ZZ100_510 (LAY1)"
    assert timeline.tracks[0][7].source_range.duration == otio.opentime.from_timecode(
        "00:00:05:16", fps
    )
    assert timeline.tracks[0][8].name == "ZZ100_510B (LAY1)"
    assert timeline.tracks[0][8].source_range.duration == otio.opentime.from_timecode(
        "00:00:10:17", fps
    )


def test_reelname_length(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("test_timeline", tracks=[track])
    rt = otio.opentime.RationalTime(5.0, 24.0)

    long_mr = otio.schema.ExternalReference(
        target_url="/var/tmp/test_a_really_really_long_filename.mov"
    )

    tr = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(0.0, 24.0), duration=rt
    )

    cl = otio.schema.Clip(
        name="test clip1",
        media_reference=long_mr,
        source_range=tr,
    )

    track.name = "V1"
    track.append(cl)

    # Test default behavior
    result = cmx_adapter.write_to_string(tl)

    expected = """TITLE: test_timeline

001  testarea V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test clip1
* FROM CLIP: /var/tmp/test_a_really_really_long_filename.mov
* OTIO TRUNCATED REEL NAME FROM: test_a_really_really_long_filename.mov
"""

    assert result == expected

    # Keep full filename (minus extension) as reelname
    result = cmx_adapter.write_to_string(tl, reelname_len=None)
    expected = """TITLE: test_timeline

001  test_a_really_really_long_filename \
V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test clip1
* FROM CLIP: /var/tmp/test_a_really_really_long_filename.mov
"""

    assert result == expected

    # Make sure reel name is only 12 characters long
    result = cmx_adapter.write_to_string(tl, reelname_len=12)
    expected = """TITLE: test_timeline

001  testareallyr V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test clip1
* FROM CLIP: /var/tmp/test_a_really_really_long_filename.mov
* OTIO TRUNCATED REEL NAME FROM: test_a_really_really_long_filename.mov
"""

    assert result == expected


def test_edl_round_trip_mem2disk2mem(cmx_adapter, assertJsonEqual):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("test_timeline", tracks=[track])
    tl.global_start_time = otio.opentime.from_timecode("01:00:00:00", 24)
    rt = otio.opentime.RationalTime(5.0, 24.0)
    mr = otio.schema.ExternalReference(target_url="/var/tmp/test.mov")
    md = {
        "cmx_3600": {
            "reel": "test",
            "comments": ["OTIO TRUNCATED REEL NAME FROM: test.mov"],
        }
    }

    tr = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(0.0, 24.0), duration=rt
    )

    cl = otio.schema.Clip(
        name="test clip1", media_reference=mr, source_range=tr, metadata=md
    )
    cl2 = otio.schema.Clip(
        name="test clip2", media_reference=mr.clone(), source_range=tr, metadata=md
    )
    cl3 = otio.schema.Clip(
        name="test clip3", media_reference=mr.clone(), source_range=tr, metadata=md
    )
    cl4 = otio.schema.Clip(
        name="test clip3_ff", media_reference=mr.clone(), source_range=tr, metadata=md
    )

    cl4.effects[:] = [otio.schema.FreezeFrame()]
    cl5 = otio.schema.Clip(
        name="test clip5 (speed)",
        media_reference=mr.clone(),
        source_range=tr,
        metadata=md,
    )
    cl5.effects[:] = [otio.schema.LinearTimeWarp(time_scalar=2.0)]
    track.name = "V"
    track.append(cl)
    track.extend([cl2, cl3])
    track.append(cl4)
    track.append(cl5)

    result = cmx_adapter.write_to_string(tl)
    new_otio = cmx_adapter.read_from_string(result)

    # Cull out the metadata fields that are read-only
    del new_otio.metadata["cmx_3600"]
    delkeys = {"clip_name", "events", "original_timecode"}
    # TODO: replace this with children_if in otio 0.16.0
    for track in new_otio.tracks:
        for item in track:
            cmx_3600_metadata = item.metadata.get("cmx_3600", {})
            for key in delkeys:
                try:
                    del cmx_3600_metadata[key]
                except KeyError:
                    continue

    # directly compare clip with speed effect
    assert len(new_otio.tracks[0][3].effects) == 1
    assert new_otio.tracks[0][3].name == tl.tracks[0][3].name

    assertJsonEqual(new_otio, tl)

    # ensure that an error is raised if more than one effect is present
    cl5.effects.append(otio.schema.FreezeFrame())
    with pytest.raises(otio.exceptions.NotSupportedError):
        cmx_adapter.write_to_string(tl)

    # blank effect should pass through and be ignored
    cl5.effects[:] = [otio.schema.Effect()]
    cmx_adapter.write_to_string(tl)

    # but a timing effect should raise an exception
    cl5.effects[:] = [otio.schema.TimeEffect()]
    with pytest.raises(otio.exceptions.NotSupportedError):
        cmx_adapter.write_to_string(tl)


def test_edl_round_trip_disk2mem2disk_speed_effects(
    cmx_adapter, assertJsonEqual, tmp_path: Path
):
    test_edl = SPEED_EFFECTS_TEST_SMALL
    timeline = cmx_adapter.read_from_file(test_edl)

    tmp_path = os.path.join(
        tmp_path, "test_edl_round_trip_disk2mem2disk_speed_effects.edl"
    )

    cmx_adapter.write_to_file(timeline, tmp_path)

    result = cmx_adapter.read_from_file(tmp_path)

    # Due to how M2 speed factors may not match the timecode values
    # (they can be off by one), we special case check that clip and then
    # snap the metadata value back to what it originally was
    # We could consider overriding the value in the M2 speed with what
    # the TC says, but it's probably best to stay true to what the EDL
    # was signalling, who knows what TC rounding methods are used.
    cmx_metadata = result.tracks[0][-1].metadata["cmx_3600"]
    assert cmx_metadata["original_timecode"]["source_tc_out"] == "01:00:08:23"
    cmx_metadata["original_timecode"]["source_tc_out"] = "01:00:08:22"

    # When debugging, you can use this to see the difference in the OTIO
    # otio.adapters.otio_json.write_to_file(timeline, "/tmp/original.otio")
    # otio.adapters.otio_json.write_to_file(result, "/tmp/output.otio")
    # os.system("xxdiff /tmp/{original,output}.otio")

    # When debugging, use this to see the difference in the EDLs on disk
    # os.system("xxdiff {} {}&".format(test_edl, tmp_path))

    # The in-memory OTIO representation should be the same
    assertJsonEqual(timeline, result)


def test_edl_round_trip_disk2mem2disk(
    cmx_adapter, assertIsOTIOEquivalentTo, tmp_path: Path
):
    timeline = cmx_adapter.read_from_file(SCREENING_EXAMPLE_PATH)

    tmp_path = os.path.join(tmp_path, "test_edl_round_trip_disk2mem2disk.edl")

    cmx_adapter.write_to_file(timeline, tmp_path)

    result = cmx_adapter.read_from_file(tmp_path)

    # When debugging, you can use this to see the difference in the OTIO
    # otio.adapters.otio_json.write_to_file(timeline, "/tmp/original.otio")
    # otio.adapters.otio_json.write_to_file(result, "/tmp/output.otio")
    # os.system("opendiff /tmp/{original,output}.otio")

    original_json = otio.adapters.otio_json.write_to_string(timeline)
    output_json = otio.adapters.otio_json.write_to_string(result)
    assert original_json == output_json

    # The in-memory OTIO representation should be the same
    assertIsOTIOEquivalentTo(timeline, result)

    # When debugging, use this to see the difference in the EDLs on disk
    # os.system("opendiff {} {}".format(SCREENING_EXAMPLE_PATH, tmp_path))

    # But the EDL text on disk are *not* byte-for-byte identical
    with open(SCREENING_EXAMPLE_PATH) as original_file:
        with open(tmp_path) as output_file:
            assert original_file.read() != output_file.read()


def test_regex_flexibility(cmx_adapter, assertIsOTIOEquivalentTo):
    timeline = cmx_adapter.read_from_file(SCREENING_EXAMPLE_PATH)
    no_spaces = cmx_adapter.read_from_file(NO_SPACES_PATH)
    assertIsOTIOEquivalentTo(timeline, no_spaces)


def test_clip_with_tab_and_space_delimiters(cmx_adapter):
    timeline = cmx_adapter.read_from_string(
        "001  Z10 V  C\t\t01:00:04:05 01:00:05:12 00:59:53:11 00:59:54:18"
    )
    assert timeline is not None
    assert len(timeline.tracks) == 1
    assert timeline.tracks[0].kind == otio.schema.TrackKind.Video
    assert len(timeline.tracks[0]) == 1
    assert timeline.tracks[0][0].source_range.start_time.value == 86501
    assert timeline.tracks[0][0].source_range.duration.value == 31


def test_imagesequence_read(cmx_adapter):
    trunced_edl1 = """TITLE: Image Sequence Write

001  myimages V     C        01:00:01:00 01:00:02:12 00:00:00:00 00:00:01:12
* FROM CLIP NAME:  my_image_sequence
* FROM CLIP: /media/path/my_image_sequence.[1025-1060].ext
* OTIO TRUNCATED REEL NAME FROM: my_image_sequence.[1025-1060].ext
"""
    rate = 24
    tl1 = cmx_adapter.read_from_string(trunced_edl1, rate=rate)
    assert isinstance(tl1, otio.schema.Timeline)

    clip1 = tl1.tracks[0][0]
    media_ref1 = clip1.media_reference
    assert isinstance(media_ref1, otio.schema.ImageSequenceReference)
    assert media_ref1.start_frame == 1025
    assert media_ref1.end_frame() == 1060
    assert clip1.available_range() == otio.opentime.range_from_start_end_time(
        otio.opentime.from_timecode("01:00:01:00", rate),
        otio.opentime.from_timecode("01:00:02:12", rate),
    )

    # Make sure regex works and uses ExternalReference for non sequences
    trunced_edl2 = """TITLE: Image Sequence Write

001  myimages V     C        01:00:01:00 01:00:02:12 00:00:00:00 00:00:01:12
* FROM CLIP NAME:  my_image_sequence
* FROM CLIP: /media/path/my_image_file.1025.ext
* OTIO TRUNCATED REEL NAME FROM: my_image_file.1025.ext
"""

    tl2 = cmx_adapter.read_from_string(trunced_edl2, rate=rate)
    clip2 = tl2.tracks[0][0]
    media_ref2 = clip2.media_reference
    assert isinstance(media_ref2, otio.schema.ExternalReference)

    trunced_edl3 = """TITLE: Image Sequence Write

001  myimages V     C        01:00:01:00 01:00:02:12 00:00:00:00 00:00:01:12
* FROM CLIP NAME:  my_image_sequence
* FROM CLIP: /media/path/my_image_file.[1025].ext
* OTIO TRUNCATED REEL NAME FROM: my_image_file.[1025].ext
"""
    tl3 = cmx_adapter.read_from_string(trunced_edl3, rate=rate)
    clip3 = tl3.tracks[0][0]
    media_ref3 = clip3.media_reference
    assert isinstance(media_ref3, otio.schema.ExternalReference)


def test_imagesequence_write(cmx_adapter):
    rate = 24
    tl = otio.schema.Timeline("Image Sequence Write")
    track = otio.schema.Track("V1")
    tl.tracks.append(track)

    clip = otio.schema.Clip(
        name="my_image_sequence",
        source_range=otio.opentime.range_from_start_end_time(
            otio.opentime.from_timecode("01:00:01:00", rate),
            otio.opentime.from_timecode("01:00:02:12", rate),
        ),
        media_reference=otio.schema.ImageSequenceReference(
            target_url_base="/media/path/",
            name_prefix="my_image_sequence.",
            name_suffix=".ext",
            rate=rate,
            start_frame=1001,
            frame_zero_padding=4,
            available_range=otio.opentime.range_from_start_end_time(
                otio.opentime.from_timecode("01:00:00:00", rate),
                otio.opentime.from_timecode("01:00:03:00", rate),
            ),
        ),
    )
    track.append(clip)

    # Default behavior
    result1 = cmx_adapter.write_to_string(tl, rate=rate)

    expected_result1 = """TITLE: Image Sequence Write

001  myimages V     C        01:00:01:00 01:00:02:12 00:00:00:00 00:00:01:12
* FROM CLIP NAME:  my_image_sequence
* FROM CLIP: /media/path/my_image_sequence.[1025-1060].ext
* OTIO TRUNCATED REEL NAME FROM: my_image_sequence.[1025-1060].ext
"""
    assert result1 == expected_result1

    # Only trunc extension in reel name
    result2 = cmx_adapter.write_to_string(tl, rate=24, reelname_len=None)

    expected_result2 = """TITLE: Image Sequence Write

001  my_image_sequence.[1025-1060] V     C        \
01:00:01:00 01:00:02:12 00:00:00:00 00:00:01:12
* FROM CLIP NAME:  my_image_sequence
* FROM CLIP: /media/path/my_image_sequence.[1025-1060].ext
"""
    assert result2 == expected_result2


def test_dissolve_parse(cmx_adapter):
    tl = cmx_adapter.read_from_file(DISSOLVE_TEST)
    # clip/transition/clip/clip
    assert len(tl.tracks[0]) == 3

    assert isinstance(tl.tracks[0][1], otio.schema.Transition)
    assert tl.tracks[0][0].duration().value == 9
    # The visible range must contains all the frames needed for the transition
    # Edit duration + transition duration
    assert tl.tracks[0][0].visible_range().duration.to_frames() == 19
    assert tl.tracks[0][0].name == "clip_A"
    assert tl.tracks[0][1].duration().value == 10
    assert tl.tracks[0][1].name == "SMPTE_Dissolve from clip_A to clip_B"
    assert tl.tracks[0][2].duration().value == 11
    assert tl.tracks[0][2].visible_range().duration.value == 11
    assert tl.tracks[0][2].name == "clip_B"


def test_dissolve_parse_middle(cmx_adapter):
    tl = cmx_adapter.read_from_file(DISSOLVE_TEST_2)
    trck = tl.tracks[0]
    # 2 clips and 1 transition
    assert len(trck) == 3

    clip_a = trck[0]
    assert clip_a.name == "clip_A"
    assert clip_a.duration().value == 5
    assert clip_a.visible_range().duration.to_frames() == 15

    transition = trck[1]
    assert isinstance(trck[1], otio.schema.Transition)
    assert transition.duration().value == 10
    assert transition.name == "SMPTE_Dissolve from clip_A to clip_B"
    assert transition.transition_type == otio.schema.TransitionTypes.SMPTE_Dissolve

    clip_b = trck[2]
    assert (
        clip_b.source_range.start_time.value
        == otio.opentime.from_timecode("01:00:08:04", 24).value
    )
    assert clip_b.name == "clip_B"
    assert clip_b.duration().value == 15
    assert clip_b.visible_range().duration.value == 15


def test_dissolve_parse_full_clip_dissolve(cmx_adapter):
    tl = cmx_adapter.read_from_file(DISSOLVE_TEST_3)
    assert len(tl.tracks[0]) == 5

    assert isinstance(tl.tracks[0][2], otio.schema.Transition)

    trck = tl.tracks[0]
    clip_a = trck[0]
    assert clip_a.name == "Clip_A.mov"
    assert clip_a.duration().value == 61
    assert clip_a.visible_range().duration.value == 61

    clip_b = trck[1]
    assert clip_b.name == "Clip_B.mov"
    assert clip_b.duration().value == 0
    assert clip_b.visible_range().duration.value == 30

    transition = trck[2]
    # Note: clip names in the EDL are wrong, the transition is actually
    # from Clip_A to Clip_B
    assert transition.name == "SMPTE_Dissolve from Clip_B.mov to Clip_C.mov"
    assert transition.in_offset.value == 0
    assert transition.out_offset.value == 30

    clip_c = trck[3]
    assert clip_c.name == "Clip_C.mov"
    assert clip_c.source_range.start_time == otio.opentime.from_timecode(
        "01:00:33:22", 24
    )
    assert clip_c.duration().value == 30
    assert clip_c.visible_range().duration.value == 30

    clip_d = trck[4]
    assert clip_d.name == "Clip_D.mov"
    assert clip_d.source_range.start_time.value == 86400
    assert clip_d.duration().value == 46


def test_dissolve_with_odd_frame_count_maintains_length(cmx_adapter):
    # EXERCISE
    tl = cmx_adapter.read_from_string(
        "1 CLPA V C     00:00:04:17 00:00:07:02 00:00:00:00 00:00:02:09\n"
        "2 CLPA V C     00:00:07:02 00:00:07:02 00:00:02:09 00:00:02:09\n"
        "2 CLPB V D 027 00:00:06:18 00:00:07:21 00:00:02:09 00:00:03:12\n"
        "3 CLPB V C     00:00:07:21 00:00:15:21 00:00:03:12 00:00:11:12\n",
    )

    # VALIDATE
    assert tl.duration().value == (11 * 24) + 12


def test_wipe_parse(cmx_adapter):
    tl = cmx_adapter.read_from_file(WIPE_TEST)
    track = tl.tracks[0]
    assert len(track) == 3

    wipe = track[1]
    assert isinstance(wipe, otio.schema.Transition)
    assert wipe.transition_type == "SMPTE_Wipe"
    assert wipe.metadata["cmx_3600"]["transition"] == "W001"

    clip_a = track[0]
    assert clip_a.duration().value == 9
    assert clip_a.visible_range().duration.value == 9 + 10

    clip_b = track[2]
    assert clip_b.duration().value == 10 + 1
    assert clip_b.visible_range().duration.value == 10 + 1


def test_fade_to_black(cmx_adapter):
    # EXERCISE
    tl = cmx_adapter.read_from_string(
        "1 CLPA V C     00:00:03:18 00:00:12:15 00:00:00:00 00:00:08:21\n"
        "2 CLPA V C     00:00:12:15 00:00:12:15 00:00:08:21 00:00:08:21\n"
        "2 BL   V D 024 00:00:00:00 00:00:01:00 00:00:08:21 00:00:09:21\n",
    )

    # VALIDATE
    assert len(tl.tracks[0]) == 3
    assert isinstance(tl.tracks[0][1], otio.schema.Transition)
    assert isinstance(tl.tracks[0][2], otio.schema.Clip)
    assert tl.tracks[0][2].media_reference.generator_kind == "black"
    assert tl.tracks[0][2].duration().value == 24
    assert tl.tracks[0][2].source_range.start_time.value == 0


@pytest.mark.parametrize(
    "edl_file", DISSOLVE_TESTS, ids=[os.path.basename(path) for path in DISSOLVE_TESTS]
)
def test_edl_round_trip_with_transitions(cmx_adapter, tmp_path: Path, edl_file):
    # Notes:
    # - the writer does not handle wipes, only dissolves
    # - the writer can generate invalid EDLs if spaces are in reel names.
    edl_name = os.path.basename(edl_file)
    timeline = cmx_adapter.read_from_file(edl_file)
    tmp_path = os.path.join(tmp_path, f"test_edl_round_trip_{edl_name}")
    cmx_adapter.write_to_file(timeline, tmp_path)

    result = cmx_adapter.read_from_file(tmp_path)
    assert len(timeline.tracks) == len(result.tracks)
    for track, res_track in zip(timeline.tracks, result.tracks):
        assert len(track) == len(res_track)
        for child, res_child in zip(track, res_track):
            assert type(child) is type(res_child)
            if isinstance(child, otio.schema.Transition):
                assert child.in_offset == res_child.in_offset
                assert child.out_offset == res_child.out_offset
                assert child.transition_type == res_child.transition_type
            else:
                assert child.source_range == res_child.source_range


def test_edl_25fps(cmx_adapter):
    # EXERCISE
    edl_path = EXEMPLE_25_FPS_PATH
    fps = 25
    timeline = cmx_adapter.read_from_file(edl_path, rate=fps)
    track = timeline.tracks[0]
    assert track[0].source_range.duration.value == 161
    assert track[1].source_range.duration.value == 200
    assert track[2].source_range.duration.value == 86
    assert track[3].source_range.duration.value == 49


def test_record_gaps(cmx_adapter):
    edl_path = GAP_TEST
    timeline = cmx_adapter.read_from_file(edl_path)
    track = timeline.tracks[0]
    assert len(track) == 5
    assert track.duration().value == 5 * 24 + 6
    clip1, gapA, clip2, gapB, clip3 = track[:]
    assert clip1.source_range.duration.value == 24
    assert clip2.source_range.duration.value == 24
    assert clip3.source_range.duration.value == 24
    assert gapA.duration().value == 16
    assert gapB.duration().value == 38
    assert clip1.range_in_parent().duration.value == 24
    assert clip2.range_in_parent().duration.value == 24
    assert clip3.range_in_parent().duration.value == 24
    assert [item.range_in_parent() for item in track] == [
        otio.opentime.TimeRange(
            otio.opentime.from_frames(0, 24), otio.opentime.from_frames(24, 24)
        ),
        otio.opentime.TimeRange(
            otio.opentime.from_frames(24, 24), otio.opentime.from_frames(16, 24)
        ),
        otio.opentime.TimeRange(
            otio.opentime.from_frames(40, 24), otio.opentime.from_frames(24, 24)
        ),
        otio.opentime.TimeRange(
            otio.opentime.from_frames(64, 24), otio.opentime.from_frames(38, 24)
        ),
        otio.opentime.TimeRange(
            otio.opentime.from_frames(102, 24), otio.opentime.from_frames(24, 24)
        ),
    ]


def test_read_generators(cmx_adapter):
    # EXERCISE
    tl = cmx_adapter.read_from_string(
        "1 BL V C 00:00:00:00 00:00:01:00 00:00:00:00 00:00:01:00\n"
        "2 BLACK V C 00:00:00:00 00:00:01:00 00:00:01:00 00:00:02:00\n"
        "3 BARS V C 00:00:00:00 00:00:01:00 00:00:02:00 00:00:03:00\n",
    )

    # VALIDATE
    assert tl.tracks[0][0].media_reference.generator_kind == "black"
    assert tl.tracks[0][1].media_reference.generator_kind == "black"
    assert tl.tracks[0][2].media_reference.generator_kind == "SMPTEBars"


def test_style_edl_read(cmx_adapter, assertIsOTIOEquivalentTo):
    edl_paths = [AVID_EXAMPLE_PATH, NUCODA_EXAMPLE_PATH, PREMIERE_EXAMPLE_PATH]
    for edl_path in edl_paths:
        fps = 24
        timeline = cmx_adapter.read_from_file(edl_path)
        assert timeline is not None
        assert len(timeline.tracks) == 1
        assert len(timeline.tracks[0]) == 2

        # If cannot assertEqual fails with clip name
        # Attempt to assertEqual with
        try:
            assert timeline.tracks[0][0].name == "take_1"
        except AssertionError:
            assert timeline.tracks[0][0].name == "ZZ100_501.take_1.0001.exr"
        assert timeline.tracks[0][
            0
        ].source_range.duration == otio.opentime.from_timecode("00:00:01:07", fps)

        try:
            assertIsOTIOEquivalentTo(
                timeline.tracks[0][0].media_reference,
                otio.schema.ExternalReference(
                    target_url=r"S:\path\to\ZZ100_501.take_1.0001.exr"
                ),
            )
        except AssertionError:
            assertIsOTIOEquivalentTo(
                timeline.tracks[0][0].media_reference, otio.schema.MissingReference()
            )

        try:
            assert timeline.tracks[0][1].name == "take_2"
        except AssertionError:
            assert timeline.tracks[0][1].name == "ZZ100_502A.take_2.0101.exr"

        assert timeline.tracks[0][
            1
        ].source_range.duration == otio.opentime.from_timecode("00:00:02:02", fps)

        try:
            assertIsOTIOEquivalentTo(
                timeline.tracks[0][1].media_reference,
                otio.schema.ExternalReference(
                    target_url=r"S:\path\to\ZZ100_502A.take_2.0101.exr"
                ),
            )
        except AssertionError:
            assertIsOTIOEquivalentTo(
                timeline.tracks[0][1].media_reference, otio.schema.MissingReference()
            )


def test_style_edl_write(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("temp", tracks=[track])
    rt = otio.opentime.RationalTime(5.0, 24.0)
    mr = otio.schema.ExternalReference(target_url=r"S:/var/tmp/test.exr")

    tr = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(0.0, 24.0), duration=rt
    )
    cl = otio.schema.Clip(
        name="test clip1",
        media_reference=mr,
        source_range=tr,
    )
    gap = otio.schema.Gap(
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        )
    )
    cl2 = otio.schema.Clip(
        name="test clip2",
        media_reference=mr.clone(),
        source_range=tr,
    )
    tl.tracks[0].name = "V"
    tl.tracks[0].append(cl)
    tl.tracks[0].append(gap)
    tl.tracks[0].append(cl2)

    tl.name = "test_nucoda_timeline"
    result = cmx_adapter.write_to_string(tl, style="nucoda")

    expected = r"""TITLE: test_nucoda_timeline

001  test     V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test clip1
* FROM FILE: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
002  test     V     C        00:00:00:00 00:00:00:05 00:00:01:05 00:00:01:10
* FROM CLIP NAME:  test clip2
* FROM FILE: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
"""

    assert result == expected

    tl.name = "test_avid_timeline"
    result = cmx_adapter.write_to_string(tl, style="avid")

    expected = r"""TITLE: test_avid_timeline

001  test     V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test clip1
* FROM CLIP: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
002  test     V     C        00:00:00:00 00:00:00:05 00:00:01:05 00:00:01:10
* FROM CLIP NAME:  test clip2
* FROM CLIP: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
"""

    assert result == expected

    tl.name = "test_premiere_timeline"
    result = cmx_adapter.write_to_string(tl, style="premiere")

    expected = r"""TITLE: test_premiere_timeline

001  AX       V     C        00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05
* FROM CLIP NAME:  test.exr
* OTIO REFERENCE FROM: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
002  AX       V     C        00:00:00:00 00:00:00:05 00:00:01:05 00:00:01:10
* FROM CLIP NAME:  test.exr
* OTIO REFERENCE FROM: S:/var/tmp/test.exr
* OTIO TRUNCATED REEL NAME FROM: test.exr
"""

    assert result == expected


def test_reels_edl_round_trip_string2mem2string(cmx_adapter):
    sample_data = r"""TITLE: Reels_Example.01

001  ZZ100_50 V     C        01:00:04:05 01:00:05:12 00:59:53:11 00:59:54:18
* FROM CLIP NAME:  take_1
* FROM FILE: S:/path/to/ZZ100_501.take_1.0001.exr
002  ZZ100_50 V     C        01:00:06:13 01:00:08:15 00:59:54:18 00:59:56:20
* FROM CLIP NAME:  take_2
* FROM FILE: S:/path/to/ZZ100_502A.take_2.0101.exr
"""

    timeline = cmx_adapter.read_from_string(sample_data)
    otio_data = cmx_adapter.write_to_string(timeline, style="nucoda")
    assert sample_data == otio_data


def test_nucoda_edl_write_with_transition(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("Example CrossDissolve", tracks=[track])

    cl = otio.schema.Clip(
        "Clip1",
        metadata={"cmx_3600": {"reel": "Clip1"}},
        media_reference=otio.schema.ExternalReference(
            target_url="/var/tmp/clip1.001.exr"
        ),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(131.0, 24.0),
            duration=otio.opentime.RationalTime(102.0, 24.0),
        ),
    )
    trans = otio.schema.Transition(
        in_offset=otio.opentime.RationalTime(57.0, 24.0),
        out_offset=otio.opentime.RationalTime(43.0, 24.0),
    )
    cl2 = otio.schema.Clip(
        "Clip2",
        metadata={"cmx_3600": {"reel": "Clip2"}},
        media_reference=otio.schema.ExternalReference(
            target_url="/var/tmp/clip2.001.exr"
        ),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(280.0, 24.0),
            duration=otio.opentime.RationalTime(143.0, 24.0),
        ),
    )
    cl3 = otio.schema.Clip(
        "Clip3",
        metadata={"cmx_3600": {"reel": "Clip3"}},
        media_reference=otio.schema.ExternalReference(
            target_url="/var/tmp/clip3.001.exr"
        ),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(0.0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        ),
    )
    tl.tracks[0].extend([cl, trans, cl2, cl3])

    result = cmx_adapter.write_to_string(tl, style="nucoda")

    expected = r"""TITLE: Example CrossDissolve

001  Clip1    V     C        00:00:05:11 00:00:07:08 00:00:00:00 00:00:01:21
* FROM CLIP NAME:  Clip1
* FROM FILE: /var/tmp/clip1.001.exr
002  Clip1    V     C        00:00:07:08 00:00:07:08 00:00:01:21 00:00:01:21
002  Clip2    V     D 100    00:00:09:07 00:00:17:15 00:00:01:21 00:00:10:05
* FROM CLIP NAME:  Clip1
* FROM FILE: /var/tmp/clip1.001.exr
* TO CLIP NAME:  Clip2
* TO FILE: /var/tmp/clip2.001.exr
003  Clip3    V     C        00:00:00:00 00:00:01:00 00:00:10:05 00:00:11:05
* FROM CLIP NAME:  Clip3
* FROM FILE: /var/tmp/clip3.001.exr
"""

    assert result == expected


def test_nucoda_edl_write_fade_in(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("Example Fade In", tracks=[track])

    trans = otio.schema.Transition(
        in_offset=otio.opentime.RationalTime(0.0, 24.0),
        out_offset=otio.opentime.RationalTime(12.0, 24.0),
    )
    cl = otio.schema.Clip(
        "My Clip",
        metadata={"cmx_3600": {"reel": "My_Clip"}},
        media_reference=otio.schema.ExternalReference(
            target_url="/var/tmp/clip.001.exr"
        ),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(50.0, 24.0),
            duration=otio.opentime.RationalTime(26.0, 24.0),
        ),
    )
    tl.tracks[0].extend([trans, cl])

    result = cmx_adapter.write_to_string(tl, style="nucoda")

    expected = r"""TITLE: Example Fade In

001  BL       V     C        00:00:00:00 00:00:00:00 00:00:00:00 00:00:00:00
001  My_Clip  V     D 012    00:00:02:02 00:00:03:04 00:00:00:00 00:00:01:02
* TO CLIP NAME:  My Clip
* TO FILE: /var/tmp/clip.001.exr
"""

    assert result == expected


def test_nucoda_edl_write_fade_out(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("Example Fade Out", tracks=[track])

    cl = otio.schema.Clip(
        "My Clip",
        metadata={"cmx_3600": {"reel": "My_Clip"}},
        media_reference=otio.schema.ExternalReference(
            target_url="/var/tmp/clip.001.exr"
        ),
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(24.0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        ),
    )
    trans = otio.schema.Transition(
        in_offset=otio.opentime.RationalTime(12.0, 24.0),
        out_offset=otio.opentime.RationalTime(0.0, 24.0),
    )
    tl.tracks[0].extend([cl, trans])

    result = cmx_adapter.write_to_string(tl, style="nucoda")

    expected = r"""TITLE: Example Fade Out

001  My_Clip  V     C        00:00:01:00 00:00:01:12 00:00:00:00 00:00:00:12
* FROM CLIP NAME:  My Clip
* FROM FILE: /var/tmp/clip.001.exr
002  My_Clip  V     C        00:00:01:12 00:00:01:12 00:00:00:12 00:00:00:12
002  BL       V     D 012    00:00:00:00 00:00:00:12 00:00:00:12 00:00:01:00
* FROM CLIP NAME:  My Clip
* FROM FILE: /var/tmp/clip.001.exr
"""

    assert result == expected


def test_nucoda_edl_write_with_double_transition(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline("Double Transition", tracks=[track])

    cl = otio.schema.Clip(
        metadata={"cmx_3600": {"reel": "Reel1"}},
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(24.0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        ),
    )
    trans = otio.schema.Transition(
        in_offset=otio.opentime.RationalTime(6.0, 24.0),
        out_offset=otio.opentime.RationalTime(6.0, 24.0),
    )
    cl2 = otio.schema.Clip(
        metadata={"cmx_3600": {"reel": "Reel2"}},
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(24.0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        ),
    )
    trans2 = otio.schema.Transition(
        in_offset=otio.opentime.RationalTime(6.0, 24.0),
        out_offset=otio.opentime.RationalTime(6.0, 24.0),
    )
    cl3 = otio.schema.Clip(
        metadata={"cmx_3600": {"reel": "Reel3"}},
        source_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(24.0, 24.0),
            duration=otio.opentime.RationalTime(24.0, 24.0),
        ),
    )
    tl.tracks[0].extend([cl, trans, cl2, trans2, cl3])

    result = cmx_adapter.write_to_string(tl, style="nucoda")

    expected = """TITLE: Double Transition

001  Reel1    V     C        00:00:01:00 00:00:01:18 00:00:00:00 00:00:00:18
002  Reel1    V     C        00:00:01:18 00:00:01:18 00:00:00:18 00:00:00:18
002  Reel2    V     D 012    00:00:00:18 00:00:01:18 00:00:00:18 00:00:01:18
003  Reel2    V     C        00:00:01:18 00:00:01:18 00:00:01:18 00:00:01:18
003  Reel3    V     D 012    00:00:00:18 00:00:02:00 00:00:01:18 00:00:03:00
"""

    assert result == expected


def test_read_edl_with_multiple_target_audio_tracks(cmx_adapter):
    tl = cmx_adapter.read_from_file(MULTIPLE_TARGET_AUDIO_PATH)

    assert len(tl.audio_tracks()) == 2

    first_track, second_track = tl.audio_tracks()
    assert first_track.name == "A1"
    assert second_track.name == "A2"

    assert first_track[0].name == "AX"
    assert second_track[0].name == "AX"

    expected_range = otio.opentime.TimeRange(
        duration=otio.opentime.from_timecode("00:56:55:22", rate=24)
    )
    assert first_track[0].source_range == expected_range
    assert second_track[0].source_range == expected_range


def test_custom_reel_names(cmx_adapter):
    track = otio.schema.Track()
    tl = otio.schema.Timeline(tracks=[track])
    tr = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(1.0, 24.0),
        duration=otio.opentime.RationalTime(24.0, 24.0),
    )
    cl = otio.schema.Clip(source_range=tr)
    cl.metadata["cmx_3600"] = {"reel": "v330_21f"}
    tl.tracks[0].append(cl)

    result = cmx_adapter.write_to_string(tl, style="nucoda")

    assert (
        result == "001  v330_21f V     C        "
        "00:00:00:01 00:00:01:01 00:00:00:00 00:00:01:00\n"
    )


def test_invalid_edl_style_raises_exception(cmx_adapter):
    tl = cmx_adapter.read_from_string(
        "001  AX       V     C        "
        "00:00:00:00 00:00:00:05 00:00:00:00 00:00:00:05\n",
    )
    with pytest.raises(otio.exceptions.NotSupportedError):
        cmx_adapter.write_to_string(tl, style="bogus")


def test_invalid_record_timecode(cmx_adapter):
    # There are timecodes beyond the 23 frame limit in this EDL that cause a
    # ValueError when parsed at 24fps.
    with pytest.raises(ValueError):
        cmx_adapter.read_from_file(TIMECODE_MISMATCH_TEST)

    tl = cmx_adapter.read_from_file(TIMECODE_MISMATCH_TEST, rate=25)
    expected_duration = otio.opentime.from_timecode(
        "00:00:19:19", 25
    ) - otio.opentime.from_timecode("00:00:17:22", 25)
    assert tl.tracks[0][3].range_in_parent() == otio.opentime.TimeRange(
        start_time=otio.opentime.from_timecode("00:00:17:22", 25),
        duration=expected_duration,
    )


def test_can_read_frame_cut_points(cmx_adapter):
    # EXERCISE
    tl = cmx_adapter.read_from_string(
        "1 CLPA V C     113 170 0 57\n"
        "2 CLPA V C     170 170 57 57\n"
        "2 CLPB V D 027 162 189 57 84\n"
        "3 CLPB V C     189 381 84 276\n",
    )

    # VALIDATE
    assert tl.duration().value == 276
    assert len(tl.tracks) == 1

    track = tl.tracks[0]
    assert len(track) == 3

    clip_a = track[0]
    assert clip_a.duration().value == 57
    assert clip_a.visible_range().duration.value == 57 + 27

    transition = track[1]
    assert transition.in_offset.value == 0
    assert transition.out_offset.value == 27

    clip_b = track[2]
    assert clip_b.duration().value == 27 + (381 - 189)


def test_speed_effects(cmx_adapter):
    tl = cmx_adapter.read_from_file(SPEED_EFFECTS_TEST)
    assert tl.duration() == otio.opentime.from_timecode("00:21:03:18", 24)

    # Look for a clip with a freeze frame effect
    clip = tl.tracks[0][182]
    assert clip.name == "Z682_156 (LAY3)"
    assert clip.effects and clip.effects[0].effect_name == "FreezeFrame"
    assert clip.duration() == otio.opentime.from_timecode("00:00:00:17", 24)
    clip = tl.tracks[0][182]
    # TODO: We should be able to ask for the source without the effect
    # assert clip.source_range == otio.opentime.TimeRange(
    #     start_time=otio.opentime.from_timecode("01:00:10:21", 24),
    #     duration=otio.opentime.from_timecode("00:00:00:01", 24)
    # )
    assert clip.range_in_parent() == otio.opentime.TimeRange(
        start_time=otio.opentime.from_timecode("00:08:30:00", 24),
        duration=otio.opentime.from_timecode("00:00:00:17", 24),
    )

    # Look for a clip with an M2 effect
    clip = tl.tracks[0][281]
    assert clip.name == "Z686_5A (LAY2) (47.56 FPS)"
    assert clip.effects and clip.effects[0].effect_name == "LinearTimeWarp"
    assert abs(clip.effects[0].time_scalar - 1.98333333) == pytest.approx(
        0, abs=0.0000001
    )

    assert clip.metadata.get("cmx_3600", {}).get("motion") is None
    assert clip.duration() == otio.opentime.from_timecode("00:00:01:12", 24)
    # TODO: We should be able to ask for the source without the effect
    # clip.source_range == otio.opentime.TimeRange(
    #     start_time=otio.opentime.from_timecode("01:00:06:00", 24),
    #     duration=otio.opentime.from_timecode("00:00:02:22", 24)
    # )
    assert clip.range_in_parent() == otio.opentime.TimeRange(
        start_time=otio.opentime.from_timecode("00:11:31:16", 24),
        duration=otio.opentime.from_timecode("00:00:01:12", 24),
    )


def test_transition_duration(cmx_adapter):
    tl = cmx_adapter.read_from_file(TRANSITION_DURATION_TEST)
    assert len(tl.tracks[0]) == 5

    assert isinstance(tl.tracks[0][2], otio.schema.Transition)

    assert tl.tracks[0][2].duration().value == 26.0


def test_three_part_transition(cmx_adapter):
    """
    Test A->B->C Transition
    """
    tl = cmx_adapter.read_from_file(DISSOLVE_TEST_4)
    assert len(tl.tracks[0]) == 10

    track = tl.tracks[0]

    abc0000 = track[0]
    assert abc0000.duration().value == 30.0

    abc0010 = track[1]
    assert abc0010.duration().value == 51.0

    abc0020_1 = track[2]
    assert abc0020_1.duration().value == 0
    assert abc0020_1.visible_range().duration.value == 35

    transition_1 = track[3]
    assert isinstance(transition_1, otio.schema.Transition)
    assert transition_1.duration().value == 35.0

    abc0020_2 = track[4]
    event_3_duration = otio.opentime.from_timecode(
        "01:00:10:07", 24
    ) - otio.opentime.from_timecode("01:00:06:22", 24)
    assert abc0020_2.duration() == event_3_duration
    assert abc0020_2.visible_range().duration == event_3_duration

    abc030_1 = track[5]
    assert abc030_1.visible_range().duration.value == 64.0

    transition_2 = track[6]
    assert isinstance(transition_2, otio.schema.Transition)
    assert transition_2.duration().value == 64.0

    abc030_2 = track[7]
    assert abc030_2.duration().value == 84.0
    assert abc030_2.visible_range().duration.value == 84.0
    assert track[8].duration().value == 96.0
    assert track[9].duration().value == 135.0


def test_enabled(cmx_adapter):
    tl = otio.adapters.read_from_file(ENABLED_TEST)
    # Exception is raised because the OTIO file has two tracks and cmx_3600 only
    # supports one
    with pytest.raises(otio.exceptions.NotSupportedError):
        cmx_adapter.write_to_string(tl)

    # Disable top track so we only have one track
    tl.tracks[1].enabled = False
    result = cmx_adapter.write_to_string(tl)
    expected = r"""TITLE: enable_test

001  Clip001  V     C        00:00:00:00 00:00:00:03 00:00:00:00 00:00:00:03
* FROM CLIP NAME:  Clip-001
* OTIO TRUNCATED REEL NAME FROM: Clip-001
002  Clip002  V     C        00:00:00:03 00:00:00:06 00:00:00:03 00:00:00:06
* FROM CLIP NAME:  Clip-002
* OTIO TRUNCATED REEL NAME FROM: Clip-002
"""

    assert result == expected

    # Disable first clip in the track
    tl.tracks[0].find_children()[0].enabled = False
    result = cmx_adapter.write_to_string(tl)
    expected = r"""TITLE: enable_test

001  Clip002  V     C        00:00:00:03 00:00:00:06 00:00:00:03 00:00:00:06
* FROM CLIP NAME:  Clip-002
* OTIO TRUNCATED REEL NAME FROM: Clip-002
"""

    assert result == expected
