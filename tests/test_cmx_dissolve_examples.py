import opentimelineio as otio
from opentimelineio import opentime

from otio_cmx3600_adapter import cmx_3600_reader


def test_cmx_dissolve_case_1():
    transition_events = """001  001                B     C        02:00:00:00 02:00:00:00 01:00:00:00  01:00:00:00
    001  002                B     D    030 03:00:00:00 03:00:10:00 01:00:00:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)
    otio.adapters.write_to_file(tl, "/tmp/dissolve_1.otio")

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:00:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    assert dissolve.duration() == opentime.from_frames(30, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(30, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:10:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_dissolve_case_2():
    transition_events = """002  001                B     C        02:00:00:00 02:00:00:00 01:00:00:00  01:00:00:00
    002  002                B     D    030 03:00:00:00 03:00:10:00 01:00:00:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)
    otio.adapters.write_to_file(tl, "/tmp/dissolve_2.otio")

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:00:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    assert dissolve.duration() == opentime.from_frames(30, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(30, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:10:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_wipe_case_3():
    # This is modified from the original only in that it uses a wipe instead of
    # a dissolve. All timings are exactly as in the original example.
    transition_events = """003  001                B     C        02:00:00:00 02:00:09:00 01:00:00:00  01:00:09:00
    003  002                B     W019 030 03:00:00:00 03:00:01:00 01:00:09:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)
    otio.adapters.write_to_file(tl, "/tmp/dissolve_3.otio")

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:09:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    wipe = track[1]
    assert wipe.duration() == opentime.from_frames(30, 30)
    assert wipe.in_offset == opentime.from_frames(0, 30)
    assert wipe.out_offset == opentime.from_frames(30, 30)
    assert wipe.metadata["cmx_3600"]["transition"] == "W019"
    assert wipe.transition_type == "SMPTE_Wipe"

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:01:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_dissolve_case_4():
    transition_events = """004  001                B     C        02:00:00:00 02:00:08:00 01:00:00:00  01:00:08:00
    004  002                B     D    030 03:00:00:00 03:00:02:00 01:00:08:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)
    otio.adapters.write_to_file(tl, "/tmp/dissolve_4.otio")

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:08:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    assert dissolve.duration() == opentime.from_frames(30, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(30, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:02:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_dissolve_case_5():
    transition_events = """006  001                B     C        02:00:00:00 02:00:00:00 01:00:00:00  01:00:00:00
    006  002                B     D    255 03:00:00:00 03:00:08:15 01:00:00:00  01:00:08:15
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)
    otio.adapters.write_to_file(tl, "/tmp/dissolve_7.otio")

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:00:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    # The diagram in the spec shows this fade as 240 frames, but I think that's
    # an error because the description directly contradicts this
    assert dissolve.duration() == opentime.from_frames(255, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(255, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:08:15", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_dissolve_case_6():
    transition_events = """007  001                B     C        02:00:00:00 02:00:00:00 01:00:00:00  01:00:00:00
    007  002                B     D    225 03:00:00:00 03:00:10:00 01:00:00:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:00:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    # In the spec, it says the rate is 255, but the event has 225 and the
    # diagram has 240. I suspect this is an error in the provided example.
    # This test asserts the presumed expected behavior while it doesn't match
    # the spec.
    assert dissolve.duration() == opentime.from_frames(225, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(225, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:10:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }


def test_cmx_dissolve_case_7():
    transition_events = """001  001                B     C        02:00:00:00 02:00:05:00 01:00:00:00  01:00:05:00
    001  002                B     D    030 03:00:00:00 03:00:05:00 01:00:05:00  01:00:10:00
    """
    tl = cmx_3600_reader.read_from_string(transition_events, rate=30)

    track = tl.tracks[0]
    first_clip = track[0]
    assert first_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("02:00:00:00", 30),
        duration=opentime.from_timecode("00:00:05:00", 30),
    )
    assert first_clip.metadata["cmx_3600"]["reel"] == "001"

    dissolve = track[1]
    assert dissolve.duration() == opentime.from_frames(30, 30)
    assert dissolve.in_offset == opentime.from_frames(0, 30)
    assert dissolve.out_offset == opentime.from_frames(30, 30)

    second_clip = track[2]
    assert second_clip.source_range == opentime.TimeRange(
        start_time=opentime.from_timecode("03:00:00:00", 30),
        duration=opentime.from_timecode("00:00:05:00", 30),
    )
    assert second_clip.metadata["cmx_3600"]["reel"] == "002"

    assert len(tl.tracks) == 2
    assert set(track.kind for track in tl.tracks) == {
        otio.schema.TrackKind.Video, otio.schema.TrackKind.Audio
    }