export const ACTION_LIMIT = 50;

export interface RequestReceipt {
  outcome: string;
  detail?: string;
  at?: number;
}

export interface Player {
  id: string;
  handle: string;
  tags: string[];
  tag?: string;
  manual_tag?: string;
  alert?: boolean;
  is_self?: boolean;
  in_party?: boolean;
  is_friend?: boolean;
  is_org?: boolean;
  on_shard?: boolean;
  relationship?: string;
  source?: string;
  invited_before?: boolean;
  friend_requested_before?: boolean;
  requests?: {
    friend?: RequestReceipt;
    party?: RequestReceipt;
  };
}

export interface QueueRecipientResult {
  id: string;
  handle: string;
  outcome: string;
  detail?: string;
}

export interface InviteQueueState {
  id: string;
  operation?: 'party' | 'friend' | string;
  active: boolean;
  paused: boolean;
  cancelling?: boolean;
  state: string;
  sent: number;
  skipped: number;
  remaining: number;
  total: number;
  next_in_seconds?: number;
  current_handle?: string;
  results?: QueueRecipientResult[];
}

export interface BuyerMatchOffer {
  id?: string;
  price: number;
  unit: string;
  location: string;
  renewed?: number;
  url?: string;
}

export interface BuyerWatch {
  id: string;
  item_id?: number;
  name: string;
  quality: number;
  minimum_price: number;
  unit?: string;
  enabled: boolean;
  checked_at?: number;
  error?: string;
  matches?: BuyerMatchOffer[];
}

export interface MarketCatalogItem {
  id: number;
  name: string;
}

export interface CompanionNotice {
  id?: string;
  title: string;
  detail: string;
  at: number;
  url?: string;
}

export interface HomeRecapBlueprint {
  name: string;
}

export interface HomeRecapReputation {
  faction: string;
  delta: number;
  scope?: string;
  before?: number;
  after?: number;
  standing_changed?: boolean;
}

export interface HomeSessionRecap {
  contracts_completed?: number;
  rep_baseline_at?: number;
  rep_checked_at?: number;
  blueprints?: HomeRecapBlueprint[];
  reputation?: HomeRecapReputation[];
}

export interface HomeOverviewState {
  identity?: string;
  connected?: boolean;
  current?: HomeSessionRecap;
  previous?: HomeSessionRecap;
  refinery_notice?: string;
  synthstrings?: {
    title?: string;
    patch_label?: string;
    status_label?: string;
    status_kind?: string;
    summary?: string;
    at?: number;
  };
}

export interface DaylightSyncState {
  state: 'idle' | 'checking' | 'ok' | 'offline';
  at?: number;
  message?: string;
}

export interface DaylightCalibrationEntry {
  phase_offset: number;
  quality: string;
  calibrated: boolean;
}

export interface DaylightNotice {
  id?: string;
  ok: boolean;
  message: string;
}

export interface DaylightState {
  kind?: string;
  schema?: number;
  revision?: number;
  written_at?: number;
  owner_pid?: number;
  catalogue?: {
    schema?: number;
    source?: string;
    signature?: string;
    checked_at?: number;
    bodies?: import('./daylight_math').BodyRecord[];
    sites?: import('./daylight_math').SiteRecord[];
  };
  calibration?: Record<string, DaylightCalibrationEntry>;
  preferences?: {
    system?: string;
    body?: string;
    site?: string;
  };
  build?: {
    available?: boolean;
    patch?: string;
  };
  sync?: DaylightSyncState;
  notice?: DaylightNotice;
}

export interface FleetShipEntry {
  name: string;
  mfg: string;
  color?: string;
  sorties: number;
  seconds: number;
  jumps: number;
  contracts: number;
  losses: number;
  pct: number;
}

export interface FlightSortieEntry {
  ship: string;
  mfg: string;
  color?: string;
  duration_s: number;
  jumps: number;
  contracts: number;
  destination?: string;
  incident?: string;
  reason?: string;
  time: string;
}

export interface FlightState {
  state?: 'ON_FOOT' | 'BOARDED' | 'IN_FLIGHT' | string;
  active_ship?: string;
  active_mfg?: string;
  active_color?: string;
  active_helm_s?: number;
  active_boarded_s?: number;
  active_jumps?: number;
  active_contracts?: number;
  active_route?: string;
  jurisdiction?: string;
  monitored?: boolean | null;
  entitlements?: number;
  total_sorties?: number;
  total_helm_s?: number;
  total_jumps?: number;
  total_contracts?: number;
  total_losses?: number;
  fleet?: FleetShipEntry[];
  recent?: FlightSortieEntry[];
}

