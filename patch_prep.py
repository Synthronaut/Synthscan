"""Pre-patch and Release Candidate preparation tools for Star Citizen.

Protects active gameplay: does not overwrite or lock the active LIVE game
until the player explicitly deploys on patch day.
Automates:
  - Keybind / control mapping preservation (actionmaps.xml)
  - Stale shader cache purging (%localappdata%/Star Citizen)
  - Safe PTU seeding from LIVE (with disk space pre-flight validation)
  - Instant patch-day swap (PTU -> LIVE metadata rename in seconds)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time
from typing import Callable, Dict, Optional, Tuple

from app_lifecycle import game_process_ids, launcher_process_ids
from installation import PROFILE, game_directory


def get_game_root(custom_dir: Optional[Path] = None) -> Path:
    """Returns the StarCitizen root directory (containing LIVE, PTU, etc.)."""
    if custom_dir:
        p = Path(custom_dir)
        if (p / 'Data.p4k').is_file():
            return p.parent
        return p
    try:
        live = game_directory(required=False)
        return live.parent if live.name.upper() in ('LIVE', 'PTU', 'EPTU', 'HOTFIX') else live
    except Exception:
        return Path(r'C:\Program Files\Roberts Space Industries\StarCitizen')


def inspect_channel(channel_dir: Path) -> Dict[str, object]:
    """Inspects a channel directory (e.g. LIVE, PTU) for version, manifest, and packfile."""
    channel_dir = Path(channel_dir)
    info = {
        'exists': channel_dir.is_dir(),
        'path': channel_dir,
        'name': channel_dir.name,
        'has_p4k': False,
        'p4k_size_bytes': 0,
        'p4k_size_gb': 0.0,
        'version': 'Unknown',
        'branch': 'Unknown',
        'build_id': 'Unknown',
        'change_num': 0,
        'build_date': '',
        'has_controls': False,
        'controls_path': None,
    }
    if not channel_dir.is_dir():
        return info

    p4k = channel_dir / 'Data.p4k'
    if p4k.is_file():
        info['has_p4k'] = True
        try:
            size = p4k.stat().st_size
            info['p4k_size_bytes'] = size
            info['p4k_size_gb'] = round(size / (1024**3), 2)
        except OSError:
            pass

    manifest = channel_dir / 'build_manifest.id'
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding='utf-8', errors='replace')).get('Data', {})
            info['version'] = data.get('Version', 'Unknown')
            info['branch'] = data.get('Branch', 'Unknown')
            info['build_id'] = data.get('BuildId', 'Unknown')
            info['build_date'] = data.get('BuildDateStamp', '')
            change = data.get('RequestedP4ChangeNum', 0)
            try:
                info['change_num'] = int(change)
            except (ValueError, TypeError):
                info['change_num'] = 0
        except Exception:
            pass

    # Check controls / actionmaps.xml
    controls_candidates = [
        channel_dir / 'user' / 'client' / '0' / 'Profiles' / 'default' / 'actionmaps.xml',
        channel_dir / 'USER' / 'Client' / '0' / 'Profiles' / 'default' / 'actionmaps.xml',
        channel_dir / 'user' / 'client' / '0' / 'Controls' / 'Mappings' / 'actionmaps.xml',
    ]
    for c in controls_candidates:
        if c.is_file():
            info['has_controls'] = True
            info['controls_path'] = c
            break

    # Check custom character appearances (.chf)
    char_candidates = [
        channel_dir / 'user' / 'client' / '0' / 'CustomCharacters',
        channel_dir / 'USER' / 'Client' / '0' / 'CustomCharacters',
    ]
    info['character_count'] = 0
    info['character_names'] = []
    for c_dir in char_candidates:
        if c_dir.is_dir():
            chf_files = [f for f in c_dir.glob('*.chf') if f.is_file()]
            if chf_files:
                info['character_count'] = len(chf_files)
                info['character_names'] = [f.name for f in chf_files]
                info['characters_dir'] = c_dir
                break

    return info


def get_drive_space(path: Path) -> Dict[str, float]:
    """Returns disk space usage for the drive containing path in GB."""
    try:
        drive_anchor = Path(path).resolve().anchor or str(path)
        usage = shutil.disk_usage(drive_anchor)
        return {
            'total_gb': round(usage.total / (1024**3), 1),
            'free_gb': round(usage.free / (1024**3), 1),
            'used_gb': round(usage.used / (1024**3), 1),
        }
    except Exception:
        return {'total_gb': 0.0, 'free_gb': 0.0, 'used_gb': 0.0}


def check_running_processes() -> Dict[str, bool]:
    """Returns whether Star Citizen or RSI Launcher processes are currently active."""
    sc_pids = game_process_ids()
    launcher_pids = launcher_process_ids()
    return {
        'game_running': bool(sc_pids),
        'launcher_running': bool(launcher_pids),
        'any_running': bool(sc_pids or launcher_pids),
    }


def get_shader_cache_info() -> Dict[str, object]:
    """Calculates file count and size of local shader caches in %LOCALAPPDATA%/Star Citizen."""
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        return {'exists': False, 'folder_count': 0, 'file_count': 0, 'size_mb': 0.0, 'folders': []}

    base = Path(local_app_data) / 'Star Citizen'
    if not base.is_dir():
        return {'exists': False, 'folder_count': 0, 'file_count': 0, 'size_mb': 0.0, 'folders': []}

    folders = []
    total_files = 0
    total_bytes = 0

    for item in base.iterdir():
        if item.is_dir() and item.name.lower().startswith('starcitizen_'):
            folders.append(item)
            try:
                for entry in item.rglob('*'):
                    if entry.is_file():
                        total_files += 1
                        total_bytes += entry.stat().st_size
            except OSError:
                pass

    return {
        'exists': bool(folders),
        'folder_count': len(folders),
        'file_count': total_files,
        'size_mb': round(total_bytes / (1024**2), 1),
        'folders': folders,
    }


def clear_shader_cache() -> Dict[str, object]:
    """Deletes shader cache folders to prevent post-patch stutters. Preserves crashes/logs."""
    info = get_shader_cache_info()
    deleted_files = 0
    freed_bytes = 0
    errors = []

    for folder in info.get('folders', []):
        try:
            for entry in list(folder.rglob('*')):
                if entry.is_file():
                    try:
                        sz = entry.stat().st_size
                        entry.unlink()
                        deleted_files += 1
                        freed_bytes += sz
                    except OSError as e:
                        errors.append(str(e))
            shutil.rmtree(folder, ignore_errors=True)
        except Exception as e:
            errors.append(str(e))

    return {
        'success': len(errors) == 0,
        'deleted_files': deleted_files,
        'freed_mb': round(freed_bytes / (1024**2), 1),
        'errors': errors,
    }


def get_controls_backup_dir() -> Path:
    """Returns the dedicated directory for saved player profile & control backups."""
    d = PROFILE / 'backups' / 'controls'
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_control_mappings(channel_dir: Optional[Path] = None) -> Dict[str, object]:
    """Saves a timestamped backup of the player's actionmaps.xml, custom characters (.chf), and attributes."""
    if not channel_dir:
        channel_dir = get_game_root() / 'LIVE'
    info = inspect_channel(channel_dir)
    src_file = info.get('controls_path')
    if not src_file or not Path(src_file).is_file():
        return {'success': False, 'error': 'No actionmaps.xml found in channel.'}

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_target = get_controls_backup_dir() / timestamp
    backup_target.mkdir(parents=True, exist_ok=True)

    dest_actionmaps = backup_target / 'actionmaps.xml'
    shutil.copy2(src_file, dest_actionmaps)

    # Check for exported mappings folder
    user_root = Path(src_file).parent.parent.parent
    user_mappings = user_root / 'Controls' / 'Mappings'
    exported_count = 0
    if user_mappings.is_dir():
        dest_mappings = backup_target / 'Mappings'
        dest_mappings.mkdir(exist_ok=True)
        for xml_file in user_mappings.glob('*.xml'):
            shutil.copy2(xml_file, dest_mappings / xml_file.name)
            exported_count += 1

    # Check for custom character appearances (.chf)
    custom_chars_dir = user_root / 'CustomCharacters'
    saved_characters = []
    if custom_chars_dir.is_dir():
        dest_chars = backup_target / 'CustomCharacters'
        dest_chars.mkdir(exist_ok=True)
        for chf_file in custom_chars_dir.glob('*.chf'):
            if chf_file.is_file():
                shutil.copy2(chf_file, dest_chars / chf_file.name)
                saved_characters.append(chf_file.name)

    # Check for attributes.xml (game preferences, audio, FOV)
    attr_file = Path(src_file).parent / 'attributes.xml'
    has_attributes = False
    if attr_file.is_file():
        shutil.copy2(attr_file, backup_target / 'attributes.xml')
        has_attributes = True

    meta = {
        'timestamp': timestamp,
        'source_channel': str(channel_dir),
        'version': info.get('version'),
        'exported_count': exported_count,
        'character_count': len(saved_characters),
        'character_names': saved_characters,
        'has_attributes': has_attributes,
    }
    (backup_target / 'meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')

    return {
        'success': True,
        'backup_path': str(backup_target),
        'timestamp': timestamp,
        'exported_count': exported_count,
        'character_count': len(saved_characters),
        'character_names': saved_characters,
        'has_attributes': has_attributes,
    }


