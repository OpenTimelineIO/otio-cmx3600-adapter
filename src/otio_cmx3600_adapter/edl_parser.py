import re
from typing import Iterable, Iterator


from .edl_statement import (
    EDLStatement,
    EffectType,
    NoteFormStatement,
    StandardFormStatement,
)
from .exceptions import EDLParseError


# This set of regexes tries to follow the robustness principle - especially
# given the EDL landscape
SEPARATOR_RE_STRING = r"\s+"
SEPARATOR_RE = re.compile(SEPARATOR_RE_STRING)
EDIT_NUMBER_RE = re.compile(
    r"^(?P<edit_number_subfield>\d+[a-zA-Z]?)"
    r"(?P<virtual_edit_indicator>>)?(?P<recorded_indicator>>!)?"
    + SEPARATOR_RE_STRING
)  # This is built to handle SMPTE 258M EDIT_NUMBERs, CMX is more constrained.
COMMENT_RE = re.compile(
    r"^\*\s*(?P<data>.*)"
)

VALID_EFFECT_TYPES = {et.value for et in EffectType}


# These known identifier types are parsed into note form statements, all others
# are parsed into UnhandledStatements - they'll be treated like comments
HANDLED_DIRECTIVES = set(
    directive.value for directive in [
        NoteFormStatement.NoteFormIdentifiers.TITLE,
        NoteFormStatement.NoteFormIdentifiers.FCM,
        NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY,
        NoteFormStatement.NoteFormIdentifiers.SPLIT,
    ]
)


def statements_from_string(edl_string: str) -> Iterator[EDLStatement]:
    return statements_from_lines(edl_string.splitlines())


def _note_form_statement_from_line(
        line: str, **element_kwargs: dict
) -> NoteFormStatement:
    statement_match = NoteFormStatement.STATEMENT_RE.match(line)
    if statement_match is not None:
        return NoteFormStatement(
            statement_text=statement_match.group("statement_value"),
            is_comment=bool(statement_match.group("is_comment")),
            **element_kwargs,
        )
    return NoteFormStatement(
        statement_text=line,
        is_supported=False,
        **element_kwargs,
    )


def statements_from_lines(edl_lines: Iterable[str]) -> Iterator[EDLStatement]:
    edit_number = None
    is_virtual_edit = False
    is_recorded = False

    for line_number, line in enumerate(edl_lines, 1):
        # Drop any stray whitespace
        line = line.strip()

        # Ignore empty lines
        if not line:
            continue

        # copy the element line into a local we can whittle down as we process
        consuming_line = line

        # Parse the edit number, if possible
        edit_number_match = EDIT_NUMBER_RE.match(consuming_line)
        did_have_edit_number = False
        if edit_number_match:
            did_have_edit_number = True
            edit_number = edit_number_match.group("edit_number_subfield")
            is_virtual_edit = bool(
                edit_number_match.group("virtual_edit_indicator")
            )
            is_recorded = bool(edit_number_match.group("recorded_indicator"))

            # Consume the field
            consuming_line = consuming_line[edit_number_match.end():]

        element_context = dict(
            line_number=line_number,
            edit_number=edit_number,
            is_edit_number_inferred=not did_have_edit_number,
            is_recorded=is_recorded,
            is_virtual_edit=is_virtual_edit,
        )
        comment_match = COMMENT_RE.match(consuming_line)
        if not did_have_edit_number or comment_match is not None:
            yield _note_form_statement_from_line(
                consuming_line, **element_context
            )
            continue

        # split the remainder of the line on separators
        fields = list(
            field for field in SEPARATOR_RE.split(consuming_line) if field
        )
        if not did_have_edit_number:
            yield _note_form_statement_from_line(line, **element_context)
            continue

        if len(fields) < 6 or len(fields) > 8:
            raise EDLParseError(
                f"incorrect number of fields [{len(fields)}] in line number:"
                f" {line_number} statement: {line}"
            )

        # consume the fields from the head of the line
        consuming_fields = fields[:]
        source_identification = consuming_fields[0]
        channels = consuming_fields[1]
        edit_type = consuming_fields[2]
        for i in range(3):
            if i == 0:
                source_identification = consuming_fields.pop(0)
            elif i == 1:
                channels_candidate = consuming_fields[0]
                if channels_candidate in VALID_EFFECT_TYPES:
                    # This indicates the channel assignment has no whitespace
                    # delimiter between the reel name and it (this can happen in
                    # cases with maxing out fixed column width reel names
                    # Here we'll try to infer reel width based on fixed-width
                    # reel names.
                    if len(source_identification) > 32:
                        # File 32 EDL
                        reel_width = 32
                    elif len(source_identification) > 16:
                        # File 16 EDL
                        reel_width = 16
                    else:
                        # EDL Classic (TM)
                        reel_width = 8
                    # If the channel doesn't look valid, see if it might have
                    # mushed into the end of the reel
                    channels = source_identification[reel_width:]
                    source_identification = source_identification[:reel_width]
                else:
                    channels = channels_candidate
                    consuming_fields.pop(0)
            elif i == 2:
                edit_type = consuming_fields.pop(0)

        # Consume the record and source fields from the end of the line back
        rec_out = consuming_fields.pop()
        rec_in = consuming_fields.pop()
        src_out = consuming_fields.pop()
        src_in = consuming_fields.pop()

        # Parse as a standard form element
        standard_statement_fields = dict(
            source_identification=source_identification,
            channels=channels,
            edit_type=edit_type,
            source_entry=src_in,
            source_exit=src_out,
            sync_entry=rec_in,
            sync_exit=rec_out,
            is_supported=True,
        )

        # If the edit parameter was present, add it
        if consuming_fields:
            standard_statement_fields["edit_parameter"] = consuming_fields.pop()

        standard_statement_fields.update(element_context)
        yield StandardFormStatement(**standard_statement_fields)
        continue