export interface PiracyPullEntry {
  id: string;
  at: number;
  target: string;
  lane: string;
  outcome: 'catch' | 'escaped' | 'dry' | 'combat' | string;
  value_uec: number;
  notes?: string;
}

export interface PiracyWatchState {
  waiting_s?: number;
  waiting_active?: boolean;
  source?: string;
  status?: string;
  timer_note?: string;
  pulls?: PiracyPullEntry[];
  pull_stats?: {
    total: number;
    catches: number;
    hit_rate: number;
    total_loot_uec: number;
  };
  flight?: FlightState;
}

export interface PiracySnapshotPayload {
  flight?: FlightState;
  piracy_watch?: PiracyWatchState;
  session_token?: string;
  server_joined?: boolean;
  account_handle?: string;
  game_running?: boolean;
}

export interface MissionAnalyticsFaction {
  name: string;
  auec: number;
  missions: number;
  rep_net: number;
  avg_per_mission: number | null;
  standing?: string;
  next_standing?: string | null;
  points_to_next?: number;
  rep_progress_pct?: number;
  rep_score?: number;
  scope?: string;
  is_max_rank?: boolean;
}

export interface MissionAnalyticsPromotion {
  faction: string;
  rank: string;
  threshold?: number;
  previous_rank?: string | null;
  scope: string;
  scope_display?: string;
  delta?: number;
  at: number;
}

export interface MissionAnalyticsState {
  totals?: {
    gains: number;
    losses: number;
    net: number;
    attributed: number;
    unattributed_gain: number;
    missions_completed: number;
  };
  factions?: MissionAnalyticsFaction[];
  categories?: { key: string; label: string; gain: number; loss: number }[];
  daily?: { day: string; gain: number; loss: number; net: number }[];
  sessions?: { id: string; started_at?: number; ended_at?: number | null; net: number | null; completed: number }[];
  top_missions?: { title: string; faction: string; auec: number; at: number }[];
  balance_history?: { at: number; auec: number }[];
  promotions?: MissionAnalyticsPromotion[];
  note?: string;
}

export interface MissionLogEntry {
  id: string;
  at: number;
  session?: string;
  cells: string[];
  detail: string;
  change_id?: string;
  is_wallet?: boolean;
  category?: string;
  is_promotion?: boolean;
  promotion?: { rank: string; threshold?: number; scope: string };
}

export interface MissionLogSession {
  id: string;
  started_at?: number;
  ended_at?: number | null;
  completed?: number;
  failed?: number;
  abandoned?: number;
  active?: number;
  wallet?: { currency: string; delta: number | null }[];
}

export interface MissionLogState {
  columns?: [string, number][];
  entries?: MissionLogEntry[];
  display_count?: number;
  display_offset?: number;
  display_limit?: number;
  mode?: string;
  direction?: string;
  sessions?: MissionLogSession[];
  current_session?: string;
  recording?: boolean;
  error?: string;
  wallet_error?: string;
  note?: string;
  note_until?: number;
  analytics?: MissionAnalyticsState;
  written_at?: number;
  count?: number;
}

export interface PeopleSnapshot {
  revision: number;
  owner_pid?: number;
  written_at?: number;
  session: string;
  session_token?: string;
  mode?: 'people' | 'buyer_alerts' | 'home' | 'settings' | 'daylight' | 'hud_piracy' | 'mission_log';
  players: Player[];
  rows?: Player[];
  action_people?: Player[];
  friend_people?: Player[];
  search?: Player[];
  search_query?: string;
  search_busy?: boolean;
  tags?: Record<string, { label?: string; handle?: string; alert?: boolean; is_org?: boolean }>;
  tag_options?: string[];
  action_limit?: number;
  roster_at?: number;
  roster_loading?: boolean;
  roster_error?: string;
  friends_known?: boolean;
  friends_at?: number;
  friend_names_error?: string;
  party_known?: boolean;
  social_busy?: boolean;
  status?: string;
  invite_queue?: InviteQueueState;
  batch_results?: QueueRecipientResult[];
  watches?: BuyerWatch[];
  notifications?: CompanionNotice[];
  market_items?: MarketCatalogItem[];
  home?: HomeOverviewState;
  daylight?: DaylightState;
  piracy?: PiracySnapshotPayload;
  mission?: MissionLogState;
}

