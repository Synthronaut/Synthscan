"""Read GitHub's public release download counters. No usage beacon or identity."""
import argparse
import json
import urllib.request


def report(repository='Synthronaut/Synthscan'):
    releases=[];page=1
    while True:
        request=urllib.request.Request(f'https://api.github.com/repos/{repository}/releases?per_page=100&page={page}',headers={'User-Agent':'SynthScan-Release-Report','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=20) as response:rows=json.load(response)
        releases.extend(rows)
        if len(rows)<100:break
        page+=1
    assets=[]
    for release in releases:
        if release.get('draft'):continue
        for asset in release['assets']:
            name=asset['name'];category='installer' if name.lower().endswith('.exe') else 'archive' if name.lower().endswith('.zip') else 'metadata'
            assets.append(dict(release=release['tag_name'],asset=name,downloads=asset['download_count'],category=category))
    return dict(repository=repository,meaning='Asset downloads, not unique users or active players. Re-downloads and automated requests can be counted.',
        installer_downloads=sum(r['downloads'] for r in assets if r['category']=='installer'),
        archive_downloads=sum(r['downloads'] for r in assets if r['category']=='archive'),assets=assets)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repository',default='Synthronaut/Synthscan');args=parser.parse_args()
    print(json.dumps(report(args.repository),indent=2))
