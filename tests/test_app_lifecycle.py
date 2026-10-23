"""Verify launch behaviour and Windows instance signalling without touching the game."""
import os
import unittest
import uuid

from app_lifecycle import LaunchPolicy, Signal, SingleInstance, instance_running, send_signal


class LaunchPolicyTests(unittest.TestCase):
    def test_launches_for_already_running_game_then_respects_manual_exit(self):
        policy = LaunchPolicy()
        self.assertTrue(policy.needs_launch({10}, False))
        policy.mark_launched()
        self.assertFalse(policy.needs_launch({10}, True))
        self.assertFalse(policy.needs_launch({10}, False))
        self.assertFalse(policy.needs_launch(set(), False))
        self.assertTrue(policy.needs_launch({20}, False))

    def test_existing_app_is_reused_and_game_exit_does_not_close_it(self):
        policy = LaunchPolicy()
        self.assertFalse(policy.needs_launch({10}, True))
        self.assertFalse(policy.needs_launch({10}, False))
        self.assertFalse(policy.needs_launch(set(), True))
        self.assertFalse(policy.needs_launch({20}, True))

    def test_no_launch_without_game_and_failed_spawn_can_retry(self):
        policy = LaunchPolicy()
        self.assertFalse(policy.needs_launch(set(), False))
        self.assertTrue(policy.needs_launch({10}, False))
        self.assertTrue(policy.needs_launch({10}, False))


@unittest.skipUnless(os.name == "nt", "Windows named kernel objects")
class WindowsLifecycleTests(unittest.TestCase):
    def test_single_instance_and_release(self):
        name = "test-" + uuid.uuid4().hex
        first = SingleInstance(name)
        try:
            second = SingleInstance(name)
            self.assertTrue(first.acquired)
            self.assertFalse(second.acquired)
            self.assertTrue(instance_running(name))
        finally:
            first.close()
        self.assertFalse(instance_running(name))

    def test_show_signal_is_delivered_once(self):
        name = "test-" + uuid.uuid4().hex
        event = Signal(name)
        try:
            self.assertFalse(event.wait())
            self.assertTrue(send_signal(name))
            self.assertTrue(event.wait())
            self.assertFalse(event.wait())
        finally:
            event.close()
        self.assertFalse(send_signal(name))
