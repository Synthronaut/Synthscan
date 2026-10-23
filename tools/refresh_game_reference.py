"""Rebuild reference catalogs from the installed game, without launching it.

Uses the locally pinned StarBreaker CLI, limits worker threads/memory, writes
only inside SynthScan, and refuses publication if the game build changes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_records import GameRecords
from tools.export_local_blueprints import export as export_blueprints
from tools.export_local_mining import export as export_mining
from tools.export_game_library import export as export_library
from installation import RELEASE, game_directory, output_root, reference_paths


def run(binary, args, log):
    env = os.environ.copy()
    env.pop('SC_DATA_P4K', None)
    env['RAYON_NUM_THREADS'] = '2'
    started = time.monotonic()
    result = subprocess.run([str(binary), *args, '--mem-cap', '2048'], env=env, text=True,
                             capture_output=True, timeout=600,
                             creationflags=(0x08000000 | 0x00004000) if os.name=='nt' else 0)
    log.append(dict(arguments=args, exit=result.returncode, seconds=round(time.monotonic()-started,2),stderr=result.stderr))
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    print(result.stderr.strip(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=game_directory())
    args = parser.parse_args()
    game = args.game_dir.resolve()
    original = (game/'build_manifest.id').read_bytes()
    manifest = json.loads(original)
    build = manifest['Data']['BuildId']
    if not build or any(c not in '0123456789abcdef-' for c in build):
        raise ValueError('Unrecognized build identity')
    archive = game/'Data.p4k'
    stamp = (archive.stat().st_size, archive.stat().st_mtime_ns)
    binary = ROOT/'third_party/starbreaker/v0.3.2/starbreaker.exe'
    provenance = json.loads(binary.with_name('download_provenance.json').read_text(encoding='utf-8'))
    expected = next(p['sha256'] for p in provenance['files'] if p['name']=='starbreaker.exe')
    if hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise ValueError('StarBreaker binary does not match the verified local release')
    work = reference_paths()['root'] if RELEASE else ROOT/'research/game_reference_cache'/build
    destination = output_root()
    (destination/'data').mkdir(parents=True,exist_ok=True)
    work.mkdir(parents=True,exist_ok=True)
    records, localizations = work/'records', work/'localization'
    log = []
    try:
        filters = ['**/{crafting,mining,resourcetypedatabase,entities/scitem,scitemmanufacturer}/**',
                   '**/{harvestable,entities/mineable,entities/ui}/**',
                   '**/{reputation,factions,missionbroker,missiondata,characternamedata,contracts,reputationvaluesettings,sreputationglobalcontextbbparams,journalentry,lawsystem}/**']
        for pattern in filters:
            run(binary, ['dcb','extract','--p4k',str(archive),'--format','json','--filter',pattern,'-o',str(records)],log)
        run(binary, ['p4k','extract','--p4k',str(archive),'--filter','**/english/global.ini','--max-threads','1','-o',str(localizations)],log)
        artwork = work/'artwork'
        art_filter = r'(?i)^Data[\\/]UI[\\/](Textures[\\/](Vector[\\/]General[\\/](Items|CommonIcons)|EA[\\/]LoadoutIcons)|mobiGlas[\\/]assets[\\/]TIF[\\/]AssetManager|SharedAssets[\\/]CommodityLogos)[\\/].*\.(svg|dds)$'
        run(binary, ['p4k','extract','--p4k',str(archive),'--regex',art_filter,'--max-threads','1','--convert','dds-png','-o',str(artwork)],log)
        global_ini = next(localizations.rglob('global.ini'))
        store = GameRecords(records, global_ini)
        base = json.loads((ROOT/'data/crafting_catalog.json').read_text(encoding='utf-8'))
        recipes = export_blueprints(store,base,manifest)
        mining = export_mining(store,manifest,ROOT/'data/mining_location_labels.csv')
        hashes = {str(p.relative_to(store.root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(store.used)}
        recipes['native_provenance']['record_hashes'] = hashes
        mining['provenance']['record_hashes'] = hashes
        library = export_library(store,artwork,destination,manifest)
        if (game/'build_manifest.id').read_bytes() != original or (archive.stat().st_size,archive.stat().st_mtime_ns) != stamp:
            raise RuntimeError('Game files changed during extraction; existing catalogs preserved')
        if not mining['locations'] or mining['provenance']['failures']:
            raise RuntimeError('Mining references are incomplete; existing catalogs preserved')
        if recipes['native_provenance']['enriched_entries'] < 1:
            raise RuntimeError('No reference recipes could be verified; existing catalogs preserved')
        if library['provenance']['failures'] or library['provenance']['asset_failures'] or not library['entries']:
            raise RuntimeError('Library export incomplete; existing catalogs preserved')
        (work/'source_manifest.json').write_bytes(original)
        (artwork/'source_manifest.json').write_bytes(original)
        # All outputs are fully prepared before active files are replaced.
        for name, data in [('local_game_catalog.json',recipes),('local_mining_catalog.json',mining),('local_game_library.json',library)]:
            prepared = work/name
            prepared.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        for name in ('local_game_catalog.json','local_mining_catalog.json','local_game_library.json'):
            temporary = destination/'data'/(name+'.tmp')
            temporary.write_bytes((work/name).read_bytes())
            os.replace(temporary, destination/'data'/name)
        print(f"Published build {manifest['Data']['RequestedP4ChangeNum']}: {recipes['native_provenance']['enriched_entries']} verified input sets, {len(mining['locations'])} mining presets, {len(library['entries'])} library records. Restart SynthScan to load.")
    finally:
        (work/'refresh_log.json').write_text(json.dumps(log,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