export type DesktopCommandAction =
  | 'search'
  | 'refresh_people'
  | 'refresh_market'
  | 'stage_people'
  | 'unstage_people'
  | 'clear_actions'
  | 'stage_tag'
  | 'tag'
  | 'tag_many'
  | 'friend'
  | 'friend_many'
  | 'party'
  | 'party_many'
  | 'pause_invites'
  | 'resume_invites'
  | 'cancel_invites'
  | 'add_watch'
  | 'toggle_watch'
  | 'remove_watch'
  | 'dismiss_notices'
  | 'open_uex_ad'
  | 'strings_settings'
  | 'strings_details'
  | 'daylight_preferences'
  | 'daylight_observe'
  | 'daylight_refresh'
  | 'daylight_copy_forecast'
  | 'piracy_toggle_wait'
  | 'piracy_reset_wait'
  | 'piracy_log_pull'
  | 'piracy_delete_pull'
  | 'mission_view'
  | 'mission_classify'
  | 'mission_export'
  | 'navigate';

export interface DesktopCommand {
  action: DesktopCommandAction;
  query?: string;
  text?: string;
  player_id?: string;
  player_ids?: string[];
  label?: string;
  alert?: boolean;
  clear_tags?: boolean;
  scope?: 'shard' | 'friends';
  include_org_affiliate?: boolean;
  from_actions?: boolean;
  confirmed?: boolean;
  resend?: boolean;
  queue_id?: string;
  item_id?: number;
  quality?: number;
  price?: number;
  unit?: string;
  watch_id?: string;
  url?: string;
  target?: string;
  system?: string;
  body?: string;
  site?: string;
  kind?: 'sunrise' | 'sunset';
  observed_at?: number;
  signature?: string;
  lane?: string;
  outcome?: string;
  value_uec?: number;
  notes?: string;
  pull_id?: string;
  mode?: string;
  direction?: string;
  category?: string;
  change_id?: string;
  format?: 'csv' | 'json' | 'html';
  current_session?: boolean;
  offset?: number;
}

export interface DesktopBridge {
  subscribePeople(listener: (snapshot: PeopleSnapshot) => void): () => void;
  stagePlayers(ids: string[]): Promise<void>;
  sendCommand(command: DesktopCommand): Promise<void>;
}

const SOCIAL_ACTIONS = new Set<DesktopCommandAction>([
  'friend',
  'friend_many',
  'party',
  'party_many',
]);

export function validateOutgoingCommand(command: DesktopCommand): void {
  if (SOCIAL_ACTIONS.has(command.action)) {
    if (command.confirmed !== true) {
      throw new Error(`Unconfirmed outgoing social action rejected: ${command.action}`);
    }
    if (command.action === 'friend_many' || command.action === 'party_many') {
      if (!Array.isArray(command.player_ids) || command.player_ids.length === 0) {
        throw new Error('Batch social action requires at least one recipient');
      }
      if (command.player_ids.length > ACTION_LIMIT) {
        throw new Error(`Batch social action exceeds cap of ${ACTION_LIMIT}`);
      }
    }
  }
  if (command.action === 'stage_people' && Array.isArray(command.player_ids)) {
    if (command.player_ids.length > ACTION_LIMIT) {
      throw new Error(`Cannot stage more than ${ACTION_LIMIT} players at once`);
    }
  }
  if (command.action === 'open_uex_ad') {
    const url = command.url ?? '';
    if (!url.startsWith('https://uexcorp.space/marketplace/item/info/') || /[\r\n\t ]/.test(url)) {
      throw new Error('Invalid UEX advertisement URL');
    }
  }
  if (command.action === 'daylight_observe') {
    if (!command.system || !command.body || !command.site || !command.kind || typeof command.observed_at !== 'number') {
      throw new Error('Daylight observation requires system, body, site, kind and observed_at timestamp');
    }
    if (command.kind !== 'sunrise' && command.kind !== 'sunset') {
      throw new Error('Daylight observation kind must be sunrise or sunset');
    }
  }
}

export function normalizePlayer(raw: Partial<Player> & { id: string; handle?: string }): Player {
  const tagText =
    typeof raw.tag === 'string'
      ? raw.tag
      : Array.isArray(raw.tags)
        ? raw.tags.join(', ')
        : '';
  const tags = Array.isArray(raw.tags)
    ? raw.tags
    : tagText
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
  return {
    ...raw,
    id: String(raw.id),
    handle: String(raw.handle ?? raw.id),
    tags,
    tag: tagText,
  };
}

