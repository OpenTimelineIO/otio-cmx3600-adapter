"""
This module contains a direct data model representing base EDL statements and
elements. This is strongly based on the modeling presented in the CMX edl
specification, but also pulls ideas from SMPTE 258M-2004.
In addition to those specifications, this parser also uses techniques based on
empirical data from EDLs in the wild for a more pragmatic approach targeting the
varied dialects of EDL in modern usage.
"""

import functools
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from functools import cached_property
from typing import Optional

from .exceptions import EDLParseError

class SourceMode(Enum):
    """
    Which source type the edit applies to.
    """
    VIDEO = "V"
    AUDIO = "A"
    BOTH = "B"
    AUDIO_2 = "A2"
    AUDIO_2_VIDEO = "A2/Y"
    AUDIO_1_AUDIO_2 = "AA"
    AUDIO_1_AUDIO_2_VIDEO = "AA/V"


class EffectType(Enum):
    """
    Type of effect.
    """
    # Single source effects
    CUT = "C"
    SYNC_ROLL = "R"

    # Multiple source effects
    DISSOLVE = "D"
    WIPE = "W"
    KEY = "K"
    KEY_BACKGROUND = "KB"
    KEY_REMOVE = "KO"
    MATTE = "M"
    FOREGROUND_FILLER = "F"
    QUAD_SPLIT = "Q"
    NONADDITIVE_MIX = "N"
    AUDIO_MIX = "X"


class SpecialSource(Enum):
    # BLACK/BL and BARS are called out as "Special Source Identifiers" in
    # the documents referenced here:
    # https://github.com/AcademySoftwareFoundation/OpenTimelineIO#cmx3600-edl
    AUX = "AX"
    BLACK = "BLACK"
    BARS = "BARS"

    @classmethod
    def _missing_(cls, value):
        if value == "BL":
            return cls.BLACK
        elif value == "SMPTEBars":
            return cls.BARS


@dataclass
class Effect:
    type: EffectType = EffectType.CUT
    parameter: Optional[str] = None
    wipe_type: Optional[str] = None

    WIPE_RE = re.compile(r"W(?P<wipe_type>\d{3})")

    @classmethod
    def from_statement(cls, statement: "StandardFormStatement"):
        effect = cls()
        try:
            effect.type = EffectType(statement.edit_type)
        except ValueError as e:
            wipe_match = effect.WIPE_RE.match(statement.edit_type)
            if wipe_match:
                effect.type = EffectType.WIPE
                effect.wipe_type = wipe_match.group("wipe_type")
            else:
                raise e

        if statement.edit_parameter:
            effect.parameter = statement.edit_parameter

        return effect

    @property
    def transition_duration(self) -> Optional[int]:
        """
        Duration in frames of the transition, if supplied.
        If the effect is not a transition, raises ValueError.
        """
        if self.type not in [EffectType.DISSOLVE, EffectType.KEY, EffectType.WIPE]:
            raise ValueError(
                f"transition_duration is not available for {self.type} effects."
            )

        return int(self.parameter) if self.parameter else None


@dataclass
class MotionDirective:
    reel: str
    speed: Decimal
    trigger: str

    # regex for parsing the playback speed of an M2 event
    SPEED_EFFECT_RE = re.compile(
        r"(?P<reel>.*?)\s*(?P<speed>-?[0-9\.]*)\s*(?P<trigger>[0-9:]{11})$"
    )

    @classmethod
    def from_string(cls, motion_directive: str):
        match = cls.SPEED_EFFECT_RE.match(motion_directive)
        if match is None:
            raise EDLParseError(
                f"Unsupported M2 Effect format: '{motion_directive}'"
            )

        return cls(
            reel=match.group("reel"),
            speed=Decimal(match.group("speed")),
            trigger=match.group("trigger"),
        )


@dataclass
class EDLStatement:
    line_number: int = 0
    """The line number of the element, where the first line in the file is 1."""

    is_supported: bool = False

    edit_number: Optional[str] = None
    """The Edit number - sometimes called event number"""

    is_virtual_edit: Optional[bool] = None

    is_recorded: Optional[bool] = None

    is_edit_number_inferred: bool = False
    """``True`` if ``edit_number`` was inferred from a preceeding element"""

    @property
    def normalized_edit_number(self) -> Optional[str]:
        """
        The normalized version of the edit number that will be comparable across
        all elements in the same edit.

        For example, edit number 055 and 000055 are the same, despite the
        textual difference.
        """
        if self.edit_number is None:
            return None

        # Remove any zero padding
        return self.edit_number.lstrip("0")


@dataclass
class UnsupportedStatement(EDLStatement):
    statement_text: str = None


