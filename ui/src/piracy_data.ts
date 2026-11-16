/**
 * Static reference tables and deterministic calculators for Flight / Piracy operations.
 * Contains Star Citizen trade corridors (Stanton, Pyro, Nyx & Wikelo Emporiums),
 * QED interdiction specs, SnarePlan-style coverage geometry, and /showlocation GPS math.
 */

export interface TradeLanePreset {
  id: string;
  label: string;
  system: 'Stanton' | 'Pyro' | 'Nyx';
  distanceMkm: number;
  comms: 'Unmonitored' | 'Hackable Array' | 'Monitored';
  note: string;
}

export interface QedShipSpec {
  id: string;
  name: string;
  radiusKm: number;
  hasSnare: boolean;
  note: string;
}

export interface GpsPoint {
  x: number;
  y: number;
  z: number;
}

export const QED_SHIPS: QedShipSpec[] = [
  {
    id: 'mantis',
    name: 'RSI Mantis (20 km Snare)',
    radiusKm: 20,
    hasSnare: true,
    note: 'Only full Quantum Snare capable of pulling ships out of active Quantum Travel + 20 km dampener.',
  },
  {
    id: 'guardian_qi',
    name: 'Mirai Guardian QI (8.5 km Dampener)',
    radiusKm: 8.5,
    hasSnare: false,
    note: 'Heavy fighter quantum dampener (8.5 km) — prevents targets at POIs/bunkers from spooling away.',
  },
  {
    id: 'cutlass_blue',
    name: 'Drake Cutlass Blue (4 km Dampener)',
    radiusKm: 4,
    hasSnare: false,
    note: 'Close-range 4 km dampener — pair with Mantis or trap targets lifting from surface outposts.',
  },
  {
    id: 'zeus_mr',
    name: 'RSI Zeus Mk II MR (Dampener)',
    radiusKm: 4,
    hasSnare: false,
    note: 'EMP + Quantum Dampener interdiction cruiser for locking down soft-death victims.',
  },
];

