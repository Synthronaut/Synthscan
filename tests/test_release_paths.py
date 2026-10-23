import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import installation
from tools.package_community import audit


class CommunityIsolationTests(unittest.TestCase):
    def test_release_uses_selected_installation_and_private_build_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'Other game disk'/'PTU';(game/'Bin64').mkdir(parents=True)
            for name in ['Data.p4k','Bin64/StarCitizen.exe']:(game/name).write_bytes(b'test')
            build='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
            (game/'build_manifest.id').write_text(json.dumps(dict(Data=dict(BuildId=build))))
            profile=root/'Person A'/'native';profile.mkdir(parents=True)
            (profile/'installation.json').write_text(json.dumps(dict(game_dir=str(game))))
            with patch.object(installation,'PROFILE',profile),patch.object(installation,'RELEASE',True),patch.dict(os.environ,{'SYNTHSCAN_GAME_DIR':''}):
                paths=installation.reference_paths()
                self.assertEqual(paths['game'],game.resolve())
                self.assertTrue(paths['schemas'].is_relative_to(profile.parent))
                self.assertNotIn('research',paths['schemas'].parts)
                other=root/'Person B'/'native';other.mkdir(parents=True)
                with patch.object(installation,'PROFILE',other):
                    self.assertNotEqual(installation.output_root(),profile.parent/'reference/active')

    def test_private_files_are_rejected_from_public_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'reputation_snapshot.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Private file'):audit(root)

    def test_release_never_automatically_imports_a_workspace_profile(self):
        import native_workspace_data as workspace
        with tempfile.TemporaryDirectory() as folder,patch.object(installation,'RELEASE',True):
            result=workspace.migrate(Path(folder)/'new-person')
            self.assertEqual(result['files'],{})
            self.assertFalse((Path(folder)/'new-person/legacy').exists())
