"""Inspect on-disk reputation strings and local log evidence, without game input.

Does not read loginData, credentials, process memory, or contact account services.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'SynthScanStaticTools'))
from tools.inspect_network_protocol import Image, DEFAULT_EXE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-logs', action='store_true', help='Reuse the previous local-log inventory')
    args = parser.parse_args()
    output = ROOT / 'research/reputation_12913470'
    image = Image(DEFAULT_EXE)
    terms = re.compile(rb'reputation|standingProgress|standingValue|standingPoints', re.I)
    strings = []
    for match in re.finditer(rb'[\x20-\x7e]{5,1200}\x00', image.data):
        value = match[0][:-1]
        if terms.search(value):
            strings.append(dict(address=hex(image.base + image.pe.get_rva_from_offset(match.start())),
                                text=value.decode('ascii')))
    targets = {int(s['address'], 16) for s in strings if any(t in s['text'].lower() for t in
               ('standingprogress', 'reputationvalue', 'reputationamount', 'reputationreplic',
                'reputationscope', 'reputationreward', 'reputationsystem::', 'reputationmanager::',
                'getreputation', 'reputationservice', 'reputationupdated', 'reputationchanged',
                'reputation.get', 'reputation.dumpcache', 'reputation.debuglevel',
                'reputation cache', 'reputation get debug', 'updatereputationcache',
                'getplayerreputation', 'logging for reputation',
                'received reputation update from push', 'reputation getscorehistory success'))}
    print(f'Found {len(strings)} static strings; resolving {len(targets)} reference targets.', flush=True)
    refs = image.references(targets)
    live = Path(DEFAULT_EXE).parents[1]
    logs = [live / 'Game.log']
    for directory in ('logbackups', 'logs', 'debuglogs'):
        logs.extend(sorted((live / directory).rglob('*.log')))
    log_inventory = []
    if args.skip_logs:
        log_inventory = json.loads((output / 'source_candidates.json').read_text(encoding='utf-8'))['log_inventory']
        logs = []
    for path in logs:
        try:
            matches = []
            count = 0
            with path.open(encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    if re.search(r'reputation|standingProgress', line, re.I):
                        count += 1
                        # Save only event/function names and numeric field names, not raw identifiers.
                        events = re.findall(r'<([A-Za-z_][\w: ]{2,100})>', line)
                        fields = re.findall(r'\b((?:current|new|old|total)?(?:reputation|standing|amount|scope)[\w]*)\s*[:=]\s*(-?\d+(?:\.\d+)?)', line, re.I)
                        if len(matches) < 8:
                            matches.append(dict(events=events, numeric_fields=fields))
            log_inventory.append(dict(path=str(path.relative_to(live)), bytes=path.stat().st_size,
                                      matching_lines=count, examples=matches))
        except OSError as error:
            log_inventory.append(dict(path=str(path.relative_to(live)), error=str(error)))
    report = dict(scope='On-disk static evidence and existing local logs only; no runtime provider established.',
                  exe_sha256=hashlib.sha256(image.data).hexdigest(), strings=strings, references=refs,
                  log_inventory=log_inventory)
    (output / 'source_candidates.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(strings=len(strings), references=len(refs), logs=len(log_inventory),
                          log_matching_lines=sum(x.get('matching_lines', 0) for x in log_inventory))))


if __name__ == '__main__':
    main()