export const TRADE_LANE_PRESETS: TradeLanePreset[] = [
  {
    id: 'nyx_levski_pyro_gw',
    label: 'Levski (Delamar) -> Pyro Gateway',
    system: 'Nyx',
    distanceMkm: 12.0,
    comms: 'Unmonitored',
    note: 'Lawless Nyx corridor (~12 Gm). Anchor 0.5–1.5 Mkm short of Pyro Gateway to catch outbound haulers.',
  },
  {
    id: 'nyx_levski_stanton_gw',
    label: 'Levski (Delamar) -> Stanton Gateway',
    system: 'Nyx',
    distanceMkm: 13.0,
    comms: 'Unmonitored',
    note: 'Primary Stanton–Nyx trade spine (~13 Gm, Agricium & gateway freight). Watch for Pyro Gateway doglegs.',
  },
  {
    id: 'nyx_gw_to_gw',
    label: 'Stanton Gateway <-> Pyro Gateway (Nyx Transit)',
    system: 'Nyx',
    distanceMkm: 18.5,
    comms: 'Unmonitored',
    note: 'Direct cross-gateway transit lane through Nyx for multi-system haulers bypassing Levski.',
  },
  {
    id: 'wikelo_hurston_dasi',
    label: 'Hurston / Stanton GW -> Dasi Station (Wikelo)',
    system: 'Stanton',
    distanceMkm: 16.0,
    comms: 'Hackable Array',
    note: 'Wikelo barter runners hauling Carinite, Scrip & loot to Dasi near Hurston. Hack array or snare outside planetary sphere.',
  },
  {
    id: 'wikelo_crusader_selo',
    label: 'Crusader / Yela -> Selo Station (Wikelo)',
    system: 'Stanton',
    distanceMkm: 1.8,
    comms: 'Hackable Array',
    note: 'Short Yela-sphere approach to Selo Station. Disable ST2-55 / Yela Comm Array or stage an 8.5 km dampener outside armistice.',
  },
  {
    id: 'wikelo_microtech_kinga',
    label: 'microTech / Pyro GW -> Kinga Station (Wikelo)',
    system: 'Stanton',
    distanceMkm: 28.0,
    comms: 'Hackable Array',
    note: 'Long inbound Wikelo Emporium approach near microTech. Snare mid-lane outside planetary Comm Array bubbles.',
  },
  {
    id: 'pyro_monox_checkmate',
    label: 'Monox Outposts -> Checkmate Station',
    system: 'Pyro',
    distanceMkm: 18.4,
    comms: 'Unmonitored',
    note: 'Zero comm-array coverage in Pyro. Snare 0.4–1.2 Mkm shy of Checkmate arrival spline.',
  },
  {
    id: 'pyro_bloom_orbituary',
    label: "Bloom (Shepherd's Rest) -> Orbituary",
    system: 'Pyro',
    distanceMkm: 24.8,
    comms: 'Unmonitored',
    note: 'Weapons-free lane with heavy hauler + salvage traffic inbound to Orbituary.',
  },
  {
    id: 'pyro_terminus_ruin',
    label: 'Pyro IV / V -> Terminus (Ruin Station)',
    system: 'Pyro',
    distanceMkm: 41.2,
    comms: 'Unmonitored',
    note: 'Long unmonitored deep-space corridor; wide QT drift cone so anchor within 1.5 Mkm of Ruin.',
  },
  {
    id: 'stanton_daymar_crusader',
    label: 'Daymar (Brio / Shubin) -> Crusader OM-1',
    system: 'Stanton',
    distanceMkm: 0.56,
    comms: 'Hackable Array',
    note: 'Disable ST2-55 / Daymar Comm Array first, or run an 8.5 km dampener trap at Brio Yard.',
  },
  {
    id: 'stanton_hur_l1_lorville',
    label: 'HUR-L1 (Refinery) -> Hurston OM-1',
    system: 'Stanton',
    distanceMkm: 14.2,
    comms: 'Hackable Array',
    note: 'Refinery hauler spine carrying Gold & Quantanium orders; drop Mantis ~800k km from Hurston.',
  },
  {
    id: 'stanton_arccorp_crusader',
    label: 'ArcCorp -> Crusader Direct Spine',
    system: 'Stanton',
    distanceMkm: 42.1,
    comms: 'Monitored',
    note: 'Interdict in deep space mid-lane outside planetary Comm Array bubbles (~2.5 Mkm off planets).',
  },
  {
    id: 'stanton_microtech_hurl2',
    label: 'microTech -> HUR-L2 Deep Corridor',
    system: 'Stanton',
    distanceMkm: 58.6,
    comms: 'Unmonitored',
    note: 'Mid-point deep space sits completely outside planetary Comm Array sensor spheres.',
  },
];

export interface SnareGeometryInput {
  laneDistanceMkm: number;
  offsetMkmFromDest: number;
  doglegKm: number;
  qedRadiusKm: number;
}

export interface SnareGeometryResult {
  snarePosPct: number;
  captureWindowSeconds: number;
  driftConeWidthKm: number;
  driftConeRadiusKm: number;
  coveragePct: number;
  inRange: boolean;
  dropAdvice: string;
}

/**
 * Exact 2D circle-circle overlap ratio: fraction of the QT drift cone cross-section
 * covered by the QED sphere at lateral offset `d`.
 */
function computeConeCoveragePct(qedRadiusKm: number, coneRadiusKm: number, lateralOffsetKm: number): number {
  const r = Math.max(0.1, qedRadiusKm);
  const R = Math.max(0.1, coneRadiusKm);
  const d = Math.abs(lateralOffsetKm);
  const coneArea = Math.PI * R * R;

  if (d >= r + R) return 0;
  if (d + R <= r) return 100;
  if (d + r <= R) return Math.round(((r * r) / (R * R)) * 100);

  const d2 = d * d;
  const r2 = r * r;
  const R2 = R * R;
  const alpha = Math.acos(Math.max(-1, Math.min(1, (d2 + r2 - R2) / (2 * d * r))));
  const beta = Math.acos(Math.max(-1, Math.min(1, (d2 + R2 - r2) / (2 * d * R))));
  const overlap =
    r2 * alpha +
    R2 * beta -
    0.5 * Math.sqrt(Math.max(0, (-d + r + R) * (d + r - R) * (d - r + R) * (d + r + R)));
  return Math.max(0, Math.min(100, Math.round((overlap / coneArea) * 100)));
}

