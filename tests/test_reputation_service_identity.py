import unittest
from tools.probe_reputation_service import matches_subject


class ReputationIdentityTests(unittest.TestCase):
    def test_verified_service_subject_matches_exact_character(self):
        self.assertTrue(matches_subject('urn:sc:global:player:geid:123456', '123456'))

    def test_other_character_and_namespace_are_rejected(self):
        for value in ('urn:sc:global:player:geid:123457',
                      'urn:sc:reputations:org:geid:123456',
                      'urn:sc:global:player:geid:1234567', '123456', '',
                      'prefix:urn:sc:global:player:geid:123456'):
            self.assertFalse(matches_subject(value, '123456'))
