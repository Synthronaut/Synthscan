"""Extract the pinned Microsoft x64 CRT for app-local use; never installs it."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('concrt140', 'msvcp140', 'msvcp140_1', 'msvcp140_2',
         'msvcp140_atomic_wait', 'msvcp140_codecvt_ids', 'vcamp140',
         'vccorlib140', 'vcomp140', 'vcruntime140', 'vcruntime140_1',
         'vcruntime140_threads')


def prepare():
    metadata = json.loads((ROOT / 'third_party/build_tools/vc_runtime.json').read_text())
    cache = ROOT / 'third_party/build_tools/vcruntime'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'redist.exe'
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != metadata['sha256']:
        subprocess.run(['curl.exe', '--fail', '--location', '--retry', '3',
                        '--output', str(archive), metadata['url']], check=True)
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != metadata['sha256']:
        raise ValueError('Microsoft runtime archive digest mismatch')
    # Burn bundles carry two ordinary CABs: manifest/UX and attached payloads.
    containers = []
    offset = 0
    while True:
        offset = data.find(b'MSCF', offset)
        if offset < 0:
            break
        if offset + 36 <= len(data):
            size = struct.unpack_from('<I', data, offset + 8)[0]
            if 36 < size <= len(data) - offset and data[offset + 25] == 1:
                cab = cache / ('container%d.cab' % len(containers))
                folder = cab.with_suffix('')
                folder.mkdir(exist_ok=True)
                cab.write_bytes(data[offset:offset + size])
                subprocess.run(['expand.exe', '-F:*', str(cab), str(folder)],
                               check=True, capture_output=True, timeout=60)
                containers.append(folder)
                offset += size
                continue
        offset += 4
    if len(containers) != 2:
        raise ValueError('Unexpected Microsoft runtime bundle layout')
    manifest = ET.parse(containers[0] / '0').getroot()
    payload = next(x for x in manifest.iter()
                   if x.tag.endswith('}Payload') and
                   x.get('FilePath') == r'packages\vcRuntimeMinimum_amd64\cab1.cab')
    cab = cache / 'minimum.cab'
    shutil.copy2(containers[1] / payload.attrib['SourcePath'], cab)
    folder = cache / 'minimum'
    folder.mkdir(exist_ok=True)
    subprocess.run(['expand.exe', '-F:*', str(cab), str(folder)],
                   check=True, capture_output=True, timeout=60)
    output = cache / 'crt'
    output.mkdir(exist_ok=True)
    for name in NAMES:
        source = folder / (name + '.dll_amd64')
        content = source.read_bytes()
        pe = struct.unpack_from('<I', content, 0x3c)[0]
        if content[:2] != b'MZ' or struct.unpack_from('<H', content, pe + 4)[0] != 0x8664:
            raise ValueError('Non-x64 CRT payload: ' + name)
        shutil.copy2(source, output / (name + '.dll'))
    return output


def bundle(destination):
    destination = Path(destination)
    runtime = prepare()
    for target in (destination / 'runtime', destination / 'dist/native'):
        target.mkdir(parents=True, exist_ok=True)
        for name in NAMES:
            shutil.copy2(runtime / (name + '.dll'), target / (name + '.dll'))


if __name__ == '__main__':
    print(prepare())
