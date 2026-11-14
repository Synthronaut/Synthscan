/**
 * Geometric sunlight forecasts in real UTC seconds and body-fixed km.
 *
 * Exact TypeScript mirror of the pure solver in daylight.py so the desktop
 * page can update instantly and live. daylight.py remains the reference and
 * the Python service still owns catalogue validation, refresh and
 * observation calibration. Parity is checked by `npm --prefix ui test`
 * against fixtures generated from daylight.py (tools/daylight_parity.py).
 */

export const EPOCH = 1577836800.0; // 2020-01-01 UTC; community rotation reference
export const TAU = 2 * Math.PI;

export interface BodyRecord {
  name: string;
  system: string;
  radius_km: number;
  period_seconds: number;
  correction_degrees: number;
  center_km: number[];
  quaternion: number[];
  star_km: number[];
  star_radius_km: number;
}

export interface SiteRecord {
  name: string;
  body: string;
  system: string;
  kind?: string;
  note?: string;
  coordinates_km: number[];
}

export interface Body {
  name: string;
  radius: number;
  period: number; // signed real seconds per rotation; zero means stationary
  sunLongitude: number; // radians at EPOCH
  declination: number;
  starRadiusAngle: number;
}

export interface DaylightEvent {
  kind: 'sunrise' | 'sunset';
  at: number;
}

export interface Forecast {
  at: number;
  daylight: boolean;
  altitude_degrees: number;
  sunrise: number | null;
  sunset: number | null;
  events: DaylightEvent[];
  windows: [number, number][];
  period_seconds: number;
  continuous: 'daylight' | 'night' | null;
  /** Display-only extras (not in daylight.py): solar hour angle and half-day angle. */
  hour_angle: number;
  half_day_angle: number | null;
}

/** Python's float modulo (result takes the sign of the divisor). */
function pymod(a: number, b: number): number {
  const r = a % b;
  return r !== 0 && (r < 0) !== (b < 0) ? r + b : r;
}

function finite(value: unknown): number {
  if (typeof value === 'boolean') throw new Error('Expected a finite number');
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error('Expected a finite number');
  return number;
}

export function vector(values: unknown[]): [number, number, number] {
  if (!Array.isArray(values) || values.length !== 3) throw new Error('Expected XYZ coordinates');
  const result = values.map(finite) as [number, number, number];
  if (Math.max(...result.map(Math.abs)) > 1e12) throw new Error('Coordinate out of range');
  return result;
}

export function rotate(quaternion: number[], point: number[]): [number, number, number] {
  if (quaternion.length !== 4) throw new Error('Expected WXYZ quaternion');
  const q = quaternion.map(finite);
  const norm = Math.sqrt(q.reduce((sum, v) => sum + v * v, 0));
  if (norm < 1e-8) throw new Error('Invalid rotation quaternion');
  const [w, x, y, z] = q.map((v) => v / norm);
  const [a, b, c] = vector(point);
  return [
    (1 - 2 * y * y - 2 * z * z) * a + (2 * x * y - 2 * z * w) * b + (2 * x * z + 2 * y * w) * c,
    (2 * x * y + 2 * z * w) * a + (1 - 2 * x * x - 2 * z * z) * b + (2 * y * z - 2 * x * w) * c,
    (2 * x * z - 2 * y * w) * a + (2 * y * z + 2 * x * w) * b + (1 - 2 * x * x - 2 * y * y) * c,
  ];
}

export function bodyFromRecord(row: BodyRecord): Body {
  const center = vector(row.center_km);
  const star = vector(row.star_km);
  const [x, y, z] = rotate(row.quaternion, star.map((s, i) => s - center[i]));
  const distance = Math.sqrt(x * x + y * y + z * z);
  const starRadius = finite(row.star_radius_km);
  if (!(starRadius > 0 && starRadius < distance)) throw new Error('Invalid star radius/distance');
  const body: Body = {
    name: row.name,
    radius: finite(row.radius_km),
    period: finite(row.period_seconds),
    sunLongitude: Math.atan2(y, x) - Math.PI / 2 - (finite(row.correction_degrees) * Math.PI) / 180,
    declination: Math.atan2(z, Math.hypot(x, y)),
    starRadiusAngle: Math.asin(starRadius / distance),
  };
  if (body.radius <= 0 || (body.period && !(Math.abs(body.period) >= 60 && Math.abs(body.period) <= 86400 * 365))) {
    throw new Error('Unsupported body radius or rotation period');
  }
  if (Math.abs(body.declination) > Math.PI / 2 || !(body.starRadiusAngle >= 0 && body.starRadiusAngle < Math.PI / 2)) {
    throw new Error('Invalid star geometry');
  }
  return body;
}

