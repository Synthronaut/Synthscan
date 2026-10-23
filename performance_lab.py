"""Read-only graphics inventory and measured benchmark comparisons.

No game memory access, injection, input automation, setting writes, or automatic
optimization. Resource categories below are hypotheses until measured per build.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET

GAME = Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE')
LOCAL = Path(os.environ.get('LOCALAPPDATA', '.')) / 'Star Citizen'
ATTRIBUTES = Path('user/client/0/Profiles/default/attributes.xml')
CATALOG = [
    ('GraphicsRenderer', 'Graphics renderer', 'CPU submission / GPU / driver', 'All scenes; separate warmed game launches', 'Compare DX11 and Vulkan separately; renderer changes require restart.'),
    ('SysSpec', 'Overall quality preset', 'Multiple systems', 'Screening only', 'A preset changes several settings; it cannot identify an individual setting cost.'),
    ('Width', 'Output width', 'GPU / VRAM', 'GPU-heavy exterior and small moving targets', 'Retain native output for the initial comparison; test internal upscaling separately.'),
    ('Height', 'Output height', 'GPU / VRAM', 'GPU-heavy exterior and small moving targets', 'Resolution and upscaling are interacting variables.'),
    ('WindowMode', 'Window mode', 'Presentation / compositor', 'Same scene, same focus and monitors', 'Check frame pacing and Discord on the second display.'),
    ('VSync', 'V-sync', 'Presentation / latency', 'Motion and repeatable input', 'Record refresh rate, frame cap, and driver overrides; FPS alone misses latency and tearing.'),
    ('UpscalingTechnique', 'Upscaling technique', 'GPU / temporal reconstruction', 'Fine detail, movement, dark targets', 'Raw enum requires menu verification; compare shimmer, ghosting, and silhouette clarity.'),
    ('Upscaling', 'Upscaling quality / scale', 'GPU / VRAM', 'Moving targets and detailed vistas', 'Lower internal resolution may not improve a CPU-limited scene.'),
    ('UpscalingModel', 'Upscaling model', 'GPU / reconstruction', 'Motion and transparent effects', 'Menu presence and saved key are unverified; record it manually if absent.'),
    ('SysSpec_TextureQuality', 'Textures quality', 'VRAM / streaming', 'Detailed interior, then travel', 'Preserve surface detail while leaving VRAM headroom; test streaming stalls as well as FPS.'),
    ('SysSpec_TextureFiltering', 'Texture filtering', 'GPU texture sampling', 'Oblique floors, ship surfaces, distance', 'Check distant clarity; measure the cost rather than assuming a large FPS gain.'),
    ('SysSpec_TextureDetail', 'Texture detail group (internal)', 'GPU / VRAM', 'Close surfaces and weapon detail', 'Internal configuration group, not a separate menu option in the observed 4.10.2 menu. Do not substitute Object Detail for it.'),
    ('SysSpec_TextureGround', 'Ground textures', 'GPU / VRAM / streaming', 'Planet surface', 'Inspect terrain readability and streaming after movement.'),
    ('SysSpec_PlanetTerrainVirtualTextures', 'Planet terrain virtual textures', 'GPU / VRAM / streaming', 'Surface flight and on-foot terrain', 'May affect memory residency and travel stutter; not established by a stationary city sample.'),
    ('SysSpec_ObjectDetail', 'Object detail', 'CPU submission / GPU geometry', 'Dense city and ship interior', 'Inspect silhouettes, LOD transitions, and small target visibility.'),
    ('SysSpec_ObjectViewDistance', 'Object view distance', 'CPU / GPU / RAM', 'Dense exterior and distant targets', 'Do not trade away useful view distance without checking pop-in and target readability.'),
    ('SysSpec_Shading', 'Shader quality', 'GPU shading', 'Reflective materials, skin, lighting', 'Higher settings can improve materials using spare GPU headroom; they do not offload simulation.'),
    ('SysSpec_ShadowMaps', 'Shadow maps', 'GPU / CPU submission / VRAM', 'Sunlit geometry and dark interiors', 'Check moving shadow edges and depth cues; lowering can reduce scene readability.'),
    ('SysSpec_ShadowScreenSpace', 'Screen-space shadows', 'GPU post processing', 'Nearby objects and characters', 'Inspect contact detail, edge artifacts, and dark target separation.'),
    ('SysSpec_Fog', 'Fog', 'GPU volumetrics', 'Foggy exterior', 'An empty space scene cannot measure this setting; preserve intended atmosphere when affordable.'),
    ('SysSpec_GasCloud', 'Gas clouds', 'GPU volumetrics', 'Gas cloud / nebula', 'Scene-dependent; retain effects if cost is acceptable.'),
    ('SysSpec_PlanetVolumetricClouds', 'Planet volumetric clouds', 'GPU / VRAM', 'Cloud-heavy vista and surface flight', 'Startup cloud overrides exist on this machine; verify effective state before comparing.'),
    ('SysSpec_Particles', 'Particles', 'CPU effects / GPU / fill rate', 'Weapons fire, impacts, dust', 'Stationary empty scenes miss effect bursts; preserve combat effect readability.'),
    ('SysSpec_PostProcessing', 'Post processing', 'GPU / presentation', 'Bright-to-dark transition and motion', 'Inspect readability, temporal artifacts, and effects as well as frame time.'),
    ('SysSpec_WaterSim', 'Water simulation', 'GPU compute / geometry', 'Near water, same camera path', 'No conclusion from a scene without water.'),
    ('SysSpec_WaterCaustics', 'Water caustics', 'GPU lighting', 'Water with visible light patterns', 'Aesthetic effect with a scene-dependent cost.'),
    ('SysSpec_VideoComms', 'Video communications', 'CPU / GPU media processing', 'Active video call', 'Test while communications are active; record concurrent Discord use.'),
    ('TerrainTessellation', 'Terrain tessellation', 'GPU geometry', 'Rocky surface and motion', 'Menu presence and saved key are unverified; do not invent a current value.'),
    ('TerrainTessDist', 'Terrain tessellation distance', 'GPU geometry / streaming', 'Surface with distant relief', 'Menu presence and saved key are unverified.'),
    ('FOV', 'Field of view', 'CPU submission / GPU visible scene', 'Same aspect ratio, close and distant targets', 'A wider view can show more scene but make distant targets smaller; preserve player comfort.'),
    ('MotionBlur', 'Motion blur', 'GPU post processing / perceived clarity', 'Camera pan and tracking a target', 'Already zero here; evaluate motion readability independently of FPS.'),
    ('FilmGrain', 'Film grain', 'GPU post processing / perceived clarity', 'Dark gradients and silhouettes', 'Already zero here; a clarity preference, not a promised FPS gain.'),
    ('ChromaticAberration', 'Chromatic aberration', 'GPU post processing / edge clarity', 'High-contrast edges and HUD', 'Already zero here; inspect edge sharpness.'),
    ('Gamma', 'Gamma', 'Display tone response', 'Dark interior plus bright reference', 'Avoid lifting blacks until the image washes out; check both dark visibility and highlight detail.'),
    ('Brightness', 'Brightness', 'Display tone response', 'Dark and bright references', 'Missing saved value means unknown/default, not zero. Keep black and white detail.'),
    ('Contrast', 'Contrast', 'Display tone response', 'Dark clothing against dark background', 'Excess contrast can crush shadow detail and hide targets.'),
    ('Sharpening', 'Sharpening', 'GPU post processing / perceived clarity', 'Moving fine edges and dark targets', 'Observed in the menu at 0; saved key is not verified. Excess sharpening can add halos and amplify noise.'),
    ('AspectModifier', 'Visor and lens aspect modifier', 'Projection / perceived view', 'Cockpit, helmet, and HUD references', 'Observed at 0. Record comfort and geometry distortion separately from performance.'),
    ('HDR', 'HDR', 'Display pipeline / tone mapping', 'HDR-capable display and reference scenes', 'Verify display support and Windows state before drawing a conclusion.'),
    ('HDRMaxBrightness', 'HDR peak brightness', 'Display tone mapping', 'HDR highlight reference', 'Match verified display behavior; do not use an invented brightness specification.'),
    ('HDRReferenceWhite', 'HDR reference white', 'Display tone mapping', 'HDR dark interior and readable HUD', 'Balance UI brightness with scene detail; only meaningful with HDR active.'),
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def config_values(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((';', '#', '--', '//')) or '=' not in line:
            continue
        key, value = line.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def normalized(key):
    return key.lower().replace('_', '')


def parse_cvar_group(text):
    """Describe packaged defaults and overrides; never claim these are live values."""
    sections, section, default_preset = {'default': {}}, 'default', None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((';', '#', '//')):
            continue
        heading = re.fullmatch(r'\[([^]]+)\]', line)
        if heading:
            section = heading[1]
            sections.setdefault(section, {})
        elif '=' in line:
            key, value = (part.strip() for part in line.split('=', 1))
            if not key and section == 'default':
                default_preset = value
            elif key:
                sections[section][key] = value
    defaults = sections.pop('default')
    presets = {}
    levels = set(sections)
    if default_preset is not None:
        levels.add(default_preset)
    for level in sorted(levels):
        presets[level] = {**defaults, **sections.get(level, {})}
    return {'default_preset': default_preset, 'defaults': defaults, 'section_overrides': sections,
            'configured_presets': presets,
            'scope': 'Static packaged configuration; registration, runtime overrides, clamping, and rendering effect are not verified.'}


def snapshot(game=GAME, graphics_path=None):
    game = Path(game)
    values, files, errors = {}, {}, []
    for name, path in [('attributes', game / ATTRIBUTES), ('user_cfg', game / 'USER.cfg'),
                       ('build_manifest', game / 'build_manifest.id')]:
        try:
            raw = path.read_bytes()
            files[name] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
            if name == 'attributes':
                keys = {row[0] for row in CATALOG}
                values = {item.attrib['name']: item.attrib.get('value') for item in ET.fromstring(raw)
                          if item.attrib.get('name') in keys}
            elif name == 'user_cfg':
                cfg = config_values(raw.decode('utf-8-sig'))
            else:
                build = json.loads(raw)['Data']
        except (OSError, ValueError, ET.ParseError, KeyError) as error:
            errors.append(f'{name}: {error}')
    build = locals().get('build', {})
    cfg = locals().get('cfg', {})
    if graphics_path is None and build.get('Branch'):
        matches = sorted(LOCAL.glob(f'*{build["Branch"]}*/GraphicsSettings/GraphicsSettings.json'))
        if len(matches) == 1:
            graphics_path = matches[0]
        elif len(matches) > 1:
            errors.append('Multiple renderer files match this build; select one explicitly.')
    if graphics_path:
        try:
            graphics = read_json(graphics_path)['GraphicsSettings']
            if 'GraphicsRenderer' in graphics:
                values['GraphicsRenderer'] = str(graphics['GraphicsRenderer'])
            files['graphics_settings'] = {'path': str(graphics_path), 'sha256': hashlib.sha256(Path(graphics_path).read_bytes()).hexdigest()}
        except (OSError, ValueError, KeyError) as error:
            errors.append(f'graphics_settings: {error}')
    potential_overrides = []
    by_normalized = {normalized(key): (key, value) for key, value in values.items()}
    for key, value in cfg.items():
        other = by_normalized.get(normalized(key))
        if other and other[1] != value:
            potential_overrides.append({'command': key, 'startup_value': value,
                                        'saved_setting': other[0], 'saved_value': other[1],
                                        'status': 'potential conflict; effective runtime state unverified'})
        elif key.lower().startswith(('r_', 'r.', 'sys_')):
            potential_overrides.append({'command': key, 'startup_value': value,
                                        'status': 'startup command present; verify runtime effect'})
    return {'schema': 1, 'captured_at': utc_now(), 'build': build, 'settings': values,
            'startup_commands': cfg, 'potential_overrides': potential_overrides,
            'files': files, 'errors': errors,
            'scope': 'saved configuration only; raw enum labels and runtime application require menu verification'}


def setting_inventory(saved):
    observed = {}
    path = Path(__file__).parent / 'research/performance/2026-10-20/menu-observations.json'
    if path.is_file():
        try:
            data = read_json(path)
            if str(saved.get('build', {}).get('RequestedP4ChangeNum')) == data.get('build'):
                observed = data.get('labels', {})
        except (OSError, ValueError):
            pass
    return [{'key': key, 'label': label, 'saved_raw': saved['settings'].get(key),
             'observed_menu_label': observed.get(key, {}).get(saved['settings'].get(key)),
             'resource_hypothesis': resource, 'test_scene': scene, 'visual_notes': notes,
             'evidence': 'untested on this hardware/build',
             'menu_verified': False} for key, label, resource, scene, notes in CATALOG]


def packaged_setting_evidence(saved, key, evidence_path=None):
    """Expose build-matched static configuration, without inferring runtime state."""
    path = Path(evidence_path) if evidence_path else (Path(__file__).parent /
            'research/performance/2026-10-20/packaged-graphics/decoded-groups.json')
    if not path.is_file():
        return None
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return None
    build = saved.get('build', {}).get('RequestedP4ChangeNum')
    if not build or str(data.get('build', {}).get('RequestedP4ChangeNum')) != str(build):
        return None
    match = next((group for name, group in data.get('groups', {}).items()
                  if normalized(name) == normalized(key)), None)
    if not match or not {'source', 'sha256', 'scope', 'configured_presets'}.issubset(match):
        return None
    raw = saved.get('settings', {}).get(key)
    return {'source': match['source'], 'sha256': match['sha256'], 'saved_raw': raw,
            'configured_values': match['configured_presets'].get(str(raw)),
            'scope': match['scope']}


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def summarize_frame_csv(path, pid=None):
    """Aggregate one process/swap chain; preserve slow frames instead of hiding them."""
    chains, rejected, seen = {}, 0, set()
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = {name.casefold(): name for name in (reader.fieldnames or [])}
        required = {'processid', 'swapchainaddress', 'msbetweenpresents'}
        if not required.issubset(columns):
            raise ValueError('Expected PresentMon --v1_metrics CSV with ProcessID, SwapChainAddress, MsBetweenPresents.')
        for row in reader:
            try:
                row_pid = int(row[columns['processid']])
                if pid is not None and row_pid != int(pid):
                    continue
                milliseconds = float(row[columns['msbetweenpresents']])
                if not math.isfinite(milliseconds) or milliseconds <= 0:
                    rejected += 1
                    continue
                chain = row[columns['swapchainaddress']]
                stamp = row.get('QPCTime') or row.get('TimeInSeconds')
                identity = (row_pid, chain, stamp)
                if stamp and identity in seen:
                    rejected += 1
                    continue
                if stamp:
                    seen.add(identity)
                chains.setdefault((row_pid, chain), []).append(milliseconds)
            except (ValueError, TypeError, KeyError):
                rejected += 1
    if not chains:
        raise ValueError('No positive finite frame intervals for the selected process.')
    process_ids = {key[0] for key in chains}
    if pid is None and len(process_ids) != 1:
        raise ValueError('CSV contains multiple process IDs; select the intended game PID.')
    key, samples = max(chains.items(), key=lambda pair: len(pair[1]))
    duration = sum(samples) / 1000
    tail_count = max(1, math.ceil(len(samples) * .01))
    tail_mean = statistics.mean(sorted(samples, reverse=True)[:tail_count])
    median = statistics.median(samples)
    warnings = []
    if duration < 30:
        warnings.append('Capture shorter than 30 seconds; tail metrics may be unstable.')
    if len(samples) < 1000:
        warnings.append('Fewer than 1000 intervals; 1% tail estimate has limited samples.')
    return {'source': 'PresentMon application presents', 'pid': key[0], 'swap_chain': key[1],
            'frame_intervals': len(samples), 'duration_seconds': duration,
            'average_fps': len(samples) / duration,
            'median_ms': median, 'p95_ms': percentile(samples, .95), 'p99_ms': percentile(samples, .99),
            'one_percent_low_fps': 1000 / tail_mean,
            'one_percent_low_definition': '1000 / mean of slowest ceil(1% of intervals) in milliseconds',
            'frames_over_50_ms': sum(value > 50 for value in samples),
            'relative_stalls': sum(value > max(50, median * 2.5) for value in samples),
            'rejected_rows': rejected, 'warnings': warnings,
            'limits': 'Application presentation intervals; not server FPS, input latency, or proof of final display cadence. Loading/menu frames must be excluded by capture boundaries.'}


def compare_runs(before, after, changed_setting, baseline_repeat=None):
    """Refuse a setting-effect verdict when known controls differ or evidence is absent."""
    issues = []
    for field in ('scene', 'route', 'background_workload', 'driver_version', 'game_build'):
        if not before.get(field) or not after.get(field):
            issues.append(f'Missing control: {field}')
        elif before[field] != after[field]:
            issues.append(f'Changed control: {field}')
    first = before.get('snapshot', {})
    second = after.get('snapshot', {})
    if first.get('errors') or second.get('errors'):
        issues.append('Settings snapshot has read errors.')
    first_settings, second_settings = first.get('settings', {}), second.get('settings', {})
    differences = {key: [first_settings.get(key), second_settings.get(key)]
                   for key in first_settings.keys() | second_settings.keys()
                   if first_settings.get(key) != second_settings.get(key)}
    if set(differences) != {changed_setting}:
        issues.append('Expected exactly the named setting to differ in saved configuration.')
    if first.get('startup_commands') != second.get('startup_commands'):
        issues.append('Startup commands differ.')
    if ((first.get('potential_overrides') and not before.get('overrides_verified'))
            or (second.get('potential_overrides') and not after.get('overrides_verified'))):
        issues.append('Startup overrides need runtime verification before causal attribution.')
    if not before.get('runtime_verified') or not after.get('runtime_verified'):
        issues.append('Effective runtime settings have not been verified.')
    if before.get('frame_generation') is not False or after.get('frame_generation') is not False:
        issues.append('Frame generation must be explicitly disabled for the initial render-rate comparison.')
    a, b = before.get('frames'), after.get('frames')
    if not a or not b:
        issues.append('Per-frame measurements missing; utilization samples cannot supply 1% lows.')
    result = {'setting': changed_setting, 'differences': differences, 'issues': issues,
              'status': 'confounded' if issues else 'preliminary_pair',
              'note': 'Visual quality and target readability require separate human assessment; no automatic optimal preset is inferred.'}
    if a and b:
        result['average_fps_change_pct'] = (b['average_fps'] / a['average_fps'] - 1) * 100
        result['p99_ms_change_pct'] = (b['p99_ms'] / a['p99_ms'] - 1) * 100
        result['one_percent_low_change_pct'] = (b['one_percent_low_fps'] / a['one_percent_low_fps'] - 1) * 100
    if baseline_repeat:
        repeat_check = compare_runs(after, baseline_repeat, changed_setting)
        repeat_settings = baseline_repeat.get('snapshot', {}).get('settings')
        repeat_frames = baseline_repeat.get('frames')
        if repeat_check['issues'] or repeat_settings != first_settings:
            issues.append('Baseline repeat did not restore the original controls/settings.')
            result['status'] = 'confounded'
        elif a and b and repeat_frames:
            drift = abs(repeat_frames['average_fps'] / a['average_fps'] - 1) * 100
            result['baseline_drift_pct'] = drift
            result['status'] = 'repeated_comparison' if not issues else 'confounded'
            if abs(result['average_fps_change_pct']) <= max(3, drift):
                result['note'] = 'Observed FPS change does not exceed the provisional 3% / baseline-drift screen. Collect additional paired repeats before claiming a benefit.'
    return result
