import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

from native_displayinfo_bindings import build_profile, install_profile, remove_profile


SOURCE = b'''<profile version="1"><platforms><PC><keyboard/></PC></platforms>
<ActivationModes><mode name="tap"/></ActivationModes>
<actionmap name="default" version="24"><action name="toggle_chat" keyboard="f12"/></actionmap>
<actionmap name="player"><action name="jump" keyboard="space"/></actionmap></profile>'''


class NativeProfileTests(unittest.TestCase):
    def test_keeps_original_profile_and_adds_exactly_two_actions(self):
        root = ET.fromstring(build_profile(SOURCE))
        default = root.find("./actionmap[@name='default']")
        self.assertEqual(default[0].attrib, {"name": "toggle_chat", "keyboard": "f12"})
        self.assertEqual([(x.get("name"), x.get("keyboard"), x.get("consoleCmd")) for x in default[1:]],
                         [("r_DisplayInfo 1", "f14", "1"), ("r_DisplayInfo 0", "f15", "1")])
        for element in list(default)[1:]:
            default.remove(element)
        self.assertEqual(ET.tostring(root), ET.tostring(ET.fromstring(SOURCE)))

    def test_rejects_existing_reserved_key_or_incomplete_profile(self):
        for source in (SOURCE.replace(b'keyboard="space"', b'keyboard="lctrl+f14"'),
                       SOURCE.replace(b'<platforms><PC><keyboard/></PC></platforms>', b''),
                       build_profile(SOURCE)):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    build_profile(source)

    def fixture(self, folder):
        game = folder / "game"
        (game / "Bin64").mkdir(parents=True)
        (game / "Bin64/StarCitizen.exe").write_bytes(b"test build")
        (game / "USER/Client/0/Controls").mkdir(parents=True)
        (game / "USER/Client/0/Profiles/default").mkdir(parents=True)
        personal = game / "USER/Client/0/Profiles/default/actionmaps.xml"
        personal.write_bytes(b'<ActionProfiles><actionmap name="player"><action name="jump"><rebind input="kb1_space"/></action></actionmap></ActionProfiles>')
        candidate = folder / "candidate.xml"
        candidate.write_bytes(build_profile(SOURCE))
        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps({"exe_sha256": hashlib.sha256(b"test build").hexdigest(),
                                       "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}))
        return game, candidate, manifest, personal

    def test_install_and_remove_only_new_override(self):
        with tempfile.TemporaryDirectory() as temp:
            game, candidate, manifest, personal = self.fixture(Path(temp))
            original = personal.read_bytes()
            state = install_profile(candidate, manifest, game, game_running=False)
            target = Path(state["target"])
            self.assertEqual(target.read_bytes(), candidate.read_bytes())
            self.assertEqual(personal.read_bytes(), original)
            remove_profile(manifest, game, game_running=False)
            self.assertFalse(target.exists())
            self.assertEqual(personal.read_bytes(), original)

    def test_refuses_running_game_changed_build_and_override_collision(self):
        with tempfile.TemporaryDirectory() as temp:
            game, candidate, manifest, personal = self.fixture(Path(temp))
            with self.assertRaises(RuntimeError):
                install_profile(candidate, manifest, game, game_running=True)
            target = game / "USER/Client/0/Controls/defaultProfile.xml"
            self.assertFalse(target.exists())
            target.write_bytes(b"existing custom profile")
            with self.assertRaises(FileExistsError):
                install_profile(candidate, manifest, game, game_running=False)
            self.assertEqual(target.read_bytes(), b"existing custom profile")
            (game / "Bin64/StarCitizen.exe").write_bytes(b"patched")
            with self.assertRaises(RuntimeError):
                install_profile(candidate, manifest, game, game_running=False)

    def test_refuses_personal_key_collision_and_modified_uninstall_target(self):
        with tempfile.TemporaryDirectory() as temp:
            game, candidate, manifest, personal = self.fixture(Path(temp))
            original = personal.read_bytes()
            personal.write_bytes(original.replace(b"kb1_space", b"kb1_f15"))
            with self.assertRaises(RuntimeError):
                install_profile(candidate, manifest, game, game_running=False)
            personal.write_bytes(original)
            state = install_profile(candidate, manifest, game, game_running=False)
            target = Path(state["target"])
            target.write_bytes(b"user edit")
            with self.assertRaises(RuntimeError):
                remove_profile(manifest, game, game_running=False)
            self.assertEqual(target.read_bytes(), b"user edit")


if __name__ == "__main__":
    unittest.main()