export function normalizeSnapshot(raw: Partial<PeopleSnapshot>): PeopleSnapshot {
  const rawPlayers = raw.players ?? raw.rows ?? [];
  const players = rawPlayers.map((p) => normalizePlayer(p));
  const actionPeople = (raw.action_people ?? []).map((p) => normalizePlayer(p));
  const friendPeople = (raw.friend_people ?? []).map((p) => normalizePlayer(p));
  const searchPeople = (raw.search ?? []).map((p) => normalizePlayer(p));
  const session = raw.session ?? raw.session_token ?? '';
  return {
    ...raw,
    revision: typeof raw.revision === 'number' ? raw.revision : Date.now(),
    session,
    session_token: session,
    players,
    rows: players,
    action_people: actionPeople,
    friend_people: friendPeople,
    search: searchPeople,
    tag_options: raw.tag_options ?? ['Org', 'Friendly', 'Aggressive', 'Trader', 'Friend'],
    action_limit: typeof raw.action_limit === 'number' ? raw.action_limit : ACTION_LIMIT,
    daylight: raw.daylight,
    piracy: raw.piracy,
    mission: raw.mission,
  };
}

/**
 * Deterministic in-memory bridge for tests and offline verification.
 * Never performs network I/O or sends game input.
 */
export class InMemoryDesktopBridge implements DesktopBridge {
  private listeners = new Set<(snapshot: PeopleSnapshot) => void>();
  private snapshot: PeopleSnapshot;
  public readonly commands: DesktopCommand[] = [];

  constructor(initial?: Partial<PeopleSnapshot>) {
    this.snapshot = normalizeSnapshot(
      initial ?? {
        revision: 1,
        session: 'synthetic-session',
        players: [],
        action_people: [],
        friends_known: true,
        party_known: true,
        roster_at: Date.now() / 1000 - 5,
        status: 'Ready',
      },
    );
  }

  public getSnapshot(): PeopleSnapshot {
    return this.snapshot;
  }

  public publish(next: Partial<PeopleSnapshot>): void {
    this.snapshot = normalizeSnapshot({
      ...this.snapshot,
      ...next,
      revision: (this.snapshot.revision ?? 0) + 1,
    });
    for (const listener of this.listeners) {
      listener(this.snapshot);
    }
  }

  public subscribePeople(listener: (snapshot: PeopleSnapshot) => void): () => void {
    this.listeners.add(listener);
    listener(this.snapshot);
    return () => {
      this.listeners.delete(listener);
    };
  }

  public async stagePlayers(ids: string[]): Promise<void> {
    await this.sendCommand({
      action: 'stage_people',
      player_ids: ids.slice(0, ACTION_LIMIT),
    });
  }

