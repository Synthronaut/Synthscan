"""Packet framing, integrity and latency association; no game access required."""
import struct
import unittest

from network_protocol import ControlPacket, PingTracker, crc32c, decode_control, decode_envelope
from tools.analyze_game_network import Frame, frames, udp


class ProtocolTests(unittest.TestCase):
    def test_crc32c_standard_check_vector(self):
        self.assertEqual(crc32c(b'123456789'), 0xe3069283)

    def test_real_control_pair_with_anonymized_connection(self):
        ping = decode_control(bytes.fromhex('5c0304000102030440bbb53d11000000de5ba6bf'))
        pong = decode_control(bytes.fromhex('5c040400010203044dbbb53d11000000cfe49fb9f6ac3f00f0cf8e85'))
        self.assertEqual(ping.kind, 3)
        self.assertEqual(pong.kind, 4)
        self.assertEqual(pong.ping_ticks-ping.ping_ticks, 13)
        tracker = PingTracker()
        tracker.feed(ping, 'out', 100, 'flow')
        sample = tracker.feed(pong, 'in', 100.022465, 'flow')
        self.assertAlmostEqual(sample['rtt_ms'], 22.4637, places=4)
        self.assertIsNone(tracker.feed(pong, 'in', 100.022466, 'flow'))

    def test_damaged_and_encrypted_packets_are_rejected(self):
        raw = bytearray.fromhex('5c0304000102030440bbb53d11000000de5ba6bf')
        raw[8] ^= 1
        self.assertIsNone(decode_control(raw))
        raw[2] = 2
        self.assertIsNone(decode_control(raw))
        self.assertIsNone(decode_control(raw[:7]))

    def test_encrypted_envelope_is_framed_without_claiming_decryption(self):
        ciphertext, nonce, tag = b'opaque-data', bytes(range(8)), bytes(range(16))
        raw = bytes.fromhex('5c07030001020304')+ciphertext+nonce+tag
        envelope = decode_envelope(raw)
        self.assertTrue(envelope.compressed)
        self.assertEqual(envelope.ciphertext, ciphertext)
        self.assertEqual(envelope.nonce_suffix, nonce)
        self.assertEqual(envelope.authentication_tag, tag)
        self.assertEqual(envelope.aad, bytes.fromhex('5c07030000000000'))
        self.assertIsNone(decode_control(raw))

    def test_other_flow_and_connection_cannot_supply_a_sample(self):
        tracker = PingTracker()
        tracker.feed(ControlPacket(3, 10, 1000, None), 'out', 100, 'a')
        self.assertIsNone(tracker.feed(ControlPacket(4, 10, 1005, 50), 'in', 100.02, 'b'))
        self.assertIsNone(tracker.feed(ControlPacket(4, 11, 1005, 50), 'in', 100.02, 'a'))

    def test_duplicate_capture_does_not_inflate_sample_count(self):
        tracker = PingTracker()
        ping, pong = ControlPacket(3, 1, 1000, None), ControlPacket(4, 1, 1010, 42)
        tracker.feed(ping, 'out', 100, 'a')
        tracker.feed(ping, 'out', 100.0005, 'a')
        sample = tracker.feed(pong, 'in', 100.025, 'a')
        self.assertEqual(sample['average_samples'], 1)
        self.assertAlmostEqual(sample['rtt_ms'], 24.999)
        self.assertIsNone(tracker.feed(pong, 'in', 100.0251, 'a'))

    def test_ambiguous_negative_and_delayed_samples_are_rejected(self):
        tracker = PingTracker()
        tracker.feed(ControlPacket(3, 1, 1000, None), 'out', 100, 'a')
        tracker.feed(ControlPacket(3, 1, 1005, None), 'out', 100.001, 'a')
        self.assertIsNone(tracker.feed(ControlPacket(4, 1, 1010, 42), 'in', 100.025, 'a'))
        self.assertIsNone(tracker.feed(ControlPacket(4, 1, 999, 42), 'in', 100.025, 'a'))
        self.assertIsNone(tracker.feed(ControlPacket(4, 1, 1000, 42), 'in', 105, 'a'))

    def test_game_clock_prevents_queued_outbound_packet_from_faking_low_rtt(self):
        tracker = PingTracker(calibrate_clock=True)
        tracker.feed(ControlPacket(3, 1, 10_000_000, None), 'out', 101, 'a')
        tracker.feed(ControlPacket(3, 1, 20_000_000, None), 'out', 102, 'a')
        # Third ping took 20 ms to reach the listener, then pong is dequeued
        # 1 ms later. Naive receive-time subtraction would report 1 ms.
        tracker.feed(ControlPacket(3, 1, 30_000_000, None), 'out', 103.020, 'a')
        sample = tracker.feed(ControlPacket(4, 1, 30_000_000, 42), 'in', 103.021, 'a')
        self.assertAlmostEqual(sample['rtt_ms'], 21, places=3)
        self.assertAlmostEqual(sample['capture_send_delay_ms'], 20, places=3)
        self.assertEqual(sample['timing_method'], 'game_clock_calibrated')


class CaptureFormatTests(unittest.TestCase):
    def packet(self):
        payload = b'game-control'
        transport = struct.pack('!HHHH', 1234, 5678, 8+len(payload), 0)+payload
        ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20+len(transport), 1, 0, 64, 17, 0,
                         bytes([192, 0, 2, 1]), bytes([192, 0, 2, 2]))
        return ip+transport

    def test_ipv4_udp_and_fragment_rejection(self):
        raw = self.packet()
        packet = udp(Frame(100, 101, raw))
        self.assertEqual(packet['payload'], b'game-control')
        self.assertEqual(packet['sport'], 1234)
        fragment = bytearray(raw)
        fragment[6] = 0x20
        self.assertIsNone(udp(Frame(100, 101, fragment)))
        self.assertIsNone(udp(Frame(100, 101, raw[:-1])))

    def test_classic_pcap(self):
        raw = self.packet()
        capture = struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 101)
        capture += struct.pack('<IIII', 100, 500000, len(raw), len(raw))+raw
        frame, = frames(capture)
        self.assertEqual(frame.timestamp, 100.5)
        self.assertEqual(udp(frame)['payload'], b'game-control')

    def test_pcapng_resolution_and_bad_trailer(self):
        def block(kind, body):
            body += b'\0'*(-len(body) % 4)
            length = 12+len(body)
            return struct.pack('<II', kind, length)+body+struct.pack('<I', length)
        capture = block(0x0a0d0d0a, struct.pack('<IHHq', 0x1a2b3c4d, 1, 0, -1))
        capture += block(1, struct.pack('<HHIHHB3xHH', 101, 0, 65535, 9, 1, 9, 0, 0))
        raw = self.packet()
        capture += block(6, struct.pack('<IIIII', 0, 0, 100_500_000, len(raw), len(raw))+raw)
        frame, = frames(capture)
        self.assertAlmostEqual(frame.timestamp, .1005)
        self.assertEqual(udp(frame)['payload'], b'game-control')
        with self.assertRaises(ValueError):
            list(frames(capture[:-1]+b'\xff'))


if __name__ == '__main__':
    unittest.main()
