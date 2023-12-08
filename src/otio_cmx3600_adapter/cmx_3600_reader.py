"""
Implementation notes:

## ignore_timecode_mismatch now has different behavior
1. It treats timeline duration as sacred (rather than source) this is based on
 the guess that most source timecode mismatches are because they are at a
 different and unguessable rate than the timeline and therefore unreliable.
2. It will ignore rate mismatches in source timecode on the assumption that the
 above is happening.
"""

import collections
import copy
import functools
import itertools
import os
import re
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional, Union

import opentimelineio as otio
from opentimelineio import opentime

from .exceptions import EDLParseError
from . import edl_parser
from .edl_statement import (
    EDLStatement,
    EffectType,
    NoteFormStatement,
    SpecialSource,
    StandardFormStatement,
)


METADATA_NAMESPACE = "cmx_3600"
TIMECODE_WAS_ADJUSTED_KEY = "timecode_was_adjusted"


# CMX_3600 supports some shorthand for channel assignments
# We name the actual tracks V and A1,A2,A3,etc.
# This channel_map tells you which track to use for each channel shorthand.
# Channels not listed here are used as track names verbatim.
CHANNEL_MAP = {
    "A": ["A1"],
    "AA": ["A1", "A2"],
    "B": ["V", "A1"],
    "A2/V": ["V", "A2"],
    "AA/V": ["V", "A1", "A2"],
}


def read_from_file(
    filepath,
    rate=24,
    ignore_timecode_mismatch=True,
    ignore_invalid_timecode_errors=False,
):
    try:
        with open(filepath) as fo:
            contents = fo.read()
    except UnicodeDecodeError:
        # attempt ISO-8859-1, this sometimes works better than UTF-8
        with open(filepath, encoding="iso-8859-1") as fo:
            contents = fo.read()

    return read_from_string(
        contents, rate, ignore_timecode_mismatch, ignore_invalid_timecode_errors
    )


def read_from_string(
    input_str,
    rate=24,
    ignore_timecode_mismatch=True,
    ignore_invalid_timecode_errors=False,
):
    if not ignore_timecode_mismatch:
        raise DeprecationWarning(
            "ignore_timecode_mismatch is now always enabled."
        )
    reader = EDLReader(
        edl_rate=rate,
        ignore_invalid_timecode_errors=ignore_invalid_timecode_errors,
    )
    reader.load_from_statements(edl_parser.statements_from_string(input_str))

    # The reader returns a timeline per TITLE entry, if there are multiples
    # wrap them in a bin first.
    if len(reader.timelines) > 1:
        return otio.schema.SerializableCollection(children=reader.timelines)

    return reader.timelines[0]


def _deep_update(to_update: Mapping, updates: Mapping):
    """
    Like dict.update, but does deep merging on nested mappings.
    """
    for key, value in updates.items():
        try:
            existing_value = to_update[key]
        except KeyError:
            existing_value = None

        # if they're both mappings, recurse
        if isinstance(existing_value, Mapping) and isinstance(value, Mapping):
            _deep_update(existing_value, value)
            continue

        # otherwise, stomp
        to_update[key] = value


