"""Offline, dependency-free PCAP/PCAPNG UDP analysis for the current game flow.

Does not send packets, access process memory, or turn packet cadence into FPS.
Reports framing hypotheses separately from verified game telemetry. Packet bodies
are not copied into the JSON report. Raw captures stay in the local research dir.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import ipaddress
import json
import math
import os
from pathlib import Path
import statistics
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from network_protocol import PingTracker, decode_control, decode_envelope


@dataclass
class Frame:
    timestamp: float
    linktype: int
    data: bytes
    interface: int = 0


def frames(data):
    """Read common classic PCAP and PCAPNG with per-interface time resolution."""
    magics = {b"\xd4\xc3\xb2\xa1": ("<", 1e6), b"\xa1\xb2\xc3\xd4": (">", 1e6),
              b"\x4d\x3c\xb2\xa1": ("<", 1e9), b"\xa1\xb2\x3c\x4d": (">", 1e9)}
    if data[:4] in magics:
        endian, scale = magics[data[:4]]
        if len(data) < 24:
            raise ValueError("Truncated PCAP header")
        linktype = struct.unpack_from(endian + "I", data, 20)[0] & 0xffff
        offset = 24
        while offset < len(data):
            if offset + 16 > len(data):
                raise ValueError("Truncated PCAP record")
            seconds, fraction, captured, original = struct.unpack_from(endian + "IIII", data, offset)
            offset += 16
            if captured > original or offset + captured > len(data):
                raise ValueError("Invalid PCAP packet length")
            yield Frame(seconds + fraction / scale, linktype, data[offset:offset+captured])
            offset += captured
        return
    offset, endian, interfaces = 0, None, []
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PCAPNG block")
        if data[offset:offset+4] == b"\x0a\x0d\x0d\x0a":
            magic = data[offset+8:offset+12]
            endian = {b"\x4d\x3c\x2b\x1a": "<", b"\x1a\x2b\x3c\x4d": ">"}.get(magic)
            if endian is None:
                raise ValueError("Invalid PCAPNG byte order")
            interfaces = []
        if endian is None:
            raise ValueError("PCAPNG must start with a section header")
        kind, length = struct.unpack_from(endian + "II", data, offset)
        if length < 12 or length % 4 or offset + length > len(data):
            raise ValueError("Invalid PCAPNG block length")
        if struct.unpack_from(endian + "I", data, offset+length-4)[0] != length:
            raise ValueError("Mismatched PCAPNG block trailer")
        body = data[offset+8:offset+length-4]
        if kind == 0x0a0d0d0a and len(body) < 16:
            raise ValueError("Truncated PCAPNG section header")
        if kind == 1:
            if len(body) < 8:
                raise ValueError("Truncated interface header")
            linktype, _, snaplen = struct.unpack_from(endian + "HHI", body)
            scale, time_offset, pos = 1e6, 0, 8
            while pos + 4 <= len(body):
                code, size = struct.unpack_from(endian + "HH", body, pos)
                pos += 4
                if pos + size > len(body):
                    raise ValueError("Truncated interface option")
                value = body[pos:pos+size]
                if code == 0:
                    break
                if code == 9 and size == 1:
                    resolution = value[0]
                    scale = (2 if resolution & 128 else 10) ** (resolution & 127)
                if code == 14 and size == 8:
                    time_offset = struct.unpack(endian + "q", value)[0]
                pos += (size + 3) & ~3
            interfaces.append((linktype, scale, time_offset))
        elif kind == 6:
            if len(body) < 20:
                raise ValueError("Truncated enhanced packet")
            interface, high, low, captured, original = struct.unpack_from(endian + "IIIII", body)
            if interface >= len(interfaces) or captured > original or 20+captured > len(body):
                raise ValueError("Invalid enhanced packet")
            linktype, scale, time_offset = interfaces[interface]
            yield Frame(((high << 32) | low) / scale + time_offset,
                        linktype, body[20:20+captured], interface)
        offset += length


def udp(frame):
    """Decode framing only; reject fragmented/truncated IP or UDP datagrams."""
    data, offset = frame.data, 0
    if frame.linktype == 1:
        if len(data) < 14:
            return None
        ethertype = struct.unpack_from("!H", data, 12)[0]
        offset = 14
        while ethertype in (0x8100, 0x88a8):
            if offset + 4 > len(data):
                return None
            ethertype = struct.unpack_from("!H", data, offset+2)[0]
            offset += 4
        if ethertype not in (0x0800, 0x86dd):
            return None
    elif frame.linktype not in (101, 228, 229):
        return None
    if offset >= len(data):
        return None
    version = data[offset] >> 4
    if version == 4:
        if offset + 20 > len(data):
            return None
        header = (data[offset] & 15) * 4
        length = struct.unpack_from("!H", data, offset+2)[0]
        flags = struct.unpack_from("!H", data, offset+6)[0]
        if header < 20 or length < header+8 or offset+length > len(data) or flags & 0x3fff:
            return None
        protocol = data[offset+9]
        source = str(ipaddress.ip_address(data[offset+12:offset+16]))
        destination = str(ipaddress.ip_address(data[offset+16:offset+20]))
        end, offset = offset+length, offset+header
    elif version == 6:
        if offset+40 > len(data):
            return None
        length = struct.unpack_from("!H", data, offset+4)[0]
        protocol = data[offset+6]
        source = str(ipaddress.ip_address(data[offset+8:offset+24]))
        destination = str(ipaddress.ip_address(data[offset+24:offset+40]))
        end, offset = offset+40+length, offset+40
        if end > len(data):
            return None
        for _ in range(8):
            if protocol not in (0, 43, 60):
                break
            if offset+2 > end:
                return None
            following, size = data[offset], (data[offset+1]+1)*8
            offset += size
            protocol = following
    else:
        return None
    if protocol != 17 or offset+8 > end:
        return None
    sport, dport, length, _ = struct.unpack_from("!HHHH", data, offset)
    if length < 8 or offset+length > end:
        return None
    return {"time": frame.timestamp, "interface": frame.interface,
            "source": source, "destination": destination, "sport": sport, "dport": dport,
            "payload": data[offset+8:offset+length]}


def entropy(values):
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((count/total)*math.log2(count/total) for count in counts.values()) if total else 0


def describe(packets):
    packets = sorted(packets, key=lambda p: p["time"])
    payloads = [p["payload"] for p in packets]
    times = [p["time"] for p in packets]
    gaps = [(right-left)*1000 for left, right in zip(times, times[1:])]
    counters = []
    for width in (2, 4):
        for offset in range(32):
            raw = [p[offset:offset+width] for p in payloads if len(p) >= offset+width]
            if len(raw) < 20:
                continue
            for order in ("little", "big"):
                values = [int.from_bytes(value, order) for value in raw]
                deltas = [(b-a) % (1 << (8*width)) for a, b in zip(values, values[1:])]
                small = sum(0 < d < 4096 for d in deltas) / len(deltas)
                if small >= .9:
                    counters.append({"offset": offset, "width": width, "byteorder": order,
                                     "small_positive_delta_fraction": round(small, 4),
                                     "median_modular_delta": statistics.median(deltas),
                                     "status": "unverified counter hypothesis, not a telemetry field"})
    return {"packets": len(packets), "duration_seconds": times[-1]-times[0] if times else 0,
            "payload_bytes": sum(map(len, payloads)), "interfaces": dict(Counter(p['interface'] for p in packets)),
            "payload_lengths": Counter(map(len, payloads)).most_common(12),
            "first_byte_counts": {hex(k): v for k, v in Counter(p[0] for p in payloads if p).most_common(16)},
            "offset_entropy_bits": [{"offset": i, "entropy": round(entropy(p[i] for p in payloads if len(p)>i), 3)}
                                    for i in range(48)],
            "interarrival_ms": {"median": statistics.median(gaps), "maximum": max(gaps)} if gaps else None,
            "counter_hypotheses": counters}


def analyze(path, server_address, server_port):
    flows, total, decoded = defaultdict(list), 0, 0
    tracker, samples, control_count, encrypted_count = PingTracker(), [], 0, 0
    for frame in frames(Path(path).read_bytes()):
        total += 1
        packet = udp(frame)
        if not packet:
            continue
        decoded += 1
        if packet['source'] == server_address and packet['sport'] == server_port:
            direction = 'server_to_client'
        elif packet['destination'] == server_address and packet['dport'] == server_port:
            direction = 'client_to_server'
        else:
            continue
        flows[direction].append(packet)
        control = decode_control(packet['payload'])
        if control:
            control_count += 1
            local_address = packet['destination'] if direction == 'server_to_client' else packet['source']
            local_port = packet['dport'] if direction == 'server_to_client' else packet['sport']
            sample = tracker.feed(control, 'in' if direction == 'server_to_client' else 'out',
                                  packet['time'], (server_address, server_port, local_address, local_port))
            if sample:
                samples.append(sample)
        if decode_envelope(packet['payload']):
            encrypted_count += 1
    return {"capture_frames": total, "decoded_udp_frames": decoded,
            "flows": {direction: describe(packets) for direction, packets in flows.items()},
            "crc_valid_control_packets": control_count, "framed_encrypted_packets": encrypted_count,
            "decoded_network_rtt_samples": samples,
            "limitations": ["Interarrival time is not server FPS or round-trip time.",
                            "Entropy and counter candidates do not establish encryption or field semantics.",
                            "RTT comes from game ping/pong; capture timestamps differ from game delivery timestamps.",
                            "No encrypted payload decryption, server FPS, or population has been validated."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(Path(os.environ.get('LOCALAPPDATA', '.')) /
                                                'SynthScan/network-research/latest.json'))
    parser.add_argument("--output", default="research/network_capture_summary.json")
    options = parser.parse_args()
    manifest = json.loads(Path(options.manifest).read_text(encoding="utf-8-sig"))
    report = analyze(manifest['pcapng'], manifest['server_address'], manifest['server_port'])
    Path(options.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"capture_frames": report['capture_frames'],
                      "flows": {key: {field: value[field] for field in ('packets', 'duration_seconds', 'payload_bytes', 'counter_hypotheses')}
                                for key, value in report['flows'].items()}, "output": options.output}))


if __name__ == '__main__':
    main()
