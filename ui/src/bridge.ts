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

export interface DirectoryItemData {
  id: string;
  name: string;
  kind?: string;
  category?: string;
  size?: number | string;
  grade?: string;
  manufacturer?: string;
  price_buy?: number;
  price_sell?: number;
  location?: string;
  stock?: number;
}

export interface BlueprintSlotData {
  slot_name: string;
  material_name: string;
  scu: number;
  units: number;
  min_quality: number;
}

export interface BlueprintDefinitionData {
  id: number;
  name: string;
  type: string;
  grade: string;
  size: number;
  item_class: number;
  seconds: number;
  known_from_start: boolean;
  missions: number;
  slots: BlueprintSlotData[];
}

export interface MiningLocationData {
  mineral: string;
  family: 'Ship' | 'ROC' | 'FPS' | string;
  location: string;
  system: string;
  kind: string;
  note: string;
  chance: number;
}

export interface RefineryLocationData {
  name: string;
  system: string;
  profile: number;
}

export interface RefiningMethodData {
  key: string;
  name: string;
  rating: string;
  yield: number;
  time: number;
  cost: number;
}

export interface DaylightSiteData {
  name: string;
  coordinates: [number, number, number];
}

export interface DaylightBodyData {
  name: string;
  radius_km: number;
  period_seconds: number;
  quaternion: [number, number, number, number];
  center_km: [number, number, number];
  star_km: [number, number, number];
  star_radius_km: number;
  correction_degrees: number;
  sites: DaylightSiteData[];
}

export interface DaylightCatalogueData {
  epoch?: number;
  systems?: Record<string, { bodies: DaylightBodyData[] }>;
}

export interface RefineryOrderPartData {
  material: string;
  quality: number;
  yield: number;
  quantity: number;
}

export interface RefineryOrderData {
  order_id: string | number;
  number: number;
  station: string;
  method: string;
  cost: number;
  placed: number;
  due: number;
  completed: number;
  collected: number;
  parts: RefineryOrderPartData[];
}

export interface MissionRecordData {
  id: string;
  title: string;
  category: string;
  system: string;
  payout: number;
  accepted_at?: number;
  completed_at?: number;
  status: 'active' | 'completed' | 'abandoned' | 'failed' | string;
  reputation_delta?: number;
}

export interface WalletChangeData {
  id: string;
  amount: number;
  at: number;
  category: string;
  note?: string;
  balance_after?: number;
}

export interface MissionStatsData {
  total_completed: number;
  total_earned: number;
  current_balance: number;
}

export interface ServerRecordData {
  shard_id: string;
  region: string;
  first_seen: number;
  last_seen: number;
  visit_count: number;
  cooldown_until?: number;
  custom_name?: string;
  notes?: string;
}

export interface ServerStatsData {
  total_shards: number;
  current_shard?: string;
  region?: string;
}

export interface DiaryEntryData {
  id: string;
  system: string;
  body: string;
  method: string;
  ship: string;
  timestamp: number;
  ores: { name: string; scu: number; percent?: number; value_uec?: number }[];
  total_value: number;
  notes?: string;
}

export interface NavBookmarkData {
  id: string;
  name: string;
  body: string;
  role: string;
  coordinates?: [number, number, number];
  stand_off_m?: number;
}

export interface ExecutiveHangarState {
  available?: boolean;
  counts?: Record<string, number>;
  set_counts?: Record<string, number>;
  revision?: number;
  timer_seconds?: number;
  ships?: { name: string; bay: string; ready: boolean; recall_seconds?: number }[];
}

export interface PiracyState {
  wait_active?: boolean;
  wait_seconds?: number;
  snare_alerts?: boolean;
  interdictions?: { target: string; ship: string; cargo_scu?: number; value?: number; at: number }[];
}

export interface DaylightState {
  selected_system?: string;
  selected_body?: string;
  selected_site?: string;
}

export interface AcceptanceSettingsData {
  enabled?: boolean;
  party_enabled?: boolean;
  friend_enabled?: boolean;
  hide_global_chat?: boolean;
}

export interface DesktopSettingsData {
  open_with_launcher?: boolean;
  scan_on_launch?: boolean;
  show_hud?: boolean;
  session_strip?: boolean;
  snare_alerts?: boolean;
  hotkeys_enabled?: boolean;
  game_only_hotkeys?: boolean;
  toggle_key?: string;
  toggle_mods?: number;
  cycle_key?: string;
  cycle_mods?: number;
  privacy_paused?: boolean;
  pause_unfocused?: boolean;
  account_access?: boolean;
  fps_granted?: boolean;
  network_granted?: boolean;
}

export interface DesktopCatalog {
  revision: number;
  directory_rows?: DirectoryItemData[];
  blueprints?: BlueprintDefinitionData[];
  blueprint_types?: string[];
  blueprint_materials?: string[];
  blueprint_slots?: string[];
  mining_locations?: MiningLocationData[];
  refineries?: RefineryLocationData[];
  refinery_materials?: string[];
  refinery_yields?: number[][];
  refining_methods?: RefiningMethodData[];
  daylight?: DaylightCatalogueData;
  available_actions?: Record<string, boolean>;
}