class EventComments:
    # this should be a map of all known comments that we can read
    # 'FROM CLIP' or 'FROM FILE' is a required comment to link media
    # An exception is raised if both 'FROM CLIP' and 'FROM FILE' are found
    # needs to be ordered so that FROM CLIP NAME gets matched before FROM CLIP
    HANDLED_NOTE_STATEMENTS = collections.OrderedDict(
        [
            (NoteFormStatement.NoteFormIdentifiers.FROM_CLIP_NAME, "clip_name"),
            (NoteFormStatement.NoteFormIdentifiers.TO_CLIP_NAME, "dest_clip_name"),
            (NoteFormStatement.NoteFormIdentifiers.FROM_CLIP, "media_reference"),
            (NoteFormStatement.NoteFormIdentifiers.FROM_FILE, "media_reference"),
            # (NoteFormStatement.NoteFormIdentifiers.SOURCE_FILE, "media_reference"),
            (NoteFormStatement.NoteFormIdentifiers.LOC, "locators"),
            (NoteFormStatement.NoteFormIdentifiers.ASC_SOP, "asc_sop"),
            (NoteFormStatement.NoteFormIdentifiers.ASC_SAT, "asc_sat"),
            (NoteFormStatement.NoteFormIdentifiers.FREEZE_FRAME, "freeze_frame"),
            (NoteFormStatement.NoteFormIdentifiers.OTIO_REFERENCE, "media_reference"),
        ]
    )

    ASC_SOP_REGEX = re.compile(r"([+-]*\d+\.\d+)")

    DEFAULT_ASC_SOP = dict(
        slope=[1.0] * 3,
        offset=[0.0] * 3,
        power=[1.0] * 3,
    )
    DEFAULT_ASC_SAT = 1.0

    def __init__(self, comments: Iterable[NoteFormStatement], edl_rate: float):
        self.handled = {}
        self.unhandled: list[str] = []
        self.malformed: list[NoteFormStatement] = []
        self.edl_rate = edl_rate
        for comment in comments:
            try:
                self.process_note_statement(comment)
            except (ValueError, EDLParseError, IndexError):
                # TODO: we should add exception details here
                self.unhandled.append(comment.statement_text)
                self.malformed.append(comment)

    def process_note_statement(self, statement: NoteFormStatement):
        # TODO: This is the basic handling, need to handle special recognized comments
        #   like CDL
        #
        note_form_identifier = statement.statement_identifier
        if note_form_identifier is None:
            self.unhandled.append(statement.statement_text)
            return

        if note_form_identifier not in self.HANDLED_NOTE_STATEMENTS:
            self.unhandled.append(statement.statement_text)
            return

        # Handle the well-known notes in order of which should win for it's
        # destination key
        for identifier, key in self.HANDLED_NOTE_STATEMENTS.items():
            if identifier is not note_form_identifier:
                continue

            if identifier is NoteFormStatement.NoteFormIdentifiers.LOC:
                marker = self.marker_for_locator_comment(statement)
                if marker is not None:
                    self.handled.setdefault(key, []).append(marker)
            elif key in self.handled:
                # Only handle the first source for any given destination key
                # except locators
                self.unhandled.append(statement.statement_text)
                continue
            elif key == "media_reference":
                # These are the comments that will drive the media ref
                self.handled[key] = statement.data
            elif key == "asc_sat":
                self.handled[key] = self.parsed_asc_sat(statement.data)
            elif key == "asc_sop":
                self.handled[key] = self.parsed_asc_sop(statement.data)
            else:
                self.handled[key] = statement.data
            break

    def parsed_asc_sat(self, sat_data: str) -> float:
        return float(sat_data)

    def parsed_asc_sop(self, sop_data: str):
        if not isinstance(sop_data, str):
            return {}

        asc_sop_values = self.ASC_SOP_REGEX.findall(sop_data)

        if len(asc_sop_values) >= 9:
            asc_sop = dict(
                slope=[float(v) for v in asc_sop_values[:3]],
                offset=[float(v) for v in asc_sop_values[3:6]],
                power=[float(v) for v in asc_sop_values[6:9]],
            )
        else:
            raise EDLParseError(f"Invalid ASC_SOP found: {sop_data}")

        return asc_sop

    def marker_for_locator_comment(
        self, statement: NoteFormStatement
    ) -> Optional[otio.schema.Marker]:
        # An example EDL locator line looks like this:
        # * LOC: 01:00:01:14 RED     ANIM FIX NEEDED
        m = re.match(r"(\d\d:\d\d:\d\d:\d\d)\s+(\w*)(\s+|$)(.*)", statement.data)
        if not m:
            # TODO: Should we report this as a warning somehow?
            return None

        marker = otio.schema.Marker()
        marker_timecode = m.group(1)
        marker_time, time_was_adjusted = from_timecode_approx(
            marker_timecode, self.edl_rate, True
        )
        marker.marked_range = otio.opentime.TimeRange(
            start_time=marker_time,
            duration=opentime.RationalTime(),
        )

        # always write the source value into metadata, in case it
        # is not a valid enum somehow.
        color_parsed_from_file = m.group(2)

        cmx_metadata = {
            "color": color_parsed_from_file,
            "timecode": marker_timecode,
        }
        if time_was_adjusted:
            cmx_metadata[TIMECODE_WAS_ADJUSTED_KEY] = True

        marker.metadata[METADATA_NAMESPACE] = cmx_metadata

        # @TODO: if it is a valid
        if hasattr(otio.schema.MarkerColor, color_parsed_from_file.upper()):
            marker.color = color_parsed_from_file.upper()
        else:
            marker.color = otio.schema.MarkerColor.RED

        marker.name = m.group(4)

        return marker