function geometry(body: Body, coordinates: number[]): [number, number, number, number] {
  const [x, y, z] = vector(coordinates);
  const radius = Math.sqrt(x * x + y * y + z * z);
  if (radius === 0) throw new Error('Site cannot be at the body center');
  const latitude = Math.atan2(z, Math.hypot(x, y));
  const longitude = Math.atan2(y, x);
  const dip = radius > body.radius ? Math.acos(Math.min(1.0, body.radius / radius)) : 0.0;
  const threshold = -Math.min(Math.PI / 2, body.starRadiusAngle + dip);
  const a = Math.sin(latitude) * Math.sin(body.declination);
  const b = Math.cos(latitude) * Math.cos(body.declination);
  return [a, b, longitude, threshold];
}

/**
 * At arrival: state, true center altitude, next events and daylight windows.
 * Windows are clipped at arrival; a current daylight window starts at arrival.
 * Times are UTC Unix seconds, never fictional accelerated universe time.
 */
export function forecast(body: Body, coordinates: number[], atValue: number, phaseOffset = 0.0, cycles = 3): Forecast {
  const at = finite(atValue);
  const offset = finite(phaseOffset);
  if (!(cycles >= 1 && cycles <= 8)) throw new Error('Use 1 to 8 forecast cycles');
  const [a, b, longitude, threshold] = geometry(body, coordinates);
  const omega = body.period ? -TAU / body.period : 0.0;
  const hour = omega
    ? body.sunLongitude - longitude + offset + omega * pymod(at - EPOCH, Math.abs(body.period))
    : body.sunLongitude - longitude + offset;
  const sine = Math.max(-1.0, Math.min(1.0, a + b * Math.cos(hour)));
  const altitude = Math.asin(sine);
  let light = altitude >= threshold;
  if (omega && Math.abs(altitude - threshold) < 1e-10) {
    light = a + b * Math.cos(hour + omega * 0.001) >= Math.sin(threshold);
  }
  const horizon = Math.sin(threshold);
  const result: Forecast = {
    at,
    daylight: light,
    altitude_degrees: (altitude * 180) / Math.PI,
    sunrise: null,
    sunset: null,
    events: [],
    windows: [],
    period_seconds: Math.abs(body.period),
    continuous: null,
    hour_angle: hour,
    half_day_angle: null,
  };
  if (!omega || b < 1e-12 || horizon <= a - b || horizon >= a + b) {
    result.continuous = light ? 'daylight' : 'night';
    return result;
  }
  const theta = Math.acos(Math.max(-1.0, Math.min(1.0, (horizon - a) / b)));
  result.half_day_angle = theta;
  const period = Math.abs(body.period);
  const events: DaylightEvent[] = [];
  for (const target of [theta, -theta]) {
    const delta = pymod(omega > 0 ? target - hour : hour - target, TAU);
    let seconds = delta / Math.abs(omega);
    if (seconds < 0.001) seconds += period;
    const kind = -b * Math.sin(target) * omega > 0 ? 'sunrise' : 'sunset';
    for (let cycle = 0; cycle < cycles; cycle += 1) {
      events.push({ kind, at: at + seconds + cycle * period });
    }
  }
  // Python's sort is stable; Array.prototype.sort is stable in ES2019+.
  events.sort((left, right) => left.at - right.at);
  result.events = events;
  for (const event of events) {
    if (result[event.kind] === null) result[event.kind] = event.at;
  }
  let start: number | null = light ? at : null;
  for (const event of events) {
    if (event.kind === 'sunrise') {
      start = event.at;
    } else if (start !== null) {
      result.windows.push([start, event.at]);
      start = null;
    }
  }
  return result;
}
