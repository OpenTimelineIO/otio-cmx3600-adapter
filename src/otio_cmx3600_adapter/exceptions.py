from opentimelineio import exceptions

from typing import Optional


class EDLParseError(exceptions.OTIOError):
    line_number: Optional[int] = None
    event_number: Optional[str] = None

    def __init__(self, message, line_number=None, event_number=None):
        super().__init__(message)
        self.line_number = line_number
        self.event_number = event_number