export function calculateSnareGeometry(input: SnareGeometryInput): SnareGeometryResult {
  const laneMkm = Math.max(0.2, input.laneDistanceMkm);
  const clampedOffset = Math.min(laneMkm * 0.9, Math.max(0.05, input.offsetMkmFromDest));

  // Fractional distance from Origin -> Destination (100% = Dest)
  const snarePosPct = Math.max(5, Math.min(96, ((laneMkm - clampedOffset) / laneMkm) * 100));

  // Quantum spline dispersion grows away from destination; tighter closer to destination beacon
  const distFromOriginRatio = snarePosPct / 100;
  const baseDispersionKm = Math.min(35, Math.max(1.5, clampedOffset * 1.4));
  const lateralOffsetKm = Math.max(0, input.doglegKm);
  const driftConeWidthKm = Number((baseDispersionKm * (0.4 + 0.6 * (1 - distFromOriginRatio))).toFixed(1));
  const driftConeRadiusKm = Number(Math.max(0.8, driftConeWidthKm * 0.5).toFixed(1));
  const effectiveMissKm = Math.abs(lateralOffsetKm);
  const inRange = effectiveMissKm <= input.qedRadiusKm;
  const coveragePct = computeConeCoveragePct(input.qedRadiusKm, driftConeRadiusKm, effectiveMissKm);

  // Time target stays inside full QED bubble diameter once dropped/decelerating
  const captureWindowSeconds = Number(((input.qedRadiusKm * 2) / 1.4).toFixed(1));

  let dropAdvice = '';
  if (!inRange) {
    dropAdvice = `Lateral offset (${effectiveMissKm.toFixed(1)} km) exceeds ${input.qedRadiusKm} km bubble. Pull ${(effectiveMissKm - input.qedRadiusKm + 1).toFixed(1)} km closer to center spline.`;
  } else if (coveragePct < 75) {
    dropAdvice = `Partial cone coverage (${coveragePct}%): edge trajectories may slip past. Anchor closer to destination or center up on spline.`;
  } else if (clampedOffset > 4) {
    dropAdvice = `Mid-lane drop (${coveragePct}% cone coverage): outside planetary Comm Array bubbles, but QT spread widens — move closer to destination if targets slip.`;
  } else {
    dropAdvice = `Convergence trap (${coveragePct}% cone coverage): ${clampedOffset.toFixed(2)} Mkm before destination locks tight arrival splines inside your ${input.qedRadiusKm} km QED sphere.`;
  }

  return {
    snarePosPct,
    captureWindowSeconds,
    driftConeWidthKm,
    driftConeRadiusKm,
    coveragePct,
    inRange,
    dropAdvice,
  };
}

/**
 * Parse Star Citizen `/showlocation` clipboard output:
 * - `Coordinates: x:12345.67 y:-89012.34 z:456.78`
 * - `12345.67, -89012.34, 456.78`
 * Values are in meters (Star Citizen global system coordinates).
 */
export function parseShowLocationText(raw: string): GpsPoint | null {
  const text = String(raw ?? '').trim();
  if (!text || text.length > 512) return null;

  const axisMatches = Array.from(
    text.matchAll(/\b([xyz])\s*[:=]\s*([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?(?:[eE][-+]?\d+)?)/gi),
  );
  if (axisMatches.length >= 3) {
    const vals: Partial<GpsPoint> = {};
    for (const m of axisMatches) {
      const axis = m[1].toLowerCase() as 'x' | 'y' | 'z';
      if (vals[axis] !== undefined) continue;
      const num = Number(m[2].replace(/,/g, ''));
      if (!Number.isFinite(num)) return null;
      vals[axis] = num;
    }
    if (vals.x !== undefined && vals.y !== undefined && vals.z !== undefined) {
      return { x: vals.x, y: vals.y, z: vals.z };
    }
  }

  const csvMatch = text.match(
    /^\s*([-+]?\d+(?:\.\d+)?)\s*[,\s]\s*([-+]?\d+(?:\.\d+)?)\s*[,\s]\s*([-+]?\d+(?:\.\d+)?)\s*$/,
  );
  if (csvMatch) {
    const x = Number(csvMatch[1]);
    const y = Number(csvMatch[2]);
    const z = Number(csvMatch[3]);
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
      return { x, y, z };
    }
  }
  return null;
}