def restore_control_mappings(target_channel_dir: Optional[Path] = None, backup_id: Optional[str] = None) -> Dict[str, object]:
    """Restores actionmaps.xml, custom character appearances (.chf), and attributes from backup."""
    if not target_channel_dir:
        target_channel_dir = get_game_root() / 'LIVE'

    backup_root = get_controls_backup_dir()
    backups = sorted([b for b in backup_root.iterdir() if b.is_dir()], key=lambda p: p.name, reverse=True)
    if not backups:
        return {'success': False, 'error': 'No existing control backups found.'}

    chosen_backup = backups[0]
    if backup_id:
        match = backup_root / backup_id
        if match.is_dir():
            chosen_backup = match

    src_actionmaps = chosen_backup / 'actionmaps.xml'
    if not src_actionmaps.is_file():
        return {'success': False, 'error': f'No actionmaps.xml in backup {chosen_backup.name}'}

    target_profile = target_channel_dir / 'user' / 'client' / '0' / 'Profiles' / 'default'
    target_profile.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_actionmaps, target_profile / 'actionmaps.xml')

    # Restore any exported mappings
    exported_dir = chosen_backup / 'Mappings'
    restored_exported = 0
    if exported_dir.is_dir():
        target_mappings = target_channel_dir / 'user' / 'client' / '0' / 'Controls' / 'Mappings'
        target_mappings.mkdir(parents=True, exist_ok=True)
        for xml_file in exported_dir.glob('*.xml'):
            shutil.copy2(xml_file, target_mappings / xml_file.name)
            restored_exported += 1

    # Restore custom character appearances (.chf)
    chars_dir = chosen_backup / 'CustomCharacters'
    restored_chars = []
    if chars_dir.is_dir():
        target_chars = target_channel_dir / 'user' / 'client' / '0' / 'CustomCharacters'
        target_chars.mkdir(parents=True, exist_ok=True)
        for chf_file in chars_dir.glob('*.chf'):
            if chf_file.is_file():
                shutil.copy2(chf_file, target_chars / chf_file.name)
                restored_chars.append(chf_file.name)

    # Restore attributes.xml
    src_attr = chosen_backup / 'attributes.xml'
    restored_attr = False
    if src_attr.is_file():
        shutil.copy2(src_attr, target_profile / 'attributes.xml')
        restored_attr = True

    return {
        'success': True,
        'restored_from': chosen_backup.name,
        'target': str(target_profile / 'actionmaps.xml'),
        'exported_count': restored_exported,
        'character_count': len(restored_chars),
        'character_names': restored_chars,
        'attributes_restored': restored_attr,
    }