class EDLReader:
    # /path/filename.[1001-1020].ext
    IMAGE_SEQUENCE_PATTERN = re.compile(
        r".*\.(?P<range>\[(?P<start>[0-9]+)-(?P<end>[0-9]+)\])\.\w+$"
    )

    def __init__(
        self,
        edl_rate=24,
        ignore_invalid_timecode_errors=False,
    ):
        """

        Args:
            edl_rate:
            ignore_record_timeline_errors: If a record timecode is invalid,
             drops the frame count off the end and uses that value (floor to the nearest second)
        """
        self.timelines: list[otio.schema.Timeline] = []
        self.current_timeline = otio.schema.Timeline()
        self.tracks_by_name: dict[str, otio.schema.Track] = {}
        self.video_tracks: list[otio.schema.Track] = []
        # We set this as a flag rather than checking
        # current_timeline.global_start_time is None because if the first
        # timecode is unparsable we don't want to put an incorrect timecode in
        self.handled_timeline_init = False
        self.current_timeline_start_offset = None
        self._edl_rate = edl_rate
        self.ignore_invalid_timecode_errors = ignore_invalid_timecode_errors

    @property
    def current_timeline(self) -> otio.schema.Timeline:
        return self._current_timeline

    @current_timeline.setter
    def current_timeline(self, new_timeline: otio.schema.Timeline):
        self.timelines.append(new_timeline)
        self._current_timeline = new_timeline
        self.tracks_by_name = {track.name: track for track in new_timeline.tracks}
        self.video_tracks = [
            track for track in new_timeline.tracks if track.kind == otio.schema.TrackKind.Video
        ]
        self.handled_timeline_init = False
        self.current_timeline_start_offset = None

    def add_track(self, track: otio.schema.Track):
        # For performance reasons, we want to cache the tracks_by_name mapping
        self._current_timeline.tracks.append(track)
        self.tracks_by_name[track.name] = track
        if track.kind == otio.schema.TrackKind.Video:
            self.video_tracks.append(track)

    def load_from_statements(self, statements: Iterator[EDLStatement]):
        event_statements = []
        current_event = None
        for statement in statements:
            should_start_new_event = False

            # Handle top-level NoteFormStatements
            if isinstance(statement, NoteFormStatement) and not statement.is_comment:
                statement_identifier = statement.statement_identifier

                if statement_identifier is NoteFormStatement.NoteFormIdentifiers.FCM:
                    # We ignore this for now on the assumption that the timecodes
                    # use either ; or : to denote drop/non-drop
                    continue
                elif (
                    statement_identifier is NoteFormStatement.NoteFormIdentifiers.TITLE
                ):
                    # If the current timeline already has a name, that means we
                    # encountered a second TITLE directive an it's the start of
                    # a new title
                    if (
                        self.current_timeline.name
                        and self.current_timeline.name != statement.data
                    ):
                        self.current_timeline = otio.schema.Timeline()
                    self.current_timeline.name = statement.data
                    continue
                elif (
                    statement_identifier is NoteFormStatement.NoteFormIdentifiers.SPLIT
                ):
                    # SPLIT notes appy to the following event
                    # TODO: How do we make the edit number on this statement not win?
                    # Perhaps the loop keeps a None Edit number until it hits an explicit one?
                    should_start_new_event = True

            # accumulate statements in the same event
            edit_number_changed = (
                current_event is not None
                and not statement.is_edit_number_inferred
                and statement.normalized_edit_number != current_event
            )
            should_start_new_event = should_start_new_event or edit_number_changed
            if not should_start_new_event:
                event_statements.append(statement)
                if current_event is None and not statement.is_edit_number_inferred:
                    current_event = statement.normalized_edit_number
                continue

            # We're starting a new event, process the current statements
            if event_statements:
                self.process_event_statements(event_statements)

            event_statements = []
            current_event = (
                statement.normalized_edit_number
                if not statement.is_edit_number_inferred
                else None
            )
            event_statements.append(statement)

        # handle unprocessed statements when we get to EOF
        if event_statements:
            self.process_event_statements(event_statements)

    @property
    def edit_rate(self) -> float:
        """
        Returns the resolved rate to use for record timecodes based on a combo
        of user provided EDL frame rate and any `TIME_CODE_MODULUS` statements
        encountered in the EDL.
        """
        # TIME_CODE_MODULUS not yet supported - it's only for SMPTE EDLs which
        # we haven't really observed in the wild with our users.
        return self._edl_rate

    def make_clip(
        self,
        statement: StandardFormStatement,
        event_comments: EventComments,
        is_from_clip: bool,
    ) -> otio.schema.Clip:
        """
        Generates a best-effort clip for the standard identifier. Depending on
        the context, the identifier may require some additional contextual data
        to fully resolve timing.
        """
        if is_from_clip:
            comment_ref_data = event_comments.handled.get("media_reference")
        else:
            comment_ref_data = None
        media_ref = self.media_reference_for_statement(statement, comment_ref_data)
        clip: otio.schema.Clip = otio.schema.Clip(
            name=statement.edit_number,
            media_reference=media_ref,
        )
        cmx_metadata = {}
        clip_metadata = {METADATA_NAMESPACE: cmx_metadata}

        # Copy metadata
        if is_from_clip:
            clip_name_key = "clip_name"
            # Copy all the metadata except the TO clip info
            if (
                "asc_sop" in event_comments.handled
                or "asc_sat" in event_comments.handled
            ):
                sop = event_comments.handled.get(
                    "asc_sop", EventComments.DEFAULT_ASC_SOP
                )
                sat = event_comments.handled.get(
                    "asc_sat", EventComments.DEFAULT_ASC_SAT
                )

                clip_metadata["cdl"] = dict(asc_sat=sat, asc_sop=sop)

            if "locators" in event_comments.handled:
                clip.markers.extend(event_comments.handled["locators"])

            if event_comments.unhandled:
                cmx_metadata["comments"] = event_comments.unhandled

        else:
            clip_name_key = "dest_clip_name"

        # get the clip name
        comment_clip_name = event_comments.handled.get(clip_name_key)
        clip.name = self.name_for_clip(clip, comment_clip_name, statement.edit_number)
        # Stash the canonical clip name or None so downstream consumers can tell
        # if the otio clip.name was inferred
        cmx_metadata["clip_name"] = comment_clip_name

        # A reel name of `AX` represents an unknown or auxilary source
        # We don't currently track these sources outside of this adapter
        # So lets skip adding AX reels as metadata for now,
        # as that would dirty json outputs with non-relevant information
        if statement.source_identification != "AX":
            cmx_metadata["reel"] = statement.source_identification

        # Copy useful metadata from the statement
        cmx_metadata["original_timecode"] = {
            "source_tc_in": statement.source_entry,
            "source_tc_out": statement.source_exit,
            "record_tc_in": statement.sync_entry,
            "record_tc_out": statement.sync_exit,
        }
        cmx_metadata["events"] = [statement.edit_number]

        clip.metadata.update(clip_metadata)

        return clip

    def name_for_clip(
        self,
        clip: otio.schema.Clip,
        comment_clip_name: Optional[str],
        edit_number: str,
    ) -> str:
        # If an explicit FROM or TO CLIP NAME was provided in comments, use it
        if comment_clip_name:
            return comment_clip_name
        elif (
            clip.media_reference
            and hasattr(clip.media_reference, "target_url")
            and clip.media_reference.target_url is not None
        ):
            return Path(clip.media_reference.target_url).stem
        elif (
            clip.media_reference
            and hasattr(clip.media_reference, "target_url_base")
            and clip.media_reference.target_url_base is not None
        ):
            return Path(_get_image_sequence_url(clip)).stem

        # Fallback on the event number
        return edit_number

    def media_reference_for_statement(
        self, statement: StandardFormStatement, comment_ref_data: Optional[str]
    ) -> otio.core.MediaReference:
        media_reference = otio.schema.MissingReference()
        special_source = statement.special_source
        if special_source is SpecialSource.BLACK:
            media_reference = otio.schema.GeneratorReference(
                # TODO: Replace with enum, once one exists
                generator_kind="black"
            )
        elif special_source is SpecialSource.BARS:
            media_reference = otio.schema.GeneratorReference(
                # TODO: Replace with enum, once one exists
                generator_kind="SMPTEBars"
            )
        elif comment_ref_data is not None:
            image_sequence_match = self.IMAGE_SEQUENCE_PATTERN.search(comment_ref_data)
            if image_sequence_match is not None:
                path, basename = os.path.split(comment_ref_data)
                prefix, suffix = basename.split(image_sequence_match.group("range"))
                start_frame = int(image_sequence_match.group("start"))
                end_frame = int(image_sequence_match.group("end"))
                duration_frames = end_frame - start_frame + 1
                start_time, _ = from_timecode_approx(
                    statement.source_entry,
                    self.edit_rate,
                    self.ignore_invalid_timecode_errors,
                )
                media_reference = otio.schema.ImageSequenceReference(
                    target_url_base=path,
                    name_prefix=prefix,
                    name_suffix=suffix,
                    rate=self.edit_rate,
                    start_frame=start_frame,
                    frame_zero_padding=len(image_sequence_match.group("start")),
                    available_range=otio.opentime.TimeRange(
                        start_time=start_time,
                        duration=opentime.from_frames(duration_frames, self.edit_rate),
                    ),
                )
            else:
                media_reference = otio.schema.ExternalReference(
                    target_url=comment_ref_data
                )

        return media_reference

    def make_transition(
        self, statement: StandardFormStatement
    ) -> otio.schema.Transition:
        # TODO: PORT THIS TO STATEMENT-BASED
        effect = statement.effect
        if effect.type == EffectType.WIPE:
            otio_transition_type = "SMPTE_Wipe"
        elif effect.type == EffectType.DISSOLVE:
            otio_transition_type = otio.schema.TransitionTypes.SMPTE_Dissolve
        else:
            raise EDLParseError(
                f"Transition type '{effect.type}' on line {statement.line_number}"
                " not supported by the CMX EDL reader currently."
            )

        if effect.transition_duration is None:
            raise EDLParseError(
                f"Transition type '{effect.type}' on line {statement.line_number}"
                "is missing a duration."
            )
        transition_duration = opentime.RationalTime(
            effect.transition_duration,
            self.edit_rate,
        )

        new_trx = otio.schema.Transition(
            name=otio_transition_type,
            # only supported type at the moment
            transition_type=otio_transition_type,
            metadata={
                "cmx_3600": {
                    "transition": statement.edit_type,
                    "transition_duration": transition_duration.value,
                    "events": [statement.edit_number],
                },
            },
        )
        new_trx.in_offset = opentime.RationalTime(0, transition_duration.rate)
        new_trx.out_offset = transition_duration
        return new_trx

    def apply_timing_effect(self, statement: NoteFormStatement, clip: otio.schema.Clip):
        if (
            statement.statement_identifier
            is NoteFormStatement.NoteFormIdentifiers.FREEZE_FRAME
        ):
            # XXX remove 'FF' suffix (writing edl will add it back)
            if clip.name.endswith(" FF"):
                clip.name = clip.name[:-3]
        elif (
            statement.statement_identifier
            is NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY
        ):
            time_scalar = float(statement.motion_directive.speed) / self.edit_rate
            if time_scalar == 0.0:
                clip.effects.append(otio.schema.FreezeFrame())
            else:
                clip.effects.append(otio.schema.LinearTimeWarp(time_scalar=time_scalar))
        else:
            raise ValueError(
                f"Cannot apply statement as a motion statement: {statement}"
            )

    def process_event_statements(self, statements: list[EDLStatement]):
        """
        Converts a group of EDL statements associated with a single event into
        OTIO objects and places them on the timeline.
        """
        if not statements:
            return

        # Handle statements not associated with an event
        # (this should be very rare)
        explicit_edit_number_present = any(
            True
            for statement in statements
            if not statement.is_edit_number_inferred and statement.edit_number
        )
        if not explicit_edit_number_present:
            # Make all statements into timeline comments
            cmx_metadata = self.current_timeline.metadata.setdefault(
                METADATA_NAMESPACE, {}
            )
            cmx_metadata.setdefault("comments", []).extend(
                statement.statement_text
                for statement in statements
                if hasattr(statement, "statement_text")
            )
            return

        # Separate the statements by type and apply processing
        non_motion_notes = (
            statement
            for statement in statements
            if isinstance(statement, NoteFormStatement)
            and not statement.statement_identifier
            == NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY
        )
        comments = EventComments(non_motion_notes, self.edit_rate)

        standard_form_statements: list[StandardFormStatement] = [
            statement
            for statement in statements
            if isinstance(statement, StandardFormStatement)
        ]
        has_transition = any(
            True
            for statement in standard_form_statements
            if statement.edit_type != EffectType.CUT.value
        )

        # Process the edit
        edit_items_by_channels: dict[
            str, list[Union[otio.schema.Clip, otio.schema.Transition]]
        ] = {}
        for source_idx, statement in enumerate(standard_form_statements):
            # The "from" clip is any clip that is the first source in a
            # transition
            # If there is no transition then audio and video can have multiple
            # statements, treat audio and video as "FROM" clips
            is_from_clip = not has_transition or source_idx == 0

            # Make the clip for the statement
            clip = self.make_clip(statement, comments, is_from_clip)

            # if the statement includes a transition, make that transition and
            # add it ahead of the clip it transitions to
            if statement.effect.type != EffectType.CUT:
                transition = self.make_transition(statement)

                # Give the transition a more context-aware name if we can
                transition_name = f"{transition.transition_type} to {clip.name}"
                if "dest_clip_name" in comments.handled:
                    if "clip_name" in comments.handled:
                        transition_name = "{} from {} to {}".format(
                            transition.transition_type,
                            comments.handled["clip_name"],
                            comments.handled["dest_clip_name"],
                        )

                transition.name = transition_name
                edit_items_by_channels.setdefault(statement.channels, []).append(
                    transition
                )

            edit_items_by_channels.setdefault(statement.channels, []).append(clip)

            # Handle any timeline level stuff - e.g. the global start time is
            # the record in timecode of the first event.
            if not self.handled_timeline_init:
                tl_cmx_metadata = self.current_timeline.metadata.setdefault(
                    METADATA_NAMESPACE, {}
                )
                tl_cmx_metadata["edl_rate"] = self.edit_rate
                try:
                    self.current_timeline.global_start_time, was_adjusted = from_timecode_approx(
                        statement.sync_entry,
                        self.edit_rate,
                        self.ignore_invalid_timecode_errors,
                    )
                    if was_adjusted:
                        tl_cmx_metadata[TIMECODE_WAS_ADJUSTED_KEY] = True
                except ValueError:
                    tl_cmx_metadata.setdefault("parsing_info", []).append(
                        f"EDL start timecode {statement.sync_entry} couldn't be parsed"
                    )
                self.handled_timeline_init = True

        motion_statement_identifiers = [
            NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY,
            NoteFormStatement.NoteFormIdentifiers.FREEZE_FRAME,
        ]
        motion_statements = [
            statement
            for statement in statements
            if isinstance(statement, NoteFormStatement)
            and statement.statement_identifier in motion_statement_identifiers
        ]

        for motion_statement in motion_statements:
            event_clips = [
                item
                for item in itertools.chain.from_iterable(
                    edit_items for edit_items in edit_items_by_channels.values()
                )
                if isinstance(item, otio.schema.Clip)
            ]
            effected_clip = event_clips[0]
            # Freeze frame statements provide no additional context so they simply
            # apply to the first available clip
            if (
                motion_statement.statement_identifier
                is NoteFormStatement.NoteFormIdentifiers.FREEZE_FRAME
            ):
                self.apply_timing_effect(motion_statement, effected_clip)
                continue

            # Try to match the M2 effect to a clip on the reel name
            motion_directive = motion_statement.motion_directive
            try:
                effected_clip = next(
                    clip
                    for clip in event_clips
                    if clip.metadata[METADATA_NAMESPACE].get("reel")
                    == motion_directive.reel
                )
            except StopIteration:
                # no exact match, just apply to the first clip
                pass
            self.apply_timing_effect(motion_statement, effected_clip)

        for channels, edit_items in edit_items_by_channels.items():
            timeline_range = self.resolve_timings_for_event_items(edit_items)
            self.place_items_in_timeline(edit_items, timeline_range, channels)

    def tracks_for_channel(
            self, channel_code: str, timeline_range: opentime.TimeRange
    ) -> list[otio.schema.Track]:
        # Expand channel shorthand into a list of track names.
        if channel_code in CHANNEL_MAP:
            track_names = CHANNEL_MAP[channel_code]
        else:
            track_names = [channel_code]

        # Get the tracks, creating any channels we don't already have
        relative_start_time = (
                timeline_range.start_time - self.current_timeline_start_offset
        )
        out_tracks = []
        for track_name in track_names:
            try:
                track = self.tracks_by_name[track_name]
            except KeyError:
                track = otio.schema.Track(
                    name=track_name, kind=_guess_kind_for_track_name(track_name)
                )
                if track.kind == otio.schema.TrackKind.Video:
                    self.video_tracks.append(track)
                self.add_track(track)

            # Check for overlaps
            if relative_start_time < track.duration():
                children = track.children_in_range(timeline_range)
                # TODO: If all the children found are Gaps, they could be
                #   replaced with the items with correct surrounding gaps below
                if len(children) > 0 and track.kind == otio.schema.TrackKind.Video:
                    # Look for (or create) another video track with open space
                    # for the items
                    for overlay_track in self.video_tracks:
                        if overlay_track is track:
                            continue
                        overlay_children = overlay_track.children_in_range(timeline_range)
                        if len(overlay_children) == 0:
                            track = overlay_track
                            break
                    else:
                        # No track found, make a new one
                        track_name = f"V{len(self.video_tracks) + 1}"
                        track = otio.schema.Track(
                            name=track_name, kind=otio.schema.TrackKind.Video
                        )
                        self.add_track(track)
                elif len(children) > 0:
                    # Don't resolve audio overwrites, unsure of the intent in these cases
                    raise EDLParseError(
                        f"Channel {channel_code} has existing content at {timeline_range}"
                    )

            out_tracks.append(track)

        # Return a list of actual tracks
        return out_tracks

    def place_items_in_timeline(
        self,
        items: list[otio.core.Item],
        timeline_range: opentime.TimeRange,
        channels: str,
    ):
        # The first event record timecode is the global start time
        if self.current_timeline_start_offset is None:
            self.current_timeline_start_offset = timeline_range.start_time

        # Find the candidate track
        try:
            target_tracks: list[otio.schema.Track] = self.tracks_for_channel(
                channels, timeline_range
            )
        except EDLParseError:
            # Remake the exception with improved context
            events = sorted(
                set(
                    itertools.chain.from_iterable(
                        item.metadata.get(METADATA_NAMESPACE, {}).get(
                            "events"
                        )
                        for item in items
                    )
                )
            )
            raise EDLParseError(
                f"Overlapping record in value for event{'s' if len(events) > 1 else ''}"
                f" {', '.join(events)}"
            )

        for destination_track in target_tracks:
            # Make sure the gap properly offsets items in the track
            relative_start_time = (
                timeline_range.start_time - self.current_timeline_start_offset
            )
            if relative_start_time > destination_track.duration():
                destination_track.append(
                    otio.schema.Gap(
                        source_range=opentime.TimeRange(
                            start_time=opentime.RationalTime(
                                0, relative_start_time.rate
                            ),
                            duration=relative_start_time - destination_track.duration(),
                        )
                    )
                )
            elif _should_merge_clip_to_track(items[0], destination_track):
                # extend the source range of the first clip by the second clip
                # duration, add the second clip's event numbers and discard the
                # second clip
                appending_clip = items[0]
                existing_clip = destination_track[-1]
                added_time = appending_clip.duration().rescaled_to(
                    existing_clip.duration().rate
                )
                existing_clip.source_range = opentime.TimeRange(
                    start_time=existing_clip.source_range.start_time,
                    duration=existing_clip.duration() + added_time,
                )
                appending_cmx_metadata = appending_clip.metadata[METADATA_NAMESPACE]
                existing_events = existing_clip.metadata[METADATA_NAMESPACE].get(
                    "events", []
                )
                for event_number in appending_cmx_metadata.get("events", []):
                    if event_number not in existing_events:
                        existing_events.append(event_number)

                existing_clip.metadata[METADATA_NAMESPACE][
                    "events"
                ] = existing_events
                items = items[1:]

            if len(target_tracks) > 1:
                destination_track.extend(copy.deepcopy(items))
            else:
                destination_track.extend(items)

    def resolve_timings_for_event_items(
        self, items: list[Union[otio.schema.Clip, otio.schema.Transition]]
    ) -> opentime.TimeRange:
        """
        Resolves the timings for the group of items in an event.
        Returns the bounds the items should occupy in the timeline.
        """
        """
        Timeline timing:
        - for each clip in event, use rec start for timeline placement
        - If a clip has a rec end time different from the start, use it
        
        Clip Timing:
        - After the timeline has been resolved and all event statements have been
            processed, back calculate source duration through any time warps from the
            timeline timing
        - The source of truth for source timing is always the Timecode values
        """
        # first, establish resolved record time ranges for all clips
        clip_record_ranges: list[opentime.TimeRange] = []
        previous_range_is_implicit = False
        clips = [item for item in items if isinstance(item, otio.schema.Clip)]
        for clip in clips:
            clip_timecode_metadata = clip.metadata[METADATA_NAMESPACE][
                "original_timecode"
            ]
            record_tc_in = clip_timecode_metadata["record_tc_in"]
            record_tc_out = clip_timecode_metadata["record_tc_out"]

            record_range, rec_tc_adjusted = from_timecode_range_approx(
                record_tc_in, record_tc_out, self.edit_rate, self.ignore_invalid_timecode_errors
            )
            if rec_tc_adjusted:
                clip.metadata[METADATA_NAMESPACE][f"record_{TIMECODE_WAS_ADJUSTED_KEY}"] = True

            # If the previous range is implicit, extend it based on context
            if previous_range_is_implicit:
                previous_record_range = clip_record_ranges[-1]
                # Run the range up to the start of this clip
                previous_record_range = opentime.range_from_start_end_time(
                    previous_record_range.start_time, record_range.start_time
                )
                clip_record_ranges[-1] = previous_record_range

            clip_record_ranges.append(record_range)

            # Note this clip needs its record range adjusted
            previous_range_is_implicit = record_tc_in == record_tc_out

        # Now resolve the source ranges in terms of the timeline ranges
        for record_range, clip in zip(clip_record_ranges, clips):
            clip_timecode_metadata = clip.metadata[METADATA_NAMESPACE][
                "original_timecode"
            ]
            src_tc_in = clip_timecode_metadata["source_tc_in"]
            src_tc_out = clip_timecode_metadata["source_tc_out"]

            src_range, src_tc_adjusted = from_timecode_range_approx(
                src_tc_in, src_tc_out, self.edit_rate, self.ignore_invalid_timecode_errors
            )
            if src_tc_adjusted:
                clip.metadata[METADATA_NAMESPACE][f"source_{TIMECODE_WAS_ADJUSTED_KEY}"] = True

            # Determine what the source duration should be back-calculated from
            # the timeline duration
            calculated_src_duration = record_range.duration.rescaled_to(
                src_range.start_time.rate
            )

            # Most source/timeline mismatches are due to a source timecode rate
            # that doesn't match the timeline. Since the source timing isn't
            # trustworthy in these cases, we favor protecting the overall
            # timeline timing.
            clip.source_range = opentime.TimeRange(
                src_range.start_time, calculated_src_duration
            )

            record_tc_in = clip_timecode_metadata["record_tc_in"]
            record_tc_out = clip_timecode_metadata["record_tc_out"]
            duration_is_implicit = record_tc_in == record_tc_out
            durations_match = record_range.duration == src_range.duration
            if not durations_match and not duration_is_implicit:
                clip_has_timing_effect = (
                    len(
                        [
                            effect
                            for effect in clip.effects
                            if isinstance(effect, otio.schema.TimeEffect)
                        ]
                    )
                    >= 1
                )
                if not clip_has_timing_effect:
                    # Tag possibly erroneous timing
                    clip.metadata[METADATA_NAMESPACE]["had_timecode_mismatch"] = True

                """
                # Sometimes the math doesn't work out for various rounding and
                # M2 precision issues. The fix below would favor the speed
                # change described by the timecodes rather than the M2 effect
                # This would be a debatable change
                else:
                    # Calculate an effective time scalar to use for the warp
                    # based on the timings in the EDL
                    linear_time_warps = [
                        effect for effect in clip.effects
                        if isinstance(effect, otio.schema.LinearTimeWarp)
                        and not effect.time_scalar == 0.0
                    ]
                    if len(linear_time_warps) == 1:
                        time_warp = linear_time_warps[0]
                        calculated_time_scalar = (
                            src_range.duration.to_seconds() /
                            record_range.duration.to_seconds()
                        )
                        time_warp.time_scalar = calculated_time_scalar
                """

        return opentime.TimeRange(
            start_time=clip_record_ranges[0].start_time,
            duration=sum(
                (r.duration for r in clip_record_ranges),
                opentime.RationalTime(0, self.edit_rate),
            ),
        )


