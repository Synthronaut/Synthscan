"""End-to-end verification of signed update-only publishing, data preservation, and rollback in an isolated profile."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import time
from unittest.mock import patch
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_updates import SCHEMA, activate, active_token, digest, load, stage, write
from feature_modules import FEATURES
from module_distribution import MANIFEST, selection_token
from update_signing import envelope, generate_key


def write_dummy_module_zip(folder, mod_id, version, files_dict, url_base):
    mod_dir = folder / f"tree_{mod_id}"
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    mod_dir.mkdir(parents=True)
    for rel, content in files_dict.items():
        target = mod_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding='utf-8')
    inv_files = {p.relative_to(mod_dir).as_posix(): digest(p) for p in sorted(mod_dir.rglob('*')) if p.is_file()}
    comp = dict(schema=1, id=mod_id, version=version, files=inv_files)
    (mod_dir / MANIFEST).write_text(json.dumps(comp, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    zip_path = folder / f"SynthScan-module-{mod_id}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(mod_dir.rglob('*')):
            if p.is_file():
                zf.write(p, 'SynthScan/' + p.relative_to(mod_dir).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        unpacked = sum(i.file_size for i in zf.infolist())
    return dict(
        id=mod_id,
        version=version,
        size=zip_path.stat().st_size,
        unpacked_size=unpacked,
        sha256=digest(zip_path),
        inventory_sha256=digest(mod_dir / MANIFEST),
        url=f"{url_base}/{zip_path.name}",
        requires=list(FEATURES[mod_id][1]) if mod_id in FEATURES else [],
    ), zip_path


def build_signed_catalog(staging_dir, version, sequence, ui_marker, priv, pub, url_base):
    packages = {}
    archives = {}
    core_files = {
        'SynthScan.exe': b'MZ-bootstrap-stub',
        'app_launcher.py': '# launcher\n',
        'app_updates.py': (ROOT / 'app_updates.py').read_bytes(),
        'update_agent.py': (ROOT / 'update_agent.py').read_bytes(),
        'update_signing.py': (ROOT / 'update_signing.py').read_bytes(),
        'edition_payload.py': (ROOT / 'edition_payload.py').read_bytes(),
        'feature_modules.py': (ROOT / 'feature_modules.py').read_bytes(),
        'module_distribution.py': (ROOT / 'module_distribution.py').read_bytes(),
        'module_setup.py': 'import sys\nsys.exit(0)\n',
        'update_trust.json': (ROOT / 'update_trust.json').read_bytes(),
        'release.json': json.dumps(dict(
            version=version,
            channel='community-alpha',
            edition='standard',
            screen_reading=False,
            updater_schema=SCHEMA,
            setup_schema=1,
            module_schema=1,
            modules=[],
            selection_configured=False,
        )),
        'runtime/python.exe': Path(sys.executable).read_bytes(),
        'runtime/pythonw.exe': Path(sys.executable).read_bytes(),
        'runtime/python314.dll': b'DLL-stub',
        'runtime/Lib/encodings/__init__.py': '# encodings\n',
        'dist/native/SynthScan.exe': b'MZ-native-standard',
        'dist/native/build_manifest.json': json.dumps(dict(edition='standard', screen_reading=False)),
        'ui/dist/index.html': (ROOT / 'ui/dist/index.html').read_text(encoding='utf-8') + f"\n<!-- {ui_marker} -->\n",
        'ui/dist/assets/app.js': (ROOT / 'ui/dist/assets/app.js').read_bytes(),
        'ui/dist/assets/index.css': (ROOT / 'ui/dist/assets/index.css').read_bytes(),
    }
    item, zpath = write_dummy_module_zip(staging_dir, 'core', version, core_files, url_base)
    packages['core'] = item
    archives[zpath.name] = zpath.read_bytes()

    for feat_id, (label, requires, capabilities, detail) in FEATURES.items():
        feat_files = {
            f'features/{feat_id}.json': json.dumps(dict(
                schema=1,
                id=feat_id,
                label=label,
                requires=requires,
                capabilities=capabilities,
                description=detail,
                shared_native_ui=True,
                marker=ui_marker,
            ))
        }
        if feat_id == 'mining_recognition':
            feat_files['dist/native/SynthScan.exe'] = b'MZ-native-full'
            feat_files['dist/native/build_manifest.json'] = json.dumps(dict(edition='full', screen_reading=True))
        item, zpath = write_dummy_module_zip(staging_dir, feat_id, version, feat_files, url_base)
        packages[feat_id] = item
        archives[zpath.name] = zpath.read_bytes()

    now = time.time()
    payload = dict(
        schema=1,
        kind='modules',
        platform='windows-x64',
        version=version,
        sequence=sequence,
        minimum_manager=1,
        issued_at=now,
        expires_at=now + 365 * 86400,
        packages=packages,
    )
    signed_bytes = (json.dumps(envelope(payload, priv, pub), indent=2) + '\n').encode('utf-8')
    return signed_bytes, archives


def build_signed_legacy_zip(staging_dir, version, sequence, ui_marker, priv, pub, url_base):
    app_dir = staging_dir / f"legacy_{version}"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    app_dir.mkdir(parents=True)
    files = {
        'SynthScan.exe': b'MZ-bootstrap-stub',
        'app_launcher.py': '# launcher\n',
        'app_updates.py': (ROOT / 'app_updates.py').read_bytes(),
        'update_agent.py': (ROOT / 'update_agent.py').read_bytes(),
        'update_signing.py': (ROOT / 'update_signing.py').read_bytes(),
        'edition_payload.py': (ROOT / 'edition_payload.py').read_bytes(),
        'update_trust.json': (ROOT / 'update_trust.json').read_bytes(),
        'release.json': json.dumps(dict(
            version=version,
            channel='community-alpha',
            edition='full',
            screen_reading=True,
            updater_schema=SCHEMA,
            setup_schema=1,
        )),
        'runtime/pythonw.exe': b'MZ-pythonw',
        'runtime/python314.dll': b'DLL-stub',
        'runtime/Lib/encodings/__init__.py': '# encodings\n',
        'dist/native/SynthScan.exe': b'MZ-native-full',
        'dist/native/build_manifest.json': json.dumps(dict(edition='full', screen_reading=True)),
        'ui/dist/index.html': (ROOT / 'ui/dist/index.html').read_text(encoding='utf-8') + f"\n<!-- {ui_marker} -->\n",
    }
    for rel, content in files.items():
        target = app_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding='utf-8')
    manifest = {p.relative_to(app_dir).as_posix(): digest(p) for p in sorted(app_dir.rglob('*')) if p.is_file()}
    (app_dir / 'release_integrity.json').write_text(json.dumps(dict(version=version, files=manifest)), encoding='utf-8')
    zip_name = f"SynthScan-full-{version}.zip"
    zip_path = staging_dir / zip_name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(app_dir.rglob('*')):
            if p.is_file():
                zf.write(p, 'SynthScan/' + p.relative_to(app_dir).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        unpacked = sum(i.file_size for i in zf.infolist() if not i.is_dir())
    now = time.time()
    value = dict(
        schema=1,
        kind='application',
        platform='windows-x64',
        version=version,
        sequence=sequence,
        issued_at=now,
        expires_at=now + 365 * 86400,
        edition='full',
        minimum_updater=1,
        size=zip_path.stat().st_size,
        unpacked_size=unpacked,
        sha256=digest(zip_path),
        url=f"{url_base}/{zip_name}",
    )
    signed_bytes = (json.dumps(envelope(value, priv, pub), indent=2) + '\n').encode('utf-8')
    return signed_bytes, zip_name, zip_path.read_bytes()


def verify_auto_update(output_path=None):
    with tempfile.TemporaryDirectory(prefix='SynthScan-auto-update-test-') as tmp:
        base = Path(tmp)
        priv, pub = generate_key()
        key_id = hashlib.sha256(pub).hexdigest()[:16]
        url_base = 'https://github.com/Synthronaut/Synthscan/releases/download/update-channel'
        trust = dict(
            schema=1,
            manifest_url=f'{url_base}/synthscan-update.json',
            standard_manifest_url=f'{url_base}/synthscan-update-standard.json',
            modules_manifest_url=f'{url_base}/synthscan-modules.json',
            allowed_hosts=['github.com', 'objects.githubusercontent.com'],
            keys={key_id: base64.b64encode(pub).decode('ascii')},
        )

        server_files = {}

        def fake_opener(url, _trust):
            name = url.rsplit('/', 1)[-1]
            if name not in server_files:
                raise FileNotFoundError(url)
            return io.BytesIO(server_files[name])

        # 1. Build v0.1.0-alpha.11.1 (initial modular installation)
        cat_v1, archives_v1 = build_signed_catalog(base / 'build_v1', '0.1.0-alpha.11.1', 1001, 'v1-initial', priv, pub, url_base)
        server_files['synthscan-modules.json'] = cat_v1
        server_files.update(archives_v1)

        mod_install = base / 'modular_app'
        mod_profile = base / 'modular_profile'
        mod_install.mkdir()
        mod_profile.mkdir()
        selected_features = ['people', 'server_hud', 'daylight']
        # Unpack initial v1 core + selected features into mod_install
        with zipfile.ZipFile(io.BytesIO(archives_v1['SynthScan-module-core.zip'])) as zf:
            for m in zf.infolist():
                if m.is_dir() or m.filename.endswith(MANIFEST):
                    continue
                rel = m.filename[len('SynthScan/'):]
                t = mod_install / rel
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(zf.read(m))
        for feat in selected_features:
            with zipfile.ZipFile(io.BytesIO(archives_v1[f'SynthScan-module-{feat}.zip'])) as zf:
                for m in zf.infolist():
                    if m.is_dir() or m.filename.endswith(MANIFEST):
                        continue
                    rel = m.filename[len('SynthScan/'):]
                    t = mod_install / rel
                    t.parent.mkdir(parents=True, exist_ok=True)
                    t.write_bytes(zf.read(m))
        rel_json = load(mod_install / 'release.json')
        rel_json.update(modules=selected_features, selection_configured=True)
        write(mod_install / 'release.json', rel_json)
        cat_v1_hash = hashlib.sha256(cat_v1).hexdigest()
        write(mod_install / 'module_lock.json', dict(
            schema=1,
            token=selection_token(cat_v1_hash, selected_features),
            catalog=cat_v1_hash,
            modules=selected_features,
        ))

        # Populate player data in isolated profile (tags, notes, server history, setup)
        player_private = {
            'tags': {
                'pilot-alpha': {'handle': 'PilotAlpha', 'label': 'Friend, Crew', 'notes': 'Met at Grim HEX', 'alert': True},
                'pilot-beta': {'handle': 'PilotBeta', 'label': 'Trader', 'notes': 'Sells Quantanium', 'alert': False},
            },
            'watches': [{'id': 'w1', 'name': 'Quantanium', 'quality': 900, 'minimum_price': 25000, 'enabled': True}],
        }
        write(mod_profile / 'companion_private.json', player_private)
        write(mod_profile / 'workspace_library.json', {'rows': [{'id': 'pilot-alpha', 'handle': 'PilotAlpha', 'tag': 'Friend, Crew'}]})
        write(mod_profile / 'server_log.json', {'sessions': [{'shard': 'us_east_001', 'joined_at': 1700000000}]})
        write(mod_profile / 'setup_result.json', {'complete': True, 'app_version': '0.1.0-alpha.11.1'})

        # 2. Publish small update v0.1.0-alpha.11.2 (sequence 1002)
        cat_v2, archives_v2 = build_signed_catalog(base / 'build_v2', '0.1.0-alpha.11.2', 1002, 'v2-small-update', priv, pub, url_base)
        server_files['synthscan-modules.json'] = cat_v2
        server_files.update(archives_v2)

        staged_v2 = stage(mod_install, mod_profile, trust=trust, opener=fake_opener)
        assert staged_v2['status'] == 'staged' and staged_v2['version'] == '0.1.0-alpha.11.2', f"Unexpected stage: {staged_v2}"
        maintenance_calls = []
        with patch('app_updates.module_maintenance', side_effect=lambda target, current, directory, prune=False, install=None: maintenance_calls.append((str(target), prune))):
            tx_v2 = activate(
                mod_install,
                mod_install,
                mod_profile,
                health=lambda target: (target / 'ui/dist/index.html').is_file(),
                launch=lambda target, updated: None,
                trust=trust,
            )
        v2_token = active_token(mod_install)
        v2_dir = mod_install / 'versions' / v2_token
        assert tx_v2['phase'] == 'applied' and v2_token == tx_v2['active']
        assert load(v2_dir / 'release.json')['version'] == '0.1.0-alpha.11.2'
        assert sorted(load(v2_dir / 'release.json')['modules']) == sorted(selected_features)
        assert 'v2-small-update' in (v2_dir / 'ui/dist/index.html').read_text(encoding='utf-8')
        assert load(mod_profile / 'companion_private.json') == player_private
        assert load(mod_profile / 'server_log.json')['sessions'][0]['shard'] == 'us_east_001'
        assert load(mod_profile / 'setup_result.json')['app_version'] == '0.1.0-alpha.11.2'

        # 3. Publish deliberately broken update v0.1.0-alpha.11.3 (sequence 1003) and prove rollback
        cat_v3, archives_v3 = build_signed_catalog(base / 'build_v3', '0.1.0-alpha.11.3', 1003, 'v3-broken-update', priv, pub, url_base)
        server_files['synthscan-modules.json'] = cat_v3
        server_files.update(archives_v3)

        staged_v3 = stage(v2_dir, mod_profile, trust=trust, opener=fake_opener)
        assert staged_v3['status'] == 'staged' and staged_v3['version'] == '0.1.0-alpha.11.3'
        rolled_back = False
        try:
            with patch('app_updates.module_maintenance', side_effect=lambda target, current, directory, prune=False, install=None: None):
                activate(
                    mod_install,
                    v2_dir,
                    mod_profile,
                    health=lambda target: False,  # Deliberate readiness failure
                    launch=lambda target, updated: None,
                    trust=trust,
                )
        except RuntimeError:
            rolled_back = True
        assert rolled_back, 'Broken update should have raised RuntimeError and rolled back'
        assert active_token(mod_install) == v2_token, 'Active version pointer did not roll back to v2'
        assert load(mod_profile / 'updates/transaction.json')['phase'] == 'rolled_back'
        assert load(mod_profile / 'updates/failed.json')['sha256'] == staged_v3.get('sha256', load(mod_profile / 'updates/failed.json').get('sha256'))
        assert load(mod_profile / 'companion_private.json') == player_private
        assert load(mod_profile / 'setup_result.json')['app_version'] == '0.1.0-alpha.11.2'

        # Subsequent automatic stage check rejects the broken update without looping
        rejected_v3 = stage(v2_dir, mod_profile, trust=trust, opener=fake_opener)
        assert rejected_v3['status'] == 'rejected'

        # 4. Also verify non-modular (legacy channel) installation receives signed update
        leg_install = base / 'legacy_app'
        leg_profile = base / 'legacy_profile'
        leg_install.mkdir()
        leg_profile.mkdir()
        leg_manifest_v2, leg_zip_name, leg_zip_bytes = build_signed_legacy_zip(
            base / 'build_leg_v2', '0.1.0-alpha.11.2', 1002, 'v2-legacy-update', priv, pub, url_base
        )
        server_files['synthscan-update.json'] = leg_manifest_v2
        server_files[leg_zip_name] = leg_zip_bytes
        write(leg_install / 'SynthScan.exe', 'stub')
        write(leg_install / 'release.json', dict(
            version='0.1.0-alpha.11.1',
            channel='community-alpha',
            edition='full',
            screen_reading=True,
            updater_schema=SCHEMA,
            setup_schema=1,
        ))
        leg_staged = stage(leg_install, leg_profile, trust=trust, opener=fake_opener)
        assert leg_staged['status'] == 'staged' and leg_staged['version'] == '0.1.0-alpha.11.2'
        leg_tx = activate(
            leg_install,
            leg_install,
            leg_profile,
            health=lambda target: (target / 'ui/dist/index.html').is_file(),
            launch=lambda target, updated: None,
            trust=trust,
        )
        assert leg_tx['phase'] == 'applied'

        report = dict(
            passed=True,
            modular_update_applied=True,
            features_preserved=sorted(load(v2_dir / 'release.json')['modules']),
            player_tags_preserved=True,
            history_preserved=True,
            broken_update_rolled_back=True,
            broken_update_marked_rejected=rejected_v3['status'] == 'rejected',
            legacy_channel_update_applied=leg_tx['phase'] == 'applied',
        )
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    verify_auto_update(args.output)
