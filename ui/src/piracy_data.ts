/**
 * Static reference tables and deterministic calculators for Piracy / Flight operations.
 * Contains verified Star Citizen trade corridors, haulers, snare ships, and commodities
 * designed for interdictions in unmonitored or hackable-array space.
 */

export interface PreyShipSpec {
  id: string;
  name: string;
  mfg: string;
  color: string;
  role: string;
  scu: number;
  maxBoxScu: number;
  qtSize: 'S1' | 'S2' | 'S3';
  recommendedCrew: string;
  hullNote: string;
  typicalCargo: string;
}

export interface TradeLanePreset {
  id: string;
  label: string;
  system: 'Stanton' | 'Pyro';
  distanceMkm: number;
  comms: 'Unmonitored' | 'Hackable Array' | 'Monitored';
  note: string;
}

export interface CommodityTier {
  id: string;
  name: string;
  avgPricePerScu: number;
  tag: string;
}

export interface QedShipSpec {
  id: string;
  name: string;
  radiusKm: number;
  hasSnare: boolean;
  note: string;
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

export const PREY_SHIPS: PreyShipSpec[] = [
  {
    id: 'c2',
    name: 'Crusader C2 Hercules',
    mfg: 'Crusader',
    color: '#9ca8ba',
    role: 'Heavy Freighter',
    scu: 696,
    maxBoxScu: 32,
    qtSize: 'S3',
    recommendedCrew: '2–4 Pirates (Distortion + Mantis)',
    hullNote: 'Dual ramp bay makes tractor beam extraction fast via 32 SCU containers.',
    typicalCargo: 'Gold, Beryl, RMC, Recycled Salvage',
  },
  {
    id: 'caterpillar',
    name: 'Drake Caterpillar',
    mfg: 'Drake',
    color: '#c2a649',
    role: 'Modular Hauler',
    scu: 576,
    maxBoxScu: 24,
    qtSize: 'S3',
    recommendedCrew: '2–3 Pirates',
    hullNote: 'Compartmentalized bays slow extraction; bring an SRV or tractor-equipped Cutlass/C1.',
    typicalCargo: 'RMC, Beryl, Scrap, Refined Ore',
  },
  {
    id: 'hull_c',
    name: 'MISC Hull C',
    mfg: 'MISC',
    color: '#ec4899',
    role: 'Bulk Spindle Freighter',
    scu: 4608,
    maxBoxScu: 32,
    qtSize: 'S3',
    recommendedCrew: '3–6 Pirates + Cargo Hauler Escort',
    hullNote: 'External spindle 32 SCU crates drop free immediately on soft-death — fastest mass-loot transfer.',
    typicalCargo: 'Bulk Contract Hauls, Helium, Hydrogen, Titanium',
  },
  {
    id: 'starlancer_max',
    name: 'MISC Starlancer MAX',
    mfg: 'MISC',
    color: '#ec4899',
    role: 'Long-Range Hauler',
    scu: 224,
    maxBoxScu: 32,
    qtSize: 'S2',
    recommendedCrew: '2 Pirates',
    hullNote: 'Belly lift + rear bay; weak rear turret blind spots against nimble interceptors.',
    typicalCargo: 'Commodity Runs, Refinery Loads',
  },
  {
    id: 'taurus',
    name: 'RSI Constellation Taurus',
    mfg: 'RSI',
    color: '#62ccff',
    role: 'Armed Freighter',
    scu: 174,
    maxBoxScu: 32,
    qtSize: 'S2',
    recommendedCrew: '2–3 Pirates',
    hullNote: 'Heavy S5 pilot guns & S3 shield — use distortion or flank from dorsal thruster arcs.',
    typicalCargo: 'Gold, Refined Quantanium, Vaughn/Contraband',
  },
  {
    id: 'corsair',
    name: 'Drake Corsair',
    mfg: 'Drake',
    color: '#c2a649',
    role: 'Explorer / Gunship',
    scu: 72,
    maxBoxScu: 32,
    qtSize: 'S2',
    recommendedCrew: '2 Pirates',
    hullNote: 'High forward alpha; fragile wings hold main maneuvering thrusters — focus wings first.',
    typicalCargo: 'Maze, Slam, ERT Bounty Loot, Quantanium',
  },
  {
    id: 'zeus_cl',
    name: 'RSI Zeus Mk II CL',
    mfg: 'RSI',
    color: '#62ccff',
    role: 'Medium Freighter',
    scu: 128,
    maxBoxScu: 32,
    qtSize: 'S2',
    recommendedCrew: '1–2 Pirates',
    hullNote: 'Built-in cargo tractor turret on dorsal hull; agile solo target.',
    typicalCargo: 'High-Value Mixed Metals, Commodities',
  },
  {
    id: 'raft',
    name: 'Argo RAFT',
    mfg: 'Argo',
    color: '#f97316',
    role: 'Industrial Freighter',
    scu: 96,
    maxBoxScu: 32,
    qtSize: 'S2',
    recommendedCrew: '1–2 Pirates',
    hullNote: 'Carries three external 32 SCU containers — extremely fast transfer once disabled.',
    typicalCargo: 'Refined Refinery Work Orders, Beryl, Gold',
  },
  {
    id: 'msr',
    name: 'Crusader Mercury Star Runner',
    mfg: 'Crusader',
    color: '#9ca8ba',
    role: 'Blockade Runner',
    scu: 114,
    maxBoxScu: 16,
    qtSize: 'S2',
    recommendedCrew: '2 Pirates (Fast Interceptor Req.)',
    hullNote: 'Very high SCM/NAV boost speed — keep dampener inside 4 km or strip main engines.',
    typicalCargo: 'Smuggling Loads, Drugs, High-Margin Ore',
  },
  {
    id: 'cutlass_black',
    name: 'Drake Cutlass Black',
    mfg: 'Drake',
    color: '#c2a649',
    role: 'Multi-Role Hauler',
    scu: 46,
    maxBoxScu: 16,
    qtSize: 'S2',
    recommendedCrew: '1–2 Pirates',
    hullNote: 'Light hull HP; wide sliding side doors make boarding effortless.',
    typicalCargo: 'ROCs, Salvage RMC, Outpost Commodities',
  },
  {
    id: 'hull_a',
    name: 'MISC Hull A',
    mfg: 'MISC',
    color: '#ec4899',
    role: 'Starter Freighter',
    scu: 64,
    maxBoxScu: 16,
    qtSize: 'S1',
    recommendedCrew: '1 Pirate',
    hullNote: 'Slow S1 QT speed gives generous snare window; exposed external spindles.',
    typicalCargo: 'Refined Goods, Small Outpost Arbitrage',
  },
  {
    id: 'reclaimer',
    name: 'Aegis Reclaimer',
    mfg: 'Aegis',
    color: '#3b82f6',
    role: 'Heavy Salvager',
    scu: 420,
    maxBoxScu: 16,
    qtSize: 'S3',
    recommendedCrew: '3–4 Pirates',
    hullNote: 'Tanky S3 shields & hull; often packed with printed 16 SCU RMC/CM crates in salvage hold.',
    typicalCargo: 'RMC, Construction Materials',
  },
];

export const TRADE_LANE_PRESETS: TradeLanePreset[] = [
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

export const COMMODITY_TIERS: CommodityTier[] = [
  { id: 'quantanium', name: 'Quantanium (Refined)', avgPricePerScu: 24500, tag: 'High-Value Ore' },
  { id: 'maze', name: 'Maze (Contraband)', avgPricePerScu: 92000, tag: 'High Risk / Smuggle' },
  { id: 'partillium', name: 'Partillium', avgPricePerScu: 19500, tag: 'Pyro Rare Material' },
  { id: 'rmc', name: 'Recycled Material Composite (RMC)', avgPricePerScu: 14200, tag: 'Salvage Gold' },
  { id: 'gold', name: 'Gold', avgPricePerScu: 6900, tag: 'Blue-Chip Cargo' },
  { id: 'taranite', name: 'Taranite', avgPricePerScu: 9100, tag: 'Refined Ore' },
  { id: 'beryl', name: 'Beryl', avgPricePerScu: 2700, tag: 'Bulk Commodity' },
  { id: 'cm', name: 'Construction Materials', avgPricePerScu: 2100, tag: 'Salvage / Bulk' },
];

export interface SnareGeometryInput {
  laneDistanceMkm: number;
  offsetMkmFromDest: number;
  doglegKm: number;
  targetDriveSpeedKms: number;
  qedRadiusKm: number;
}

export interface SnareGeometryResult {
  snarePosPct: number;
  transitSeconds: number;
  captureWindowSeconds: number;
  driftConeWidthKm: number;
  inRange: boolean;
  dropAdvice: string;
}

export function calculateSnareGeometry(input: SnareGeometryInput): SnareGeometryResult {
  const laneMkm = Math.max(0.2, input.laneDistanceMkm);
  const clampedOffset = Math.min(laneMkm * 0.9, Math.max(0.05, input.offsetMkmFromDest));
  const laneKm = laneMkm * 1_000_000;
  const speed = Math.max(25_000, input.targetDriveSpeedKms);

  // Fractional distance from Origin -> Destination (100% = Dest)
  const snarePosPct = Math.max(5, Math.min(96, ((laneMkm - clampedOffset) / laneMkm) * 100));
  const transitSeconds = Math.round(laneKm / speed);

  // Typical quantum spline dispersion grows away from destination; tighter closer to destination beacon
  const distFromOriginRatio = snarePosPct / 100;
  const baseDispersionKm = Math.min(35, Math.max(1.5, clampedOffset * 1.4));
  const lateralOffsetKm = Math.max(0, input.doglegKm);
  const driftConeWidthKm = Number((baseDispersionKm * (0.4 + 0.6 * (1 - distFromOriginRatio))).toFixed(1));
  const effectiveMissKm = Math.abs(lateralOffsetKm);
  const inRange = effectiveMissKm <= input.qedRadiusKm;

  // Time target stays inside full QED bubble diameter once dropped/decelerating
  const captureWindowSeconds = Number(((input.qedRadiusKm * 2) / 1.4).toFixed(1));

  let dropAdvice = '';
  if (!inRange) {
    dropAdvice = `Lateral offset (${effectiveMissKm.toFixed(1)} km) exceeds ${input.qedRadiusKm} km bubble. Pull closer to center spline.`;
  } else if (clampedOffset > 4) {
    dropAdvice = 'Mid-lane drop: zero planetary Comm Array coverage in deep space, but QT spread widens — anchor closer to destination beacon if missing.';
  } else {
    dropAdvice = `Convergence trap: ${clampedOffset.toFixed(2)} Mkm before destination catches tight arrival trajectories within the ${input.qedRadiusKm} km QED sphere.`;
  }

  return {
    snarePosPct,
    transitSeconds,
    captureWindowSeconds,
    driftConeWidthKm,
    inRange,
    dropAdvice,
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