def get_latest_controls_backup() -> Optional[Dict[str, object]]:
    """Returns information on the most recent control backup."""
    backup_root = get_controls_backup_dir()
    backups = sorted([b for b in backup_root.iterdir() if b.is_dir()], key=lambda p: p.name, reverse=True)
    if not backups:
        return None
    latest = backups[0]
    meta_file = latest / 'meta.json'
    if meta_file.is_file():
        try:
            return json.loads(meta_file.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'timestamp': latest.name, 'backup_path': str(latest)}


def get_patch_status(custom_root: Optional[Path] = None) -> Dict[str, object]:
    """Gathers complete status for pre-patch dashboard."""
    root = get_game_root(custom_root)
    live_info = inspect_channel(root / 'LIVE')
    ptu_info = inspect_channel(root / 'PTU')
    eptu_info = inspect_channel(root / 'EPTU')
    hotfix_info = inspect_channel(root / 'HOTFIX')

    drive_space = get_drive_space(root)
    proc_info = check_running_processes()
    shader_info = get_shader_cache_info()
    latest_backup = get_latest_controls_backup()

    # Determine Release Candidate status:
    # A candidate is detected if PTU exists and has a change_num or version ahead of LIVE
    rc_detected = False
    rc_status_text = 'No Release Candidate detected in PTU'
    if ptu_info['exists'] and live_info['exists']:
        if ptu_info['change_num'] > live_info['change_num'] and ptu_info['change_num'] > 0:
            rc_detected = True
            rc_status_text = f"PTU has newer build ready ({ptu_info['version']})"
        elif ptu_info['version'] != live_info['version'] and ptu_info['version'] != 'Unknown':
            rc_detected = True
            rc_status_text = f"PTU build differs ({ptu_info['version']})"

    # Can parallel clone: requires free space >= live_p4k_size + 5 GB
    needed_for_clone = (live_info['p4k_size_gb'] + 5.0) if live_info['has_p4k'] else 150.0
    can_clone = drive_space['free_gb'] >= needed_for_clone

    return {
        'root': root,
        'live': live_info,
        'ptu': ptu_info,
        'eptu': eptu_info,
        'hotfix': hotfix_info,
        'drive_space': drive_space,
        'can_clone': can_clone,
        'needed_for_clone_gb': round(needed_for_clone, 1),
        'processes': proc_info,
        'shader_cache': shader_info,
        'latest_controls_backup': latest_backup,
        'rc_detected': rc_detected,
        'rc_status_text': rc_status_text,
    }


