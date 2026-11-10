"""Compute a strictly monotonic version and sequence for automatic update-only publishing."""
import argparse
import json
import os
from pathlib import Path
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_updates import config, manifest, request, version_key
from module_distribution import catalog
from tools.package_community import VERSION as BASE_VERSION


def fetch_remote_state(root):
    trust = config(root)
    max_seq = 0
    remote_versions = []
    for url, parser in [
        (trust.get('modules_manifest_url'), catalog),
        (trust.get('manifest_url'), manifest),
        (trust.get('standard_manifest_url'), manifest),
    ]:
        if not url:
            continue
        try:
            with request(url, trust) as response:
                raw = response.read(256 * 1024 + 1)
            data = parser(raw, trust)
            max_seq = max(max_seq, int(data.get('sequence', 0)))
            if data.get('version'):
                remote_versions.append(str(data['version']))
        except Exception:
            continue
    return remote_versions, max_seq


def compute_next(base_version=BASE_VERSION, run_number=None, check_remote=True, root=ROOT):
    run_num = int(run_number if run_number is not None else os.environ.get('GITHUB_RUN_NUMBER', '0') or 0)
    remote_versions, remote_seq = fetch_remote_state(root) if check_remote else ([], 0)
    candidate = f"{base_version}.{run_num}" if run_num > 0 else base_version
    highest_remote = None
    for rv in remote_versions:
        try:
            if highest_remote is None or version_key(rv) > version_key(highest_remote):
                highest_remote = rv
        except ValueError:
            continue
    if highest_remote is not None and version_key(candidate) <= version_key(highest_remote):
        bump = max(run_num, 1)
        while version_key(f"{base_version}.{bump}") <= version_key(highest_remote):
            bump += 1
            if bump > run_num + 10000:
                # If base_version itself is older than highest_remote's major/minor/patch/prerelease,
                # append a monotonic counter directly to highest_remote.
                candidate = f"{highest_remote}.{max(run_num, 1)}"
                break
        else:
            candidate = f"{base_version}.{bump}"
    now_seq = time.time_ns() // 1000000
    sequence = max(now_seq, remote_seq + 1)
    return dict(version=candidate, sequence=sequence, highest_remote_version=highest_remote, highest_remote_sequence=remote_seq)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-version', default=BASE_VERSION)
    parser.add_argument('--run-number', type=int, default=None)
    parser.add_argument('--no-remote', action='store_true')
    args = parser.parse_args()
    result = compute_next(
        base_version=args.base_version,
        run_number=args.run_number,
        check_remote=not args.no_remote,
    )
    gh_env = os.environ.get('GITHUB_ENV')
    if gh_env:
        with Path(gh_env).open('a', encoding='utf-8') as stream:
            stream.write(f"SYNTHSCAN_VERSION={result['version']}\n")
            stream.write(f"SYNTHSCAN_SEQUENCE={result['sequence']}\n")
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
