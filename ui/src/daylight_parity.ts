import { bodyFromRecord, forecast, type BodyRecord, type SiteRecord } from './daylight_math';

interface ParityCase {
  system: string;
  body: string;
  site: string;
  at: number;
  offset: number;
  daylight: boolean;
  altitude_degrees: number;
  sunrise: number | null;
  sunset: number | null;
  windows: [number, number][];
  continuous: 'daylight' | 'night' | null;
  period_seconds: number;
}

export interface ParityFixture {
  signature: string;
  bodies: BodyRecord[];
  sites: SiteRecord[];
  cases: ParityCase[];
}

export interface ParityResult {
  daylight_cases: number;
  daylight_mismatches: number;
  daylight_max_time_error_seconds: number;
  daylight_max_altitude_error_degrees: number;
  daylight_first_mismatch?: string;
}

/** Compare the TypeScript solver against results produced by daylight.py. */
export function runDaylightParity(fixture: ParityFixture): ParityResult {
  const bodies = new Map(fixture.bodies.map((row) => [row.name, bodyFromRecord(row)]));
  const sites = new Map(fixture.sites.map((row) => [`${row.system}|${row.body}|${row.name}`, row]));
  let mismatches = 0;
  let maxTime = 0;
  let maxAltitude = 0;
  let first: string | undefined;
  const time = (left: number | null, right: number | null): boolean => {
    if (left === null || right === null) return left === right;
    const error = Math.abs(left - right);
    maxTime = Math.max(maxTime, error);
    return error < 1e-3;
  };
  for (const item of fixture.cases) {
    const site = sites.get(`${item.system}|${item.body}|${item.site}`);
    const body = bodies.get(item.body);
    let ok = Boolean(site && body);
    if (site && body) {
      const result = forecast(body, site.coordinates_km, item.at, item.offset);
      const altitude = Math.abs(result.altitude_degrees - item.altitude_degrees);
      maxAltitude = Math.max(maxAltitude, altitude);
      ok =
        result.daylight === item.daylight &&
        altitude < 1e-7 &&
        result.continuous === item.continuous &&
        result.period_seconds === item.period_seconds &&
        time(result.sunrise, item.sunrise) &&
        time(result.sunset, item.sunset) &&
        result.windows.length === item.windows.length &&
        result.windows.every((w, i) => time(w[0], item.windows[i][0]) && time(w[1], item.windows[i][1]));
    }
    if (!ok) {
      mismatches += 1;
      first ??= `${item.system}/${item.body}/${item.site} @ ${item.at} offset ${item.offset}`;
    }
  }
  return {
    daylight_cases: fixture.cases.length,
    daylight_mismatches: mismatches,
    daylight_max_time_error_seconds: maxTime,
    daylight_max_altitude_error_degrees: maxAltitude,
    ...(first ? { daylight_first_mismatch: first } : {}),
  };
}