  public async sendCommand(command: DesktopCommand): Promise<void> {
    validateOutgoingCommand(command);
    this.commands.push(structuredClone(command));

    const limit = Math.min(ACTION_LIMIT, this.snapshot.action_limit ?? ACTION_LIMIT);
    const allById = new Map<string, Player>();
    for (const list of [
      this.snapshot.players,
      this.snapshot.friend_people ?? [],
      this.snapshot.search ?? [],
      this.snapshot.action_people ?? [],
    ]) {
      for (const p of list) {
        allById.set(p.id, p);
      }
    }

    if (command.action === 'stage_people' && Array.isArray(command.player_ids)) {
      const current = [...(this.snapshot.action_people ?? [])];
      const existingIds = new Set(current.map((p) => p.id));
      for (const id of command.player_ids) {
        if (current.length >= limit) break;
        if (existingIds.has(id)) continue;
        const found = allById.get(id);
        if (found && !found.is_self && (found.on_shard !== false || found.is_friend)) {
          current.push(found);
          existingIds.add(id);
        }
      }
      this.publish({ action_people: current });
    } else if (command.action === 'unstage_people' && Array.isArray(command.player_ids)) {
      const removeSet = new Set(command.player_ids);
      const current = (this.snapshot.action_people ?? []).filter((p) => !removeSet.has(p.id));
      this.publish({ action_people: current });
    } else if (command.action === 'clear_actions') {
      this.publish({ action_people: [] });
    } else if (command.action === 'stage_tag' && command.label) {
      const current = [...(this.snapshot.action_people ?? [])];
      const existingIds = new Set(current.map((p) => p.id));
      const wanted = command.label.trim().toLowerCase();
      for (const p of this.snapshot.players) {
        if (current.length >= limit) break;
        if (p.is_self || existingIds.has(p.id)) continue;
        const pTags = p.tags.map((t) => t.toLowerCase());
        const matches =
          (wanted === 'org' &&
            (p.is_org ||
              pTags.includes('org') ||
              (command.include_org_affiliate && pTags.includes('org affiliate')))) ||
          (wanted === 'friend' && (p.is_friend || pTags.includes('friend'))) ||
          pTags.includes(wanted);
        if (matches) {
          current.push(p);
          existingIds.add(p.id);
        }
      }
      this.publish({ action_people: current });
    } else if (command.action === 'tag' && command.player_id) {
      this.applyTagUpdate([command.player_id], command.label ?? '', Boolean(command.clear_tags), command.alert);
    } else if (command.action === 'tag_many' && Array.isArray(command.player_ids)) {
      this.applyTagUpdate(command.player_ids, command.label ?? '', Boolean(command.clear_tags));
    } else if (command.action === 'daylight_preferences' && command.system && command.body && command.site) {
      const prev = this.snapshot.daylight ?? {};
      this.publish({
        daylight: {
          ...prev,
          preferences: {
            system: command.system,
            body: command.body,
            site: command.site,
          },
        },
      });
    } else if (command.action === 'daylight_observe' && command.body && command.kind) {
      const prev = this.snapshot.daylight ?? {};
      const cal = { ...(prev.calibration ?? {}) };
      cal[command.body] = {
        phase_offset: 0.123,
        quality: 'Local observation · Just now',
        calibrated: true,
      };
      this.publish({
        daylight: {
          ...prev,
          calibration: cal,
          notice: {
            id: 'mock-obs',
            ok: true,
            message: `Observation saved. ${command.body} clock adjusted.`,
          },
        },
      });
    } else if (command.action === 'daylight_refresh') {
      const prev = this.snapshot.daylight ?? {};
      this.publish({
        daylight: {
          ...prev,
          sync: {
            state: 'ok',
            at: Date.now() / 1000,
            message: 'Public catalogue checked · timing calibration is separate',
          },
        },
      });
    } else if (command.action === 'piracy_toggle_wait') {
      const prev = this.snapshot.piracy ?? {};
      const watch = { ...(prev.piracy_watch ?? {}) };
      watch.waiting_active = !watch.waiting_active;
      watch.waiting_s = watch.waiting_s ?? 0;
      this.publish({ piracy: { ...prev, piracy_watch: watch } });
    } else if (command.action === 'piracy_reset_wait') {
      const prev = this.snapshot.piracy ?? {};
      const watch = { ...(prev.piracy_watch ?? {}) };
      watch.waiting_s = 0;
      this.publish({ piracy: { ...prev, piracy_watch: watch } });
    } else if (command.action === 'piracy_log_pull') {
      const prev = this.snapshot.piracy ?? {};
      const watch = { ...(prev.piracy_watch ?? {}) };
      const pulls = [...(watch.pulls ?? [])];
      const nextPull: PiracyPullEntry = {
        id: `pull-${pulls.length + 1}`,
        at: Date.now() / 1000,
        target: command.target ?? 'Unknown Vessel',
        lane: command.lane ?? 'Open Lane',
        outcome: command.outcome ?? 'catch',
        value_uec: command.value_uec ?? 0,
        notes: command.notes ?? '',
      };
      pulls.unshift(nextPull);
      const catches = pulls.filter((p) => p.outcome === 'catch').length;
      const totalLoot = pulls.reduce((acc, p) => acc + (p.value_uec ?? 0), 0);
      watch.pulls = pulls;
      watch.pull_stats = {
        total: pulls.length,
        catches,
        hit_rate: Math.round((catches / pulls.length) * 100),
        total_loot_uec: totalLoot,
      };
      this.publish({ piracy: { ...prev, piracy_watch: watch } });
    } else if (command.action === 'piracy_delete_pull' && command.pull_id) {
      const prev = this.snapshot.piracy ?? {};
      const watch = { ...(prev.piracy_watch ?? {}) };
      const pulls = (watch.pulls ?? []).filter((p) => p.id !== command.pull_id);
      const catches = pulls.filter((p) => p.outcome === 'catch').length;
      const totalLoot = pulls.reduce((acc, p) => acc + (p.value_uec ?? 0), 0);
      watch.pulls = pulls;
      watch.pull_stats = {
        total: pulls.length,
        catches,
        hit_rate: pulls.length > 0 ? Math.round((catches / pulls.length) * 100) : 0,
        total_loot_uec: totalLoot,
      };
      this.publish({ piracy: { ...prev, piracy_watch: watch } });
    }
  }

