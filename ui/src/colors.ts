export interface RgbColor {
  r: number;
  g: number;
  b: number;
  css: string;
}

export interface PersonRelationshipFlags {
  is_self?: boolean;
  in_party?: boolean;
  is_friend?: boolean;
}

function makeRgb(r: number, g: number, b: number): RgbColor {
  return { r, g, b, css: `rgb(${r}, ${g}, ${b})` };
}

export const SELF_PURPLE = makeRgb(193, 157, 255);
export const PARTY_BLUE = makeRgb(116, 183, 255);
export const FRIEND_GREEN = makeRgb(121, 225, 158);
export const NEUTRAL_INK = makeRgb(234, 240, 247);

/**
 * Relationship priority: Self (purple) > Party (blue) > Friend (green) > Neutral ink.
 */
export function personColor(person: PersonRelationshipFlags): RgbColor {
  if (person.is_self) return SELF_PURPLE;
  if (person.in_party) return PARTY_BLUE;
  if (person.is_friend) return FRIEND_GREEN;
  return NEUTRAL_INK;
}

const PRESET_TAG_COLORS: Record<string, [number, number, number]> = {
  org: [255, 145, 40],
  'enemy org': [255, 68, 68],
  friend: [45, 225, 122],
  friendly: [166, 231, 190],
  aggressive: [255, 105, 112],
  trader: [75, 207, 232],
  'org affiliate': [231, 204, 80],
  crew: [184, 150, 255],
  buyer: [106, 163, 255],
  avoid: [237, 125, 207],
};

const resolvedTagColors = new Map<string, RgbColor>();
const usedPackedColors = new Set<number>();

for (const [key, [r, g, b]] of Object.entries(PRESET_TAG_COLORS)) {
  resolvedTagColors.set(key, makeRgb(r, g, b));
  usedPackedColors.add((r << 16) | (g << 8) | b);
}

/**
 * Deterministic per-tag color matching SynthCompanion.cpp tagColor().
 * Never reuses an already-assigned color; guarantees "Friend" and "Friendly" stay distinct.
 */
export function tagColor(rawTag: string): RgbColor {
  const key = rawTag.trim().toLowerCase();
  const existing = resolvedTagColors.get(key);
  if (existing) return existing;

  let hash = 2166136261 >>> 0;
  for (let i = 0; i < key.length; i++) {
    hash ^= key.charCodeAt(i);
    hash = Math.imul(hash, 16777619) >>> 0;
  }

  let r = 0;
  let g = 0;
  let b = 0;
  let packed = 0;
  do {
    const hue = (hash % 3600) / 600.0;
    const saturation = 0.5 + (((hash >>> 12) % 25) / 100.0);
    const value = 0.9 + (((hash >>> 20) % 10) / 100.0);
    const chroma = value * saturation;
    const x = chroma * (1 - Math.abs((hue % 2) - 1));
    const m = value - chroma;
    let rf = 0;
    let gf = 0;
    let bf = 0;
    if (hue < 1) {
      rf = chroma;
      gf = x;
    } else if (hue < 2) {
      rf = x;
      gf = chroma;
    } else if (hue < 3) {
      gf = chroma;
      bf = x;
    } else if (hue < 4) {
      gf = x;
      bf = chroma;
    } else if (hue < 5) {
      rf = x;
      bf = chroma;
    } else {
      rf = chroma;
      bf = x;
    }
    r = Math.trunc((rf + m) * 255);
    g = Math.trunc((gf + m) * 255);
    b = Math.trunc((bf + m) * 255);
    packed = (r << 16) | (g << 8) | b;
    hash = (hash + 0x9e3779b9) >>> 0;
  } while (usedPackedColors.has(packed));

  usedPackedColors.add(packed);
  const color = makeRgb(r, g, b);
  resolvedTagColors.set(key, color);
  return color;
}

export function splitTags(value: string | undefined | null): string[] {
  if (!value) return [];
  return value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}
