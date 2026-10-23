"""Passive Star Citizen control-packet decoder, verified against build 12913470.

Only clear, CRC32C-protected ping/pong packets are decoded. Encrypted gameplay
payloads are deliberately left opaque. No packet is transmitted by this module.
"""
from collections import deque
from dataclasses import dataclass
import math
import struct


def _crc_table():
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0x82f63b78 if value & 1 else 0)
        table.append(value)
    return tuple(table)


CRC_TABLE = _crc_table()


def crc32c(data):
    value = 0xffffffff
    for byte in data:
        value = CRC_TABLE[(value ^ byte) & 255] ^ (value >> 8)
    return value ^ 0xffffffff


@dataclass(frozen=True)
class ControlPacket:
    kind: int
    connection: int
    ping_ticks: int
    pong_ticks: int | None


@dataclass(frozen=True)
class EncryptedEnvelope:
    kind: int
    compressed: bool
    connection: int
    aad: bytes
    ciphertext: bytes
    nonce_suffix: bytes
    authentication_tag: bytes


def decode_envelope(data):
    """Split the AES-GCM envelope. This does not decrypt or authenticate it.

    The nonce also needs a channel-specific four-byte prefix, not supplied by
    this function. A correct key/prefix must pass the 16-byte GCM tag check.
    """
    if len(data) < 33 or data[0] != 0x5c or data[3] != 0 or not data[2] & 2:
        return None
    if data[2] & ~3 or data[1] not in (7, 8):
        return None
    aad = data[:2] + bytes([data[2] & 7, 0]) + b'\0'*4
    return EncryptedEnvelope(data[1], bool(data[2] & 1), int.from_bytes(data[4:8], 'little'),
                             aad, data[8:-24], data[-24:-16], data[-16:])


def decode_control(data):
    if len(data) not in (20, 28) or data[0] != 0x5c or data[3] != 0:
        return None
    kind, flags = data[1], data[2]
    if flags != 4 or (kind, len(data)) not in ((3, 20), (4, 28)):
        return None
    # The client zeroes connection bytes for integrity calculation, and keeps
    # only the three protocol flag bits in the authenticated header.
    normalized = data[:2] + bytes([flags & 7, 0]) + b"\0" * 4 + data[8:-4]
    if crc32c(normalized) != int.from_bytes(data[-4:], "little"):
        return None
    connection = int.from_bytes(data[4:8], "little")
    ping = struct.unpack_from("<Q", data, 8)[0]
    pong = struct.unpack_from("<Q", data, 16)[0] if kind == 4 else None
    return ControlPacket(kind, connection, ping, pong)


class PingTracker:
    """Match requests/replies on the same endpoint and connection.

    Packet capture timestamps measure network RTT. The responder adjusts the
    echoed ping timestamp by time spent handling the request; that adjustment
    is subtracted. This can differ from the game's displayed 16-sample average
    because capture and application receive timestamps are different.
    """
    def __init__(self, calibrate_clock=False):
        self.requests = deque(maxlen=128)
        self.samples = deque(maxlen=16)
        self.used = deque(maxlen=128)
        self.calibrate_clock = calibrate_clock
        self.clock_offsets = deque(maxlen=120)

    def feed(self, packet, direction, observed_at, flow):
        if not math.isfinite(observed_at):
            return None
        if direction == "out" and packet.kind == 3:
            key = (flow, packet.connection, packet.ping_ticks)
            if not any(item[0] == key for item in self.requests):
                if self.calibrate_clock:
                    self.clock_offsets.append(observed_at - packet.ping_ticks / 10_000_000)
                self.requests.append((key, observed_at))
            return None
        if direction != "in" or packet.kind != 4:
            return None
        reply_key = (flow, packet.connection, packet.ping_ticks, packet.pong_ticks)
        if reply_key in self.used:
            return None
        matches = []
        for key, sent_at in self.requests:
            if key[:2] != (flow, packet.connection):
                continue
            adjustment = packet.ping_ticks - key[2]
            elapsed = observed_at - sent_at
            # Reject ambiguous long responder delays rather than matching a
            # reply to the next one-second ping or guessing across clock jumps.
            if 0 <= adjustment <= 2_500_000 and 0 <= elapsed <= 3:
                rtt = elapsed * 1000 - adjustment / 10000
                if 0 <= rtt <= 3000:
                    matches.append((rtt, adjustment, key))
        if len(matches) != 1:
            return None
        rtt, adjustment, request_key = matches[0]
        capture_delay = 0.0
        if self.calibrate_clock:
            if len(self.clock_offsets) < 3:
                return None
            sent_at = next(at for key, at in self.requests if key == request_key)
            mapped_send = request_key[2] / 10_000_000 + min(self.clock_offsets)
            capture_delay = max(0.0, (sent_at - mapped_send) * 1000)
            # Do not report an artificially tiny RTT when an outgoing packet
            # sat in the listener queue. Its game-clock send time is retained.
            rtt += capture_delay
            if not 0 <= rtt <= 3000:
                return None
        self.used.append(reply_key)
        self.requests = deque((item for item in self.requests if item[0] != request_key), maxlen=128)
        self.samples.append(rtt)
        return {"rtt_ms": rtt, "average_ms": sum(self.samples)/len(self.samples),
                "average_samples": len(self.samples), "observed_at": observed_at,
                "responder_adjustment_ms": adjustment / 10000,
                "capture_send_delay_ms": capture_delay,
                "timing_method": "game_clock_calibrated" if self.calibrate_clock else "capture_timestamps",
                "source": "game_udp_ping_pong"}
