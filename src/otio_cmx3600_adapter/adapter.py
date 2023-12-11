from otio_cmx3600_adapter import (
    cmx_3600_reader, cmx_3600_writer, exceptions
)
from otio_cmx3600_adapter.exceptions import EDLParseError


read_from_file = cmx_3600_reader.read_from_file
read_from_string = cmx_3600_reader.read_from_string
write_to_string = cmx_3600_writer.write_to_string


__all__ = [
    exceptions,
    EDLParseError,
    read_from_string,
    write_to_string,
]
