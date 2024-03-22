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
    r"(?P<virtual_edit_indicator>>)?(?P<recorded_indicator>>!)?" + SEPARATOR_RE_STRING
)  # This is built to handle SMPTE 258M EDIT_NUMBERs, CMX is more constrained.
CHANNEL_NAME_RE = re.compile(r"A\d*\\/V|A\d*|AA|AA\\/V|A|B|V")
COMMENT_RE = re.compile(r"^\*\s*(?P<data>.*)")
WIPE_RE = re.compile(r"W\d{3}")

VALID_EFFECT_TYPES = {et.value for et in EffectType}


# These known identifier types are parsed into note form statements, all others
# are parsed into UnhandledStatements - they'll be treated like comments
HANDLED_DIRECTIVES = set(
    directive.value
    for directive in [
        NoteFormStatement.NoteFormIdentifiers.TITLE,
        NoteFormStatement.NoteFormIdentifiers.FCM,
        NoteFormStatement.NoteFormIdentifiers.MOTION_MEMORY,
        NoteFormStatement.NoteFormIdentifiers.SPLIT,
    ]
)


def _is_effect_type(field: str) -> bool:
    return field in VALID_EFFECT_TYPES or WIPE_RE.fullmatch(field) is not None


def statements_from_string(
    edl_string: str, allow_best_effort_parsing: bool = False
) -> Iterator[EDLStatement]:
    return statements_from_lines(edl_string.splitlines(), allow_best_effort_parsing)


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


def statements_from_lines(
    edl_lines: Iterable[str], allow_best_effort_parsing: bool = False
) -> Iterator[EDLStatement]:
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
            is_virtual_edit = bool(edit_number_match.group("virtual_edit_indicator"))
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
            # Skip empty comments
            if comment_match and not comment_match.group("data"):
                continue
            yield _note_form_statement_from_line(consuming_line, **element_context)
            continue

        # split the remainder of the line on separators
        fields = list(field for field in SEPARATOR_RE.split(consuming_line) if field)
        if not did_have_edit_number:
            yield _note_form_statement_from_line(line, **element_context)
            continue

        if len(fields) < 3:
            raise EDLParseError(
                f"incorrect number of fields [{len(fields)}] in line number:"
                f" {line_number} statement: {line}",
                line_number=line_number,
                event_number=edit_number,
            )

        # TODO: Rather than splitting on spaces, we may want to just consume
        #   chunks off the end of the line. That way the reel name isn't re-joining
        #   and potentially discarding spaces.

        # Start consuming the fields from the tail backwards - this lets us
        # work backward until only the reel name (which is of varying format) is
        # leftover
        consuming_fields = fields[:]

        # Consume the record and source fields from the end of the line back
        rec_out = consuming_fields.pop()
        rec_in = consuming_fields.pop()
        src_out = consuming_fields.pop()
        src_in = consuming_fields.pop()

        # The end field is either an edit parameter or the edit type
        edit_parameter_or_type = consuming_fields.pop()
        edit_parameter = None
        if _is_effect_type(edit_parameter_or_type):
            edit_type = edit_parameter_or_type
        else:
            edit_parameter = edit_parameter_or_type
            edit_type = consuming_fields.pop()

        channels = consuming_fields.pop()

        # TODO: This technically could need to be multiple spaces
        source_identification = " ".join(consuming_fields)

        # Parse as a standard form element
        standard_statement_fields = dict(
            source_identification=source_identification,
            channels=channels,
            edit_type=edit_type,
            edit_parameter=edit_parameter,
            source_entry=src_in,
            source_exit=src_out,
            sync_entry=rec_in,
            sync_exit=rec_out,
            is_supported=True,
        )

        standard_statement_fields.update(element_context)
        yield StandardFormStatement(**standard_statement_fields)
        continue