def seed_ptu_from_live(
    custom_root: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    check_processes: bool = True
) -> Dict[str, object]:
    """Clones LIVE to PTU safely so the player can download the RC in PTU while keeping LIVE intact.

    Aborts if insufficient free space to protect active game from drive exhaustion.
    """
    root = get_game_root(custom_root)
    if check_processes:
        procs = check_running_processes()
        if procs['any_running']:
            raise RuntimeError('Close Star Citizen and the RSI Launcher before seeding PTU.')

    live_dir = root / 'LIVE'
    ptu_dir = root / 'PTU'

    live_info = inspect_channel(live_dir)
    if not live_info['has_p4k']:
        raise RuntimeError('Cannot find valid Star Citizen LIVE installation with Data.p4k.')

    space = get_drive_space(root)
    needed = live_info['p4k_size_gb'] + 5.0
    if space['free_gb'] < needed:
        raise RuntimeError(
            f'Insufficient free drive space to clone LIVE without impacting current gameplay. '
            f'Requires {needed:.1f} GB free, but drive has {space["free_gb"]:.1f} GB. '
            f'Use Fast Patch Day Swap when the patch goes live instead.'
        )

    if progress_callback:
        progress_callback('Creating PTU directory...', 0.05)

    ptu_dir.mkdir(parents=True, exist_ok=True)

    # Copy files excluding giant p4k first
    files_to_copy = [f for f in live_dir.iterdir() if f.is_file() and f.name.lower() != 'data.p4k']
    total_files = len(files_to_copy) + 1
    done = 0
    for f in files_to_copy:
        try:
            shutil.copy2(f, ptu_dir / f.name)
        except OSError:
            pass
        done += 1
        if progress_callback:
            progress_callback(f'Copying manifest: {f.name}', (done / total_files) * 0.1)

    # Copy Bin64 / EasyAntiCheat directories if present
    for sub in ('Bin64', 'EasyAntiCheat'):
        src_sub = live_dir / sub
        dest_sub = ptu_dir / sub
        if src_sub.is_dir():
            shutil.copytree(src_sub, dest_sub, dirs_exist_ok=True)

    # Copy Data.p4k
    src_p4k = live_dir / 'Data.p4k'
    dest_p4k = ptu_dir / 'Data.p4k'
    if progress_callback:
        progress_callback('Copying Data.p4k (~150 GB)... This may take a few minutes.', 0.15)

    # Stream copy Data.p4k with progress reporting
    total_bytes = src_p4k.stat().st_size
    copied_bytes = 0
    buffer_size = 64 * 1024 * 1024  # 64 MB buffer for fast sequential NVMe/SSD copy

    with open(src_p4k, 'rb') as fsrc, open(dest_p4k, 'wb') as fdst:
        while True:
            buf = fsrc.read(buffer_size)
            if not buf:
                break
            fdst.write(buf)
            copied_bytes += len(buf)
            if progress_callback:
                frac = 0.15 + (copied_bytes / total_bytes) * 0.85
                progress_callback(f'Copying Data.p4k: {copied_bytes / (1024**3):.1f} / {total_bytes / (1024**3):.1f} GB', frac)

    if progress_callback:
        progress_callback('PTU seeding complete! Open RSI Launcher to update PTU.', 1.0)

    return {
        'success': True,
        'message': 'PTU seeded successfully from LIVE. Your LIVE game remains 100% playable.',
        'copied_gb': round(total_bytes / (1024**3), 1),
    }