  private applyTagUpdate(
    targetIds: string[],
    labelText: string,
    clearTags: boolean,
    alertFlag?: boolean,
  ): void {
    const idSet = new Set(targetIds);
    const newTags = clearTags
      ? []
      : labelText
          .split(',')
          .map((t) => t.trim())
          .filter((t) => t.length > 0);
    const updateList = (list: Player[]): Player[] =>
      list.map((p) => {
        if (!idSet.has(p.id)) return p;
        const merged = clearTags ? [] : Array.from(new Set([...newTags]));
        return normalizePlayer({
          ...p,
          tags: merged,
          tag: merged.join(', '),
          manual_tag: merged.join(', '),
          alert: typeof alertFlag === 'boolean' ? alertFlag : p.alert,
        });
      });
    this.publish({
      players: updateList(this.snapshot.players),
      action_people: updateList(this.snapshot.action_people ?? []),
    });
  }
}

declare global {
  interface Window {
    chrome?: {
      webview?: {
        postMessage(message: unknown): void;
        addEventListener(
          type: 'message',
          listener: (event: { data: unknown }) => void,
        ): void;
        removeEventListener(
          type: 'message',
          listener: (event: { data: unknown }) => void,
        ): void;
      };
    };
  }
}

/**
 * Production WebView2 bridge using in-process COM postMessage channel.
 * Requires per-session bridge_token issued by the native C++ host.
 */
export class WebViewDesktopBridge implements DesktopBridge {
  private listeners = new Set<(snapshot: PeopleSnapshot) => void>();
  private snapshot: PeopleSnapshot | null = null;
  private bridgeToken = '';
  private sequence = 0;

  constructor() {
    const wv = typeof window !== 'undefined' ? window.chrome?.webview : undefined;
    if (wv) {
      wv.addEventListener('message', (event) => {
        const payload =
          typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        if (!payload || typeof payload !== 'object') return;
        const record = payload as Record<string, unknown>;
        if (typeof record.bridge_token === 'string' && record.bridge_token.length > 0) {
          this.bridgeToken = record.bridge_token;
        }
        if (record.kind === 'snapshot' && record.state && typeof record.state === 'object') {
          const stateObj = record.state as Partial<PeopleSnapshot>;
          this.snapshot = normalizeSnapshot({
            ...stateObj,
            mode: (record.mode as PeopleSnapshot['mode']) ?? stateObj.mode ?? 'people',
            market_items:
              (record.market_items as MarketCatalogItem[] | undefined) ??
              stateObj.market_items,
            home: (record.home as HomeOverviewState | undefined) ?? stateObj.home,
            daylight: (record.daylight as DaylightState | undefined) ?? stateObj.daylight,
            piracy: (record.piracy as PiracySnapshotPayload | undefined) ?? stateObj.piracy,
            mission: (record.mission as MissionLogState | undefined) ?? stateObj.mission,
          });
          for (const listener of this.listeners) {
            listener(this.snapshot);
          }
        }
      });
      wv.postMessage({ kind: 'ui_ready', at: Date.now() / 1000 });
    }
  }

  public subscribePeople(listener: (snapshot: PeopleSnapshot) => void): () => void {
    this.listeners.add(listener);
    if (this.snapshot) {
      listener(this.snapshot);
    }
    return () => {
      this.listeners.delete(listener);
    };
  }

  public async stagePlayers(ids: string[]): Promise<void> {
    await this.sendCommand({
      action: 'stage_people',
      player_ids: ids.slice(0, ACTION_LIMIT),
    });
  }

  public async sendCommand(command: DesktopCommand): Promise<void> {
    validateOutgoingCommand(command);
    const wv = typeof window !== 'undefined' ? window.chrome?.webview : undefined;
    if (!wv) {
      throw new Error('WebView2 host channel is not available');
    }
    this.sequence += 1;
    wv.postMessage({
      kind: 'command',
      bridge_token: this.bridgeToken,
      client_seq: this.sequence,
      at: Date.now() / 1000,
      command,
    });
  }
}
