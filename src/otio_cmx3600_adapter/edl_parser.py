import re
from typing import Iterable, Iterator


from .edl_statement import (
    EDLStatement,
    NoteFormStatement,
    StandardFormStatement,
)


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
        if not did_have_edit_number or len(fields) < 7 or len(fields) > 8:
            yield _note_form_statement_from_line(line, **element_context)
            continue

        # Parse as a standard form element
        standard_statement_fields = dict(
            source_identification=fields[0],
            channels=fields[1],
            edit_type=fields[2],
            source_entry=fields[-4],
            source_exit=fields[-3],
            sync_entry=fields[-2],
            sync_exit=fields[-1],
            is_supported=True,
        )

        if len(fields) == 8:
            standard_statement_fields["edit_parameter"] = fields[3]

        standard_statement_fields.update(element_context)
        yield StandardFormStatement(**standard_statement_fields)
        continue