export interface GpsInterceptResult {
  laneDistanceMkm: number;
  offsetMkmFromDest: number;
  lateralOffsetKm: number;
  progressPct: number;
  distanceFromDestKm: number;
  inRange: boolean;
  coveragePct: number;
}

export function calculateGpsIntercept(
  origin: GpsPoint,
  dest: GpsPoint,
  ship: GpsPoint,
  qedRadiusKm: number,
): GpsInterceptResult | null {
  const dx = dest.x - origin.x;
  const dy = dest.y - origin.y;
  const dz = dest.z - origin.z;
  const lenSq = dx * dx + dy * dy + dz * dz;
  if (!Number.isFinite(lenSq) || lenSq < 1e6) return null;

  const laneLenM = Math.sqrt(lenSq);
  const sx = ship.x - origin.x;
  const sy = ship.y - origin.y;
  const sz = ship.z - origin.z;

  const tRaw = (sx * dx + sy * dy + sz * dz) / lenSq;
  const tClamped = Math.max(0, Math.min(1, tRaw));
  const projX = origin.x + tClamped * dx;
  const projY = origin.y + tClamped * dy;
  const projZ = origin.z + tClamped * dz;

  const perpM = Math.hypot(ship.x - projX, ship.y - projY, ship.z - projZ);
  const distToDestM = Math.hypot(dest.x - projX, dest.y - projY, dest.z - projZ);

  const laneDistanceMkm = Number((laneLenM / 1_000_000_000).toFixed(2));
  const offsetMkmFromDest = Number((distToDestM / 1_000_000_000).toFixed(2));
  const lateralOffsetKm = Number((perpM / 1_000).toFixed(2));
  const progressPct = Number((tClamped * 100).toFixed(1));
  const distanceFromDestKm = Math.round(distToDestM / 1_000);

  const geom = calculateSnareGeometry({
    laneDistanceMkm: Math.max(0.2, laneDistanceMkm),
    offsetMkmFromDest: Math.max(0.05, offsetMkmFromDest),
    doglegKm: lateralOffsetKm,
    qedRadiusKm,
  });

  return {
    laneDistanceMkm,
    offsetMkmFromDest,
    lateralOffsetKm,
    progressPct,
    distanceFromDestKm,
    inRange: geom.inRange,
    coveragePct: geom.coveragePct,
  };
}

export interface CrewSplitInput {
  totalLootAuec: number;
  crewCount: number;
  snareBonusPct: number;
  fenceFeePct: number;
}

export interface CrewSplitResult {
  netPoolAuec: number;
  fenceFeeAuec: number;
  snareShareAuec: number;
  crewMemberShareAuec: number;
  otherCrewCount: number;
}

export function calculateCrewSplit(input: CrewSplitInput): CrewSplitResult {
  const gross = Math.max(0, Math.round(input.totalLootAuec));
  const crew = Math.max(1, Math.min(16, Math.round(input.crewCount)));
  const fencePct = Math.max(0, Math.min(40, input.fenceFeePct));
  const fenceFeeAuec = Math.round(gross * (fencePct / 100));
  const netPoolAuec = Math.max(0, gross - fenceFeeAuec);

  if (crew === 1) {
    return {
      netPoolAuec,
      fenceFeeAuec,
      snareShareAuec: netPoolAuec,
      crewMemberShareAuec: netPoolAuec,
      otherCrewCount: 0,
    };
  }

  const bonusPct = Math.max(0, Math.min(40, input.snareBonusPct));
  const bonusAmount = Math.round(netPoolAuec * (bonusPct / 100));
  const evenPool = Math.max(0, netPoolAuec - bonusAmount);
  const perHead = Math.floor(evenPool / crew);
  const snareShareAuec = perHead + bonusAmount;
  const otherCrewCount = crew - 1;

  return {
    netPoolAuec,
    fenceFeeAuec,
    snareShareAuec,
    crewMemberShareAuec: perHead,
    otherCrewCount,
  };
}

export function formatDurationHms(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

export function formatCompactHours(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  if (s >= 3600) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  }
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}m ${rem}s`;
  }
  return `${s}s`;
}

export function formatAuec(amount: number): string {
  const n = Math.max(0, Math.round(amount));
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(2)}M aUEC`;
  }
  if (n >= 1_000) {
    return `${Math.round(n).toLocaleString('en-US')} aUEC`;
  }
  return `${n} aUEC`;
}
