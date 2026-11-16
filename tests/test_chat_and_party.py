"""Unit tests for chat_codec, party management, and live chat backend."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import chat_codec
from companion_features import CompanionService
from player_services import PlayerClient, PLAYER_PREFIX


CONTEXT = dict(session_token='join', full_shard_id='pub_ape1a_13165946_060', joined_at=100)
ME = dict(id=PLAYER_PREFIX + '1', handle='Synthronaut')
PERSON = dict(id=PLAYER_PREFIX + '2', handle='DemoZebra')
OTHER = dict(id=PLAYER_PREFIX + '3', handle='OtherPilot')


class ImmediatePool:
    def submit(self, function, *args, **kwargs):
        from concurrent.futures import Future
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as error:
            future.set_exception(error)
        return future
    def shutdown(self, **kwargs):
        pass


class ChatCodecTests(unittest.TestCase):
    def test_decode_plain_english(self):
        res = chat_codec.decode_sc_chat("Hello verse, anyone selling Quantanium?")
        self.assertFalse(res['was_zh_encoded'])
        self.assertFalse(res['was_mojibake'])
        self.assertEqual(res['decoded'], "Hello verse, anyone selling Quantanium?")

    def test_encode_and_decode_zh_roundtrip(self):
        text = "你好，有人出纯卡R4吗？"
        encoded = chat_codec.encode_sc_zh_chat(text)
        self.assertTrue(encoded.startswith("[zh] "))
        self.assertIn("@IH@E8", encoded)
        decoded_info = chat_codec.decode_sc_chat(encoded)
        self.assertTrue(decoded_info['was_zh_encoded'])
        self.assertEqual(decoded_info['decoded'], text)

    def test_translator_cache_and_mock(self):
        with tempfile.TemporaryDirectory() as td:
            cache_file = Path(td) / "tr_cache.json"
            tr = chat_codec.ChatTranslator(cache_file)
            tr._cache["auto:en:你好"] = ("Hello", "zh-CN")
            translated, src = tr.translate("你好")
            self.assertEqual(translated, "Hello")
            self.assertEqual(src, "zh-CN")

            # Outgoing encode test with cached translation
            tr._cache["auto:zh-CN:Hello"] = ("你好", "en")
            bundle = tr.translate_and_encode_zh("Hello")
            self.assertEqual(bundle['zh_text'], "你好")
            self.assertTrue(bundle['encoded'].startswith("[zh] "))


class PartyManagementTests(unittest.TestCase):
    def client(self, is_leader=True):
        c = object.__new__(PlayerClient)
        c.account = SimpleNamespace(subject=ME['id'])
        c.scope = Mock()
        def make_msg(domain, name):
            ns = SimpleNamespace()
            ns.filters = SimpleNamespace(types=[])
            ns.pagination = SimpleNamespace(first=0, after='')
            return lambda: ns
        c.message = Mock(side_effect=make_msg)

        members = [SimpleNamespace(urn=ME['id']), SimpleNamespace(urn=PERSON['id'])]
        leader_urn = ME['id'] if is_leader else PERSON['id']
        party_group = SimpleNamespace(id='party-grp-1', type=4, leader_urn=leader_urn, members=members)

        def call(domain, service, method, req, confirmed=False):
            if method == 'ListGroups':
                return SimpleNamespace(groups=[party_group], page_info=SimpleNamespace(has_next_page=False))
            return SimpleNamespace()

        c.call = Mock(side_effect=call)
        return c

    def test_kick_party_member_success_as_leader(self):
        c = self.client(is_leader=True)
        res = c.party_manage('kick_party_member', PERSON['id'], CONTEXT, confirmed=True, member_handle=PERSON['handle'])
        self.assertIn("Removed DemoZebra", res)
        # Verify KickGroupMember was called
        calls = [call for call in c.call.call_args_list if call.args[2] == 'KickGroupMember']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3].member_urn, PERSON['id'])
        self.assertEqual(calls[0].args[3].group_id, 'party-grp-1')

    def test_kick_party_member_rejected_when_not_leader(self):
        c = self.client(is_leader=False)
        with self.assertRaisesRegex(ValueError, "party leader"):
            c.party_manage('kick_party_member', PERSON['id'], CONTEXT, confirmed=True)

    def test_transfer_party_leader_success(self):
        c = self.client(is_leader=True)
        res = c.party_manage('transfer_party_leader', PERSON['id'], CONTEXT, confirmed=True, member_handle=PERSON['handle'])
        self.assertIn("Made DemoZebra the party leader", res)
        calls = [call for call in c.call.call_args_list if call.args[2] == 'TransferGroupLeadership']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3].player_urn, PERSON['id'])

    def test_leave_party_success(self):
        c = self.client(is_leader=False)
        res = c.party_manage('leave_party', '', CONTEXT, confirmed=True)
        self.assertEqual(res, "Left party.")
        calls = [call for call in c.call.call_args_list if call.args[2] == 'LeaveGroup']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3].group_id, 'party-grp-1')


class ChatServiceLiveTests(unittest.TestCase):
    def client(self):
        c = object.__new__(PlayerClient)
        c.account = SimpleNamespace(subject=ME['id'])
        c.scope = Mock()
        def make_msg(domain, name):
            ns = SimpleNamespace()
            ns.filters = SimpleNamespace(types=[])
            ns.pagination = SimpleNamespace(first=0, after='')
            ns.metadata = SimpleNamespace(shard_id='')
            return lambda: ns
        c.message = Mock(side_effect=make_msg)

        global_group = SimpleNamespace(id='group-global-1', type=2, name='Global · pub_ape1a_13165946_060', members=[SimpleNamespace(urn=ME['id'])])
        party_group = SimpleNamespace(id='group-party-1', type=4, name='Party', leader_urn=ME['id'], members=[SimpleNamespace(urn=ME['id'])])
        ship_group = SimpleNamespace(id='group-ship-1', type=6, name='Ship: Cutlass Black', members=[SimpleNamespace(urn=ME['id'])])

        msg1 = SimpleNamespace(
            id='m-1',
            group_id='group-global-1',
            sender_urn=PERSON['id'],
            sender_nickname='DemoZebra',
            sender_display_name='Demo Zebra',
            content='[zh] @IH@E8',
            created_at=1794720599616,
        )

        def call(domain, service, method, req, confirmed=False):
            if method == 'ListGroups':
                return SimpleNamespace(groups=[global_group, party_group, ship_group], page_info=SimpleNamespace(has_next_page=False))
            if method == 'ListMessages':
                if getattr(req, 'group_id', '') == 'group-global-1':
                    return SimpleNamespace(messages=[msg1], page_info=SimpleNamespace(has_next_page=False))
                return SimpleNamespace(messages=[], page_info=SimpleNamespace(has_next_page=False))
            if method == 'SendMessage':
                return SimpleNamespace()
            return SimpleNamespace()

        c.call = Mock(side_effect=call)
        return c

    def test_chat_snapshot_decodes_and_translates(self):
        c = self.client()
        tr = Mock()
        tr.translate.return_value = ("Hello", "zh-CN")

        snap = c.chat_snapshot(CONTEXT, known={PERSON['id']: 'DemoZebra'}, translator=tr, auto_translate=True)
        self.assertEqual(len(snap['channels']), 2)
        self.assertEqual(snap['channels'][0]['kind'], 'global')
        self.assertEqual(len(snap['messages']), 1)
        m = snap['messages'][0]
        self.assertEqual(m['content'], "你好")
        self.assertEqual(m['translated_content'], "Hello")
        self.assertTrue(m['was_zh_encoded'])

    def test_send_chat_with_zh_encoding(self):
        c = self.client()
        tr = Mock()
        tr.translate_and_encode_zh.return_value = {"original": "Hello", "zh_text": "你好", "encoded": "[zh] @IH@E8"}

        res = c.send_chat('group-global-1', "Hello", CONTEXT, confirmed=True, encode_zh=True, translator=tr)
        self.assertTrue(res['sent'])
        calls = [call for call in c.call.call_args_list if call.args[2] == 'SendMessage']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3].content, "[zh] @IH@E8")


class CompanionPartyAndChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.social = Mock()
        self.service = CompanionService(self.directory, 42, social=self.social, pool=ImmediatePool())
        self.service.tick(CONTEXT, False, 1000)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_companion_party_people_decorated_and_published(self):
        self.service.roster = [ME, PERSON]
        self.service.relationships = dict(
            friends_at=1000,
            friends=[],
            party_at=1000,
            party=[ME['id'], PERSON['id']],
            party_group_id='grp-1',
            party_leader_id=ME['id'],
            self_id=ME['id'],
        )
        self.service.publish(1001)

        state = json.loads((self.directory / 'companion_state.json').read_text())
        self.assertTrue(state['party_known'])
        self.assertTrue(state['is_party_leader'])
        self.assertEqual(len(state['party_people']), 2)
        self.assertTrue(state['party_people'][0]['is_leader'])
        self.assertTrue(state['party_people'][0]['is_self'])
        self.assertFalse(state['party_people'][1]['is_leader'])

    def test_companion_chat_messages_decorated_with_sender_tags(self):
        self.service.store.data['tags'][PERSON['id']] = dict(
            handle='DemoZebra', label='Trader, Friendly', labels=['Trader', 'Friendly'], alert=False
        )
        self.service.store.data['tags']['custom-key-999'] = dict(
            handle='OtherPilot', label='Pirate', labels=['Pirate'], alert=True
        )
        self.service.chat_messages = [
            dict(
                id='msg-1',
                group_id='grp-global',
                channel_kind='global',
                channel_label='Global',
                sender_id=PERSON['id'],
                sender_handle='DemoZebra',
                content='Selling cargo at Port Tressler',
                at=1000,
            ),
            dict(
                id='msg-2',
                group_id='grp-global',
                channel_kind='global',
                channel_label='Global',
                sender_id=OTHER['id'],
                sender_handle='OtherPilot',
                content='Heading to Yela belt',
                at=1001,
            ),
            dict(
                id='msg-3',
                group_id='grp-global',
                channel_kind='global',
                channel_label='Global',
                sender_id=ME['id'],
                sender_handle='Synthronaut',
                is_self=True,
                content='Copy that',
                at=1002,
            ),
        ]
        self.service.relationships = dict(
            friends_at=1000,
            friends=[PERSON['id']],
            party_at=1000,
            party=[ME['id'], OTHER['id']],
            party_group_id='grp-party-1',
            party_leader_id=ME['id'],
            self_id=ME['id'],
        )
        self.service.publish(1001)

        state = json.loads((self.directory / 'companion_state.json').read_text())
        msgs = state['chat_messages']
        self.assertEqual(len(msgs), 3)

        # Message 1: DemoZebra (tagged Trader, Friendly + friend)
        self.assertIn('Trader', msgs[0]['sender_tags'])
        self.assertIn('Friendly', msgs[0]['sender_tags'])
        self.assertIn('Friend', msgs[0]['sender_tags'])
        self.assertTrue(msgs[0]['is_friend'])
        self.assertFalse(msgs[0]['in_party'])

        # Message 2: OtherPilot (matched by handle -> Pirate + party)
        self.assertIn('Pirate', msgs[1]['sender_tags'])
        self.assertIn('Party', msgs[1]['sender_tags'])
        self.assertTrue(msgs[1]['in_party'])
        self.assertFalse(msgs[1]['is_friend'])

        # Message 3: Synthronaut (self -> no 'Party' badge added to tags)
        self.assertTrue(msgs[2]['is_self'])
        self.assertNotIn('Party', msgs[2]['sender_tags'])


if __name__ == '__main__':
    unittest.main()
