"""Generate daylight solver parity fixtures from the Python reference.

The desktop page mirrors daylight.forecast in TypeScript for live updates.
`npm --prefix ui test` compares that mirror against these Python results for
every bundled destination, several arrival times and a calibration offset.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from daylight import Body, Site, forecast, vector  # noqa: E402
import daylight_catalogue as catalogue  # noqa: E402

TIMES = (1762776000.0, 1762798123.5, 1793000000.25)
OFFSETS = (0.0, 0.7)
OUTPUT = ROOT/'ui/test-fixtures/daylight_parity.json'


def main():
    data = catalogue.validate_catalogue(catalogue.read_json(catalogue.BUNDLED))
    bodies = {row['name']: row for row in data['bodies']}
    cases = []
    for index, row in enumerate(data['sites']):
        body = Body.from_record(bodies[row['body']])
        site = Site(row['name'], tuple(vector(row['coordinates_km'])))
        for at in TIMES:
            for offset in OFFSETS if index % 7 == 0 else OFFSETS[:1]:
                result = forecast(body, site, at, offset)
                cases.append(dict(system=row['system'], body=row['body'], site=row['name'], at=at, offset=offset,
                                  daylight=result['daylight'], altitude_degrees=result['altitude_degrees'],
                                  sunrise=result['sunrise'], sunset=result['sunset'],
                                  windows=[list(w) for w in result['windows']],
                                  continuous=result['continuous'], period_seconds=result['period_seconds']))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(dict(signature=data['signature'], bodies=data['bodies'], sites=data['sites'],
                                      cases=cases), separators=(',', ':')), encoding='utf-8')
    print(f'{len(cases)} parity cases written to {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