export interface DesktopState {
  active_page?: string;
  game_running?: boolean;
  game_focused?: boolean;
  capture_status?: 'reading' | 'idle' | 'paused';
  hud_active?: {
    mining?: boolean;
    finder?: boolean;
    missions?: boolean;
    hangars?: boolean;
  };
  server?: {
    shard_id?: string;
    region?: string;
    display?: string;
    history_count?: number;
    last_location?: string;
    notes?: string;
  };
  executive_hangar?: ExecutiveHangarState;
  refinery?: {
    orders?: RefineryOrderData[];
    collections?: RefineryOrderData[];
  };
  blueprints?: {
    owned?: string[];
    note?: string;
  };
  mission_log?: {
    missions?: MissionRecordData[];
    wallet_changes?: WalletChangeData[];
    stats?: MissionStatsData;
  };
  servers?: {
    entries?: ServerRecordData[];
    stats?: ServerStatsData;
  };
  diary?: {
    entries?: DiaryEntryData[];
    auto_log?: boolean;
  };
  navigation?: {
    bookmarks?: NavBookmarkData[];
    active_target?: string;
  };
  piracy?: PiracyState;
  daylight?: DaylightState;
  acceptance?: AcceptanceSettingsData;
  settings?: DesktopSettingsData;
}

export interface PeopleSnapshot {
  revision: number;
  owner_pid?: number;
  written_at?: number;
  session: string;
  session_token?: string;
  mode?:
    | 'people'
    | 'buyer_alerts'
    | 'home'
    | 'directory'
    | 'mission_log'
    | 'servers'
    | 'blueprints'
    | 'planner'
    | 'diary'
    | 'refinery'
    | 'executive_hangar'
    | 'hud_piracy'
    | 'daylight'
    | 'acceptance'
    | 'settings';
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
  catalog?: DesktopCatalog;
  desktop?: DesktopState;
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
  | 'import_org'
  | 'add_watch'
  | 'toggle_watch'
  | 'remove_watch'
  | 'dismiss_notices'
  | 'open_uex_ad'
  | 'navigate'
  | 'hud_mode'
  | 'open_dialog'
  | 'dismiss_refinery'
  | 'directory_select'
  | 'toggle_favorite'
  | 'mission_view'
  | 'classify_wallet'
  | 'mission_export'
  | 'session_view'
  | 'session_note'
  | 'shard_name'
  | 'shard_cooldown'
  | 'session_export'
  | 'toggle_blueprint_owned'
  | 'plan_mining'
  | 'diary_view'
  | 'diary_save'
  | 'diary_delete'
  | 'diary_merge'
  | 'diary_share'
  | 'diary_auto_log'
  | 'nav_select'
  | 'nav_arm'
  | 'nav_cancel'
  | 'nav_delete'
  | 'nav_export'
  | 'nav_import'
  | 'refinery_collected'
  | 'hangar_action'
  | 'piracy_action'
  | 'daylight_prefs'
  | 'save_acceptance'
  | 'save_settings'
  | 'save_hotkeys'
  | 'save_privacy'
  | 'helper_permission';

export interface DesktopCommand {
  action: DesktopCommandAction;
  symbol?: string;
  tag_label?: string;
  query?: string;
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
  row_id?: string;
  mode?: string;
  outcome?: string;
  direction?: string;
  category?: string;
  current_session?: boolean;
  offset?: number;
  change_id?: string;
  format?: string;
  region?: string;
  date_from?: string;
  date_to?: string;
  session_id?: string;
  text?: string;
  name?: string;
  minutes?: number;
  blueprint_index?: number;
  targets?: string[];
  family?: string;
  system?: string;
  body?: string;
  site?: string;
  entry_id?: string;
  entry_ids?: string[];
  options?: Record<string, unknown>;
  entry?: Record<string, unknown>;
  auto_log?: boolean;
  bookmark_id?: string;
  body_id?: string;
  role?: string;
  stand_off_m?: number;
  order_index?: number;
  sub_action?: string;
  counts?: Record<string, number>;
  revision?: number;
  enabled?: boolean;
  party_enabled?: boolean;
  friend_enabled?: boolean;
  hide_global_chat?: boolean;
  open_with_launcher?: boolean;
  scan_on_launch?: boolean;
  show_hud?: boolean;
  session_strip?: boolean;
  snare_alerts?: boolean;
  game_only?: boolean;
  toggle_key?: string;
  toggle_mods?: number;
  cycle_key?: string;
  cycle_mods?: number;
  paused?: boolean;
  pause_unfocused?: boolean;
  account_access?: boolean;
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
            catalog:
              (record.catalog as DesktopCatalog | undefined) ??
              this.snapshot?.catalog ??
              stateObj.catalog,
            desktop:
              (record.desktop as DesktopState | undefined) ??
              stateObj.desktop,
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