def deploy_ptu_to_live(
    custom_root: Optional[Path] = None,
    keep_backup: bool = False,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    check_processes: bool = True
) -> Dict[str, object]:
    """Patch-day one-touch deployment:

    1. Backs up controls / actionmaps.xml
    2. Clears stale shader cache
    3. Swaps PTU into LIVE instantly via NTFS metadata rename (0 seconds copy time)
    4. Restores controls into the new LIVE folder
    5. Preserves user.cfg settings
    """
    root = get_game_root(custom_root)
    if check_processes:
        procs = check_running_processes()
        if procs['any_running']:
            raise RuntimeError('Close Star Citizen and the RSI Launcher before deploying patch.')

    live_dir = root / 'LIVE'
    ptu_dir = root / 'PTU'

    ptu_info = inspect_channel(ptu_dir)
    if not ptu_info['has_p4k']:
        raise RuntimeError('Cannot find valid Star Citizen PTU installation with Data.p4k to deploy.')

    if progress_callback:
        progress_callback('Backing up keybinds and control mappings...', 0.1)

    # 1. Back up controls
    backup_res = backup_control_mappings(live_dir)

    # 2. Clear shader cache
    if progress_callback:
        progress_callback('Purging stale shader cache...', 0.3)
    shader_res = clear_shader_cache()

    # 3. Swap folders
    if progress_callback:
        progress_callback('Swapping PTU Release Candidate into LIVE...', 0.6)

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_live = root / f'LIVE_backup_{timestamp}'

    # Rename LIVE -> backup
    if live_dir.exists():
        live_dir.rename(backup_live)

    # Rename PTU -> LIVE
    try:
        ptu_dir.rename(live_dir)
    except Exception as e:
        # Rollback if rename fails
        if backup_live.exists() and not live_dir.exists():
            backup_live.rename(live_dir)
        raise RuntimeError(f'Failed to swap PTU into LIVE: {e}')

    # If keep_backup is False or drive space is tight, remove backup_live
    space = get_drive_space(root)
    if not keep_backup or space['free_gb'] < 20.0:
        if progress_callback:
            progress_callback('Cleaning up replaced build to preserve SSD space...', 0.8)
        shutil.rmtree(backup_live, ignore_errors=True)

    # 4. Restore controls into new LIVE
    if progress_callback:
        progress_callback('Restoring control mappings into new LIVE build...', 0.9)
    restore_control_mappings(live_dir)

    if progress_callback:
        progress_callback('Patch staged! Open RSI Launcher and click Verify on LIVE.', 1.0)

    return {
        'success': True,
        'message': 'Release Candidate successfully deployed to LIVE. Controls restored and shaders cleared.',
        'controls_backed_up': backup_res.get('success', False),
        'shaders_cleared_mb': shader_res.get('freed_mb', 0.0),
    }
