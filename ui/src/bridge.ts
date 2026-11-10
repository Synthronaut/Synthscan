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

export interface PeopleSnapshot {
  revision: number;
  owner_pid?: number;
  written_at?: number;
  session: string;
  session_token?: string;
  mode?: 'people' | 'buyer_alerts' | 'home' | 'settings';
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
  | 'navigate';

export interface DesktopCommand {
  action: DesktopCommandAction;
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