def from_timecode_approx(
    timecode: str, rate: float, ignore_invalid_timecode_errors=False
) -> tuple[opentime.RationalTime, bool]:
    """
    Generates a time for the provided timecode according to the
    ignore_invalid_timecode_errors policy.

    If ignore_invalid_timecode_errors is True, invalid timecode will be
    interpreted at the rate of 1 + the frame count. This should get the
    value pretty close in a lot of cases - within the second at least.

    :returns: a tuple of (time, did_adjust_to_rate)
    """
    # Handle EDLs with frame numbers instead of TC
    if ":" not in timecode and ";" not in timecode:
        timecode = opentime.to_timecode(
            opentime.from_frames(int(timecode), rate),
            rate,
        )

    timecode_exception = None
    try:
        return opentime.from_timecode(timecode, rate=rate), False
    except ValueError as e:
        if ignore_invalid_timecode_errors:
            timecode_exception = e
        else:
            raise e

    # Attempt to interpret the doctored timecode
    tc_parts = re.split("[:;]", timecode)
    if tc_parts is None or len(tc_parts) != 4:
        raise timecode_exception

    try:
        tc_parts = [int(part) for part in tc_parts]
    except ValueError:
        raise timecode_exception

    tc_frame_count = tc_parts[-1]
    # Infer a rate from known rates
    # This list is derived from:
    # https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/17e92975080b32a26c6c3ded2b5750b31b9910a2/src/opentime/rationalTime.cpp#L41-L58
    known_rates = [1, 12, 24, 25, 30, 48, 50, 60]
    inferred_rate = tc_frame_count + 1
    for rate in known_rates:
        if rate > tc_frame_count:
            inferred_rate = rate
            break
    try:
        return opentime.from_timecode(timecode, rate=inferred_rate), True
    except ValueError:
        raise timecode_exception