@dataclass
class NoteFormStatement(EDLStatement):
    """
    This is used for all well-known note form statements.
    """
    class NoteFormIdentifiers(Enum):
        # System directives (From SMPTE 258M)
        TITLE = "TITLE"  # Also in CMX
        WAIT = "WAIT"
        SKIP = "SKIP"
        BELL = "BELL"
        RECORD = "RECORD"
        NORECORD = "NORECORD"
        SLAVE = "SLAVE"
        NOSLAVE = "NOSLAVE"
        AUDIO = "AUDIO"
        INCLUDE = "INCLUDE"
        MEDIUM = "MEDIUM"
        WIPES = "WIPES"
        MOTION_CURVE = "MOTION_CURVE"
        # in SMPTE258M a comment can be a system directive, but we don't treat
        # them as such in this parser.

        # Header Statements (From SMPTE 258M)
        TIME_CODE_MODULUS = "TIME_CODE_MODULUS"

        # Note form Statements (from CMX)
        FCM = "FCM"  # not from the smpte spec
        SPLIT = "SPLIT"
        GPI = "GPI"
        MASTER_SLAVE = "M/S"
        SWITCHER_MEMORY = "SWM"
        MOTION_MEMORY = "M2"
        MOTION_MEMORY_VARIABLE = "%"

        # OTIO identifiers
        FROM_CLIP_NAME = "FROM CLIP NAME"
        TO_CLIP_NAME = "TO CLIP NAME"
        FROM_CLIP = "FROM CLIP"
        FROM_FILE = "FROM FILE"
        SOURCE_FILE = "SOURCE FILE"
        LOC = "LOC"
        ASC_SOP = "ASC_SOP"
        ASC_SAT = "ASC_SAT"
        FREEZE_FRAME = "* FREEZE FRAME"
        OTIO_REFERENCE = "OTIO REFERENCE"

    statement_text: str = None
    is_comment: bool = True

    # extracts the identifier minus leading * and surrounding whitespace
    STATEMENT_RE = re.compile(
        r"^(?P<is_comment>\*)?\s*(?P<statement_value>.*(?<! ))"
    )

    @classmethod
    def identifiers(cls) -> list[str]:
        try:
            return cls._identifiers
        except AttributeError:
            pass

        # We do this from longest to shortest so that statements like
        # FROM CLIP NAME:
        # Aren't matched against the
        # FROM CLIP:
        # identifier.
        # In future we may want to get more explicit about calling out which
        # identifiers expect a : and which don't.
        cls._identifiers = sorted(
            (identifier.value for identifier in cls.NoteFormIdentifiers),
            reverse=True,
        )

        return cls._identifiers

    @cached_property
    def identifier(self) -> str:
        for identifier in self.identifiers():
            if self.statement_text.startswith(identifier):
                return identifier

        # Try to take a guess at the identifier based on well-known forms
        if ":" in self.statement_text:
            return self.statement_text.split(":", 1)[0]

        parts = self.statement_text.split(maxsplit=1)
        return parts[-1] if parts else ""

    @property
    def data(self) -> Optional[str]:
        after_identifier = self.statement_text.split(self.identifier, 1)[-1]
        return after_identifier.lstrip(":").strip()

    @property
    def statement_identifier(self) -> Optional[NoteFormIdentifiers]:
        try:
            return NoteFormStatement.NoteFormIdentifiers(self.identifier)
        except ValueError:
            return None

    @property
    def fcm_statement_is_drop_frame(self) -> bool:
        """
        If this is an FCM identifier, returns ``True`` if it specifies Drop-Frame
        and ``False`` if not.

        :raises ValueError: if this is not an FCM identifier or the drop/non-drop
        note is malformed.
        """
        if self.statement_identifier is not self.NoteFormIdentifiers.FCM:
            raise ValueError(
                f"{self.statement_text} on line {self.line_number} is not an FCM identifier."
            )

        upper_text = self.data.upper()
        if upper_text == "DROP FRAME":
            return True
        elif upper_text == "NON-DROP FRAME":
            return False
        else:
            raise ValueError(
                f"FCM identifier on line {self.line_number} "
                f"has invalid value: '{self.data}'"
            )

    @property
    def motion_directive(self) -> MotionDirective:
        if self.statement_identifier is not self.NoteFormIdentifiers.MOTION_MEMORY:
            raise ValueError(
                f"{self.statement_text} on line {self.line_number} is not an M2 identifier."
            )

        return MotionDirective.from_string(self.data)

    @property
    def otio_reference(self):
        if self.statement_identifier is not self.NoteFormIdentifiers.OTIO_REFERENCE:
            raise ValueError(
                f"{self.statement_text} on line {self.line_number} is not an OTIO_REFERENCE identifier."
            )

        return self.data


@dataclass
class StandardFormStatement(EDLStatement):

    source_identification: str = ""
    channels: str = "V"
    edit_type: str = "C"
    edit_parameter: Optional[str] = None
    source_entry: str = None
    source_exit: str = None
    sync_entry: str = None
    sync_exit: str = None
    disabled: bool = False

    @property
    def special_source(self) -> Optional[SpecialSource]:
        """
        If the source identifier is one of the special sources, returns that
        source. Otherwise, returns ``None``.
        """
        try:
            return SpecialSource(self.source_identification)
        except ValueError:
            return None

    @property
    def source_mode(self) -> SourceMode:
        """
        Returns the parsed SourceMode from the provided channels.
        raises ValueError if the source mode isn't a standard form.
        """
        return SourceMode(self.channels)

    @property
    def effect(self) -> Optional[Effect]:
        """The Effect parsed from the Edit Type"""
        try:
            return Effect.from_statement(self)
        except ValueError:
            return None
