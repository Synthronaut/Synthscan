"""Read embedded telemetry protobuf descriptors from the on-disk client only.

Does not open the game process, connect to a service, or execute extracted data.
Requires the protobuf package already available in this development environment.
"""
import argparse
import json
from pathlib import Path
import re

from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.message import DecodeError

from installation import game_directory
DEFAULT_EXE = str(game_directory()/'Bin64/StarCitizen.exe')


def find_descriptor(data, name):
    for descriptor, offset in iter_descriptors(data, name):
        return descriptor, offset
    return None, None


def _varint(data, offset, limit):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= limit:
            raise ValueError("Truncated varint")
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("Varint exceeds uint64")
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("Unterminated varint")


def iter_descriptors(data, name=None):
    """Find bounded serialized descriptors, including proto2 without a syntax tag.

    Searching for a trailing ``proto3`` marker misses legacy services entirely.
    Read top-level protobuf field lengths instead; extracted bytes are only parsed
    as data, never imported or executed. Duplicate copies are reported once.
    """
    pattern = rb"\x0a(?:[\x01-\x7f]|[\x80-\xff][\x01-\x7f])([A-Za-z0-9_/.-]{3,200}\.proto)"
    singletons = {1, 2, 8, 9, 12, 14}
    known_fields = set(range(1, 13)) | {14}
    seen_names = set()
    for occurrence in re.finditer(pattern, data):
        filename = occurrence.group(1)
        if name is not None and filename != name:
            continue
        if filename in seen_names:
            continue
        start = occurrence.start()
        limit = min(len(data), start + 400000)
        size, end = _varint(data, start + 1, limit)
        if size != len(filename) or end != occurrence.start(1):
            continue
        offset = last = start
        seen_fields = set()
        while offset < limit:
            try:
                key, after = _varint(data, offset, limit)
                field, wire = key >> 3, key & 7
                if field not in known_fields or (field in singletons and field in seen_fields):
                    break
                seen_fields.add(field)
                if wire == 2 and field != 14:
                    size, after = _varint(data, after, limit)
                    offset = after + size
                elif wire == 0 and field in {10, 11, 14}:
                    _, offset = _varint(data, after, limit)
                else:
                    break
                if offset > limit:
                    break
                last = offset
            except ValueError:
                break
        try:
            descriptor = FileDescriptorProto.FromString(data[start:last])
        except DecodeError:
            continue
        if descriptor.name.encode() != filename:
            continue
        seen_names.add(filename)
        yield descriptor, start


def enum_summary(enum):
    return {"name": enum.name, "values": [{"name": value.name, "number": value.number} for value in enum.value]}


def message_summary(message):
    return {"name": message.name,
            "fields": [{"name": field.name, "type": field.type_name or field.type,
                        "number": field.number, "repeated": field.label == field.LABEL_REPEATED} for field in message.field],
            "nested_messages": [message_summary(child) for child in message.nested_type],
            "enums": [enum_summary(enum) for enum in message.enum_type]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=DEFAULT_EXE)
    parser.add_argument("--output", help="Optional JSON metadata output; no game assets are executed")
    parser.add_argument("--all", action="store_true", help="Inventory every embedded protobuf service, including proto2")
    options = parser.parse_args()
    data = Path(options.exe).read_bytes()
    files = []
    descriptors = iter_descriptors(data) if options.all else (
        find_descriptor(data, name) for name in
        (b"sc/game/telemetry/v1/api.proto", b"sc/game/telemetry/v1/types.proto"))
    for descriptor, offset in descriptors:
        if descriptor is None:
            continue
        files.append({"name": descriptor.name, "package": descriptor.package, "offset": hex(offset),
                      "syntax": descriptor.syntax or "proto2",
                      "messages": [message_summary(message) for message in descriptor.message_type],
                      "enums": [enum_summary(enum) for enum in descriptor.enum_type],
                      "services": [{"name": service.name, "methods": [
                          {"name": method.name, "input": method.input_type, "output": method.output_type,
                           "server_streaming": method.server_streaming} for method in service.method]}
                          for service in descriptor.service]})
    result = {"provenance": "Read-only embedded descriptor inspection. Runtime service availability is not established.", "files": files}
    if options.output:
        destination = Path(options.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"descriptors": len(files) if options.all else [item["name"] for item in files],
                      "message_count": sum(len(item["messages"]) for item in files), "output": options.output}, indent=2))


if __name__ == "__main__":
    main()