def from_timecode_range_approx(
        start_timecode: str, end_timecode: str,  rate: float, ignore_invalid_timecode_errors=False
) -> tuple[opentime.TimeRange, bool]:
    """
    Generates a time range for the provided timecodes, adjusting them if invalid for the rate.

    Returns a tuple of the time range and a boolean indicating if the timecodes were adjusted.
    """
    start_time, did_adjust_start_timecode = from_timecode_approx(
        start_timecode, rate, ignore_invalid_timecode_errors
    )
    end_time, did_adjust_end_timecode = from_timecode_approx(
        end_timecode, rate, ignore_invalid_timecode_errors
    )
    time_range = opentime.range_from_start_end_time(start_time, end_time)

    return time_range, did_adjust_start_timecode or did_adjust_end_timecode


def _get_image_sequence_url(clip):
    ref = clip.media_reference
    start_frame, end_frame = ref.frame_range_for_time_range(clip.trimmed_range())

    frame_range_str = "[{start}-{end}]".format(start=start_frame, end=end_frame)

    url = clip.media_reference.abstract_target_url(frame_range_str)

    return url


def _clips_are_continuous(clip_1: otio.schema.Clip, clip_2: otio.schema.Clip) -> bool:
    """
    Assuming clip_2 immediately follows clip_1 in a track, checks to see if
    clip_2 is continuous in the source from clip_1.
    """
    # Check to make sure they're coming from the same source
    clip_1_reel = clip_1.metadata.get(METADATA_NAMESPACE, {}).get("reel")
    clip_2_reel = clip_2.metadata.get(METADATA_NAMESPACE, {}).get("reel")
    if clip_1_reel != clip_2_reel:
        return False

    if type(clip_1.media_reference) != type(clip_2.media_reference):
        return False

    if hasattr(clip_1, "target_url"):
        if clip_1.target_url != clip_2.target_url:
            return False

    # check the preceding clip to see if it can merge with the first one
    # in our set
    previous_end = clip_1.source_range.end_time_exclusive()
    next_start = clip_2.source_range.start_time
    if previous_end != next_start:
        # clip source ranges are not "continuous" and can't be melded
        return False

    # Make sure the net effect of the time warps is the same
    clip_1_time_scalar = functools.reduce(
        lambda x, y: (x * y.time_scalar),
        (
            effect
            for effect in clip_1.effects
            if isinstance(effect, otio.schema.LinearTimeWarp)
        ),
        1,
    )
    clip_2_time_scalar = functools.reduce(
        lambda x, y: (x * y.time_scalar),
        (
            effect
            for effect in clip_2.effects
            if isinstance(effect, otio.schema.LinearTimeWarp)
        ),
        1,
    )
    # TODO: These are floats, should we be applying some tolerance to this?
    #   if so, what tolerance is reasonable
    return clip_1_time_scalar == clip_2_time_scalar


def _guess_kind_for_track_name(name):
    if name.startswith("V"):
        return otio.schema.TrackKind.Video
    if name.startswith("A"):
        return otio.schema.TrackKind.Audio
    return otio.schema.TrackKind.Video


def _should_merge_clip_to_track(
    clip: otio.schema.Clip, track: otio.schema.Track
) -> bool:
    # If there's nothing to merge to, then don't
    if len(track) == 0:
        return False

    # only merge clips to clips
    existing_item = track[-1]
    if not isinstance(existing_item, otio.schema.Clip):
        return False
    # When to elide:
    # If the clip is zero length (due to transition-based implicit duration)
    # and the existing clip is continuous, merge them
    if clip.duration().value == 0:
        return _clips_are_continuous(existing_item, clip)

    if len(track) < 2:
        return False

    item_before_existing = track[-2]
    if not isinstance(item_before_existing, otio.schema.Transition):
        return False

    clip_is_all_transition = item_before_existing.out_offset == existing_item.duration()

    return _clips_are_continuous(existing_item, clip)