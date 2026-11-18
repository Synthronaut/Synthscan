import type {
  DesktopBridge,
  KnickAccountItem,
  KnickKnackItem,
  KnickKnacksState,
  KnickShipEntry,
  PeopleSnapshot,
} from './bridge';

export type KnickViewTab = 'spare' | 'account' | 'ships';

export type KnickCategoryFilter =
  | 'all'
  | 'crafted'
  | 'ship_components'
  | 'mining_crafting'
  | 'wikelo'
  | 'comp_boards'
  | 'gear_weapons'
  | 'other';

export type KnickAccountCategoryFilter =
  | 'all'
  | 'ships'
  | 'paints'
  | 'gear_weapons'
  | 'ship_components'
  | 'flair';

export type KnickAccountSourceFilter = 'rsi_hangar' | 'ingame_ltp' | 'all';

export type KnickShipCategoryFilter =
  | 'all'
  | 'ingame_earned'
  | 'pledged'
  | 'unowned'
  | 'dealership'
  | 'wikelo'
  | 'exec_hangar';

export type KnickSortKey = 'qty_desc' | 'name_asc' | 'location_asc' | 'category_asc';

function esc(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatAge(updatedAt?: number): string {
  if (!updatedAt || updatedAt <= 0) return 'Not synced yet';
  const delta = Math.max(0, Math.round(Date.now() / 1000 - updatedAt));
  if (delta < 10) return 'Synced just now';
  if (delta < 60) return `Synced ${delta}s ago`;
  if (delta < 3600) return `Synced ${Math.floor(delta / 60)}m ago`;
  return `Synced ${Math.floor(delta / 3600)}h ago`;
}

function formatSizeGrade(item: {
  size: number | null;
  grade: number | null;
  sub_type: string;
  manufacturer: string;
  is_ship_component?: boolean;
  category?: string;
}): string {
  const parts: string[] = [];
  const showComp = item.is_ship_component || item.category === 'ship_components';
  if (typeof item.size === 'number' && item.size > 0 && showComp) {
    parts.push(`S${item.size}`);
  }
  if (typeof item.grade === 'number' && item.grade > 0 && showComp) {
    const letters = ['', 'A', 'B', 'C', 'D'];
    parts.push(`Grade ${letters[item.grade] ?? item.grade}`);
  }
  if (item.sub_type && item.sub_type !== 'Misc' && item.sub_type !== 'UNDEFINED') {
    parts.push(item.sub_type);
  }
  if (item.manufacturer) {
    parts.push(item.manufacturer);
  }
  return parts.join(' · ');
}

function formatScu(scu: number): string {
  if (scu >= 100) return scu.toFixed(1);
  if (scu >= 10) return scu.toFixed(2);
  if (scu >= 0.01) return scu.toFixed(3);
  return scu.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
}

function rowExpandKey(item: KnickKnackItem): string {
  const ing = (item.crafted_ingredients ?? []).map((x) => `${x.name}:${x.quality}`).join(',');
  return `${item.crc}|${item.location_id}|${item.storage_kind}|${item.container}|${item.is_crafted ? 'c' : 's'}|${ing}`;
}

export function matchesKnickCategory(item: KnickKnackItem, cat: KnickCategoryFilter): boolean {
  if (cat === 'all') return true;
  if (cat === 'crafted') return Boolean(item.is_crafted);
  if (cat === 'wikelo') return item.category === 'wikelo' || Boolean(item.is_wikelo);
  if (cat === 'mining_crafting') return item.category === 'mining_crafting' || Boolean(item.is_crafting);
  if (cat === 'comp_boards') return item.category === 'comp_boards' || Boolean(item.is_comp_board);
  return item.category === cat;
}

export function filterAndSortItems(
  items: KnickKnackItem[],
  opts: {
    query: string;
    category: KnickCategoryFilter;
    locationId: string;
    storageFilter: string;
    sort: KnickSortKey;
  },
): KnickKnackItem[] {
  const q = opts.query.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (!matchesKnickCategory(item, opts.category)) return false;
    if (opts.locationId !== 'all' && item.location_id !== opts.locationId) return false;
    if (opts.storageFilter === 'local' && (item.storage_kind !== 'location' || item.container !== 'Local Storage')) {
      return false;
    }
    if (opts.storageFilter === 'hangar' && item.storage_kind !== 'hangar' && item.container !== 'Persistent Hangar') {
      return false;
    }
    if (opts.storageFilter === 'nested' && !item.container.startsWith('In ')) {
      return false;
    }
    if (q) {
      const hay = `${item.name} ${item.sub_type} ${item.manufacturer} ${item.location_name} ${item.system} ${item.container} ${item.category_label}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (opts.sort === 'name_asc') {
      return a.name.localeCompare(b.name) || b.quantity - a.quantity;
    }
    if (opts.sort === 'location_asc') {
      return a.location_name.localeCompare(b.location_name) || b.quantity - a.quantity || a.name.localeCompare(b.name);
    }
    if (opts.sort === 'category_asc') {
      return a.category_label.localeCompare(b.category_label) || b.quantity - a.quantity || a.name.localeCompare(b.name);
    }
    return b.quantity - a.quantity || a.name.localeCompare(b.name) || a.location_name.localeCompare(b.location_name);
  });

  return filtered;
}

export function filterAndSortAccountItems(
  items: KnickAccountItem[],
  opts: {
    query: string;
    category: KnickAccountCategoryFilter;
    sourceFilter: KnickAccountSourceFilter;
    sort: KnickSortKey;
  },
): KnickAccountItem[] {
  const q = opts.query.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (opts.sourceFilter !== 'all' && item.source_kind !== opts.sourceFilter) return false;
    if (opts.category !== 'all' && item.category !== opts.category) return false;
    if (q) {
      const hay = `${item.name} ${item.sub_type} ${item.manufacturer} ${item.source_label} ${item.status_label} ${item.category_label}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (opts.sort === 'name_asc') {
      return a.name.localeCompare(b.name) || b.quantity - a.quantity;
    }
    if (opts.sort === 'location_asc') {
      return a.source_label.localeCompare(b.source_label) || a.name.localeCompare(b.name);
    }
    if (opts.sort === 'category_asc') {
      return a.category_label.localeCompare(b.category_label) || b.quantity - a.quantity || a.name.localeCompare(b.name);
    }
    return (
      (a.source_kind === b.source_kind ? 0 : a.source_kind === 'rsi_hangar' ? -1 : 1) ||
      b.quantity - a.quantity ||
      a.name.localeCompare(b.name)
    );
  });

  return filtered;
}

export function filterAndSortShips(
  ships: KnickShipEntry[],
  opts: {
    query: string;
    filter: KnickShipCategoryFilter;
    sort: KnickSortKey;
  },
): KnickShipEntry[] {
  const q = opts.query.trim().toLowerCase();
  const filtered = ships.filter((s) => {
    if (opts.filter === 'ingame_earned' && s.ownership !== 'ingame_earned') return false;
    if (opts.filter === 'pledged' && s.ownership !== 'pledged') return false;
    if (opts.filter === 'unowned' && s.owned) return false;
    if (opts.filter === 'dealership' && s.channel !== 'dealership') return false;
    if (opts.filter === 'wikelo' && s.channel !== 'wikelo' && !s.also_wikelo) return false;
    if (opts.filter === 'exec_hangar' && s.channel !== 'exec_hangar') return false;
    if (q) {
      const hay = `${s.name} ${s.company} ${s.role} ${s.ownership_label} ${s.channel_label} ${s.dealer_label} ${s.recipe}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const rank: Record<string, number> = { ingame_earned: 0, pledged: 1, unowned: 2 };
  filtered.sort((a, b) => {
    if (opts.sort === 'name_asc') {
      return a.name.localeCompare(b.name);
    }
    if (opts.sort === 'location_asc') {
      return (a.dealer_label || a.ownership_label).localeCompare(b.dealer_label || b.ownership_label) || a.name.localeCompare(b.name);
    }
    if (opts.sort === 'category_asc') {
      return a.channel_label.localeCompare(b.channel_label) || a.name.localeCompare(b.name);
    }
    return (
      (rank[a.ownership] ?? 9) - (rank[b.ownership] ?? 9) ||
      (b.price_auec || 0) - (a.price_auec || 0) ||
      a.name.localeCompare(b.name)
    );
  });

  return filtered;
}

export class KnickKnacksViewController {
  private state: KnickKnacksState | null = null;
  private activeTab: KnickViewTab = 'spare';
  private query = '';
  private category: KnickCategoryFilter = 'all';
  private accountCategory: KnickAccountCategoryFilter = 'all';
  private shipCategory: KnickShipCategoryFilter = 'all';
  private locationId = 'all';
  private storageFilter = 'all';
  private accountSourceFilter: KnickAccountSourceFilter = 'rsi_hangar';
  private sort: KnickSortKey = 'qty_desc';
  private expandedKeys = new Set<string>();

  private viewTabsEl!: HTMLElement;
  private searchEl!: HTMLInputElement;
  private locationSelectEl!: HTMLSelectElement;
  private storageSelectEl!: HTMLSelectElement;
  private accountSourceSelectEl!: HTMLSelectElement;
  private sortSelectEl!: HTMLSelectElement;
  private refreshBtn!: HTMLButtonElement;
  private clearBtn!: HTMLButtonElement;
  private statusBadgeEl!: HTMLElement;
  private metaEl!: HTMLElement;
  private statsEl!: HTMLElement;
  private categoryBarEl!: HTMLElement;
  private locationChipsEl!: HTMLElement;
  private countEl!: HTMLElement;
  private excludedHintEl!: HTMLElement;
  private colHeaderRowEl!: HTMLTableRowElement;
  private tbodyEl!: HTMLTableSectionElement;

  constructor(
    private root: HTMLElement,
    private bridge: DesktopBridge,
    private hooks?: { onNotice?: (msg: string) => void },
  ) {
    this.mount();
  }

  private mount(): void {
    this.root.innerHTML = `
      <div class="ss-kk-shell">
        <div class="ss-card ss-kk-header-card">
          <div id="kk-view-tabs" class="ss-kk-view-tabs"></div>
          <div class="ss-kk-top-row">
            <div id="kk-stats" class="ss-kk-stats"></div>
            <div class="ss-kk-actions">
              <span id="kk-status-badge" class="ss-pill ss-pill-warn">Waiting</span>
              <span id="kk-meta" class="ss-kk-meta">Waiting for inventory sync</span>
              <button id="kk-refresh-btn" type="button" class="ss-btn ss-btn-accent">Refresh</button>
            </div>
          </div>
          <div class="ss-kk-filter-row">
            <input id="kk-search-input" type="search" class="ss-input ss-kk-search" placeholder="Search spare components, ores, Wikelo turn-ins, Comp Boards, stations…" />
            <select id="kk-location-select" class="ss-select ss-kk-select" aria-label="Filter by location">
              <option value="all">All locations</option>
            </select>
            <select id="kk-storage-select" class="ss-select ss-kk-select" aria-label="Filter by storage container">
              <option value="all">All storage types</option>
              <option value="local">Local Storage only</option>
              <option value="hangar">Persistent Hangar</option>
              <option value="nested">Inside Backpacks / Crates</option>
            </select>
            <select id="kk-account-source-select" class="ss-select ss-kk-select" aria-label="Filter by account attribution" hidden>
              <option value="rsi_hangar">RSI Hangar (Permanent)</option>
              <option value="ingame_ltp">In-Game Persistent (LTP)</option>
              <option value="all">All Account Items</option>
            </select>
            <select id="kk-sort-select" class="ss-select ss-kk-select" aria-label="Sort items">
              <option value="qty_desc">Sort: Highest qty</option>
              <option value="name_asc">Sort: Name A–Z</option>
              <option value="location_asc">Sort: Station A–Z</option>
              <option value="category_asc">Sort: Category</option>
            </select>
            <button id="kk-clear-btn" type="button" class="ss-btn ss-btn-default">Clear</button>
          </div>
          <div id="kk-category-bar" class="ss-kk-cat-bar"></div>
          <div id="kk-location-chips" class="ss-kk-loc-chips"></div>
        </div>

        <div class="ss-card ss-kk-table-card">
          <div class="ss-kk-table-header">
            <span id="kk-visible-count" class="ss-kk-visible-count">0 matching stacks</span>
            <span id="kk-excluded-hint" class="ss-kk-excluded-hint">Ship-mounted parts, worn loadout &amp; starter respawn gear excluded automatically</span>
          </div>
          <div class="ss-table-scroll ss-kk-scroll">
            <table class="ss-table ss-kk-table">
              <thead>
                <tr id="kk-col-header-row">
                  <th>Item</th>
                  <th>Category</th>
                  <th>Location</th>
                  <th>Container</th>
                  <th class="ss-kk-num-col">Qty</th>
                </tr>
              </thead>
              <tbody id="kk-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    this.viewTabsEl = this.root.querySelector('#kk-view-tabs')!;
    this.searchEl = this.root.querySelector('#kk-search-input')!;
    this.locationSelectEl = this.root.querySelector('#kk-location-select')!;
    this.storageSelectEl = this.root.querySelector('#kk-storage-select')!;
    this.accountSourceSelectEl = this.root.querySelector('#kk-account-source-select')!;
    this.sortSelectEl = this.root.querySelector('#kk-sort-select')!;
    this.refreshBtn = this.root.querySelector('#kk-refresh-btn')!;
    this.clearBtn = this.root.querySelector('#kk-clear-btn')!;
    this.statusBadgeEl = this.root.querySelector('#kk-status-badge')!;
    this.metaEl = this.root.querySelector('#kk-meta')!;
    this.statsEl = this.root.querySelector('#kk-stats')!;
    this.categoryBarEl = this.root.querySelector('#kk-category-bar')!;
    this.locationChipsEl = this.root.querySelector('#kk-location-chips')!;
    this.countEl = this.root.querySelector('#kk-visible-count')!;
    this.excludedHintEl = this.root.querySelector('#kk-excluded-hint')!;
    this.colHeaderRowEl = this.root.querySelector('#kk-col-header-row')!;
    this.tbodyEl = this.root.querySelector('#kk-tbody')!;

    this.tbodyEl.addEventListener('click', (ev) => {
      const tr = (ev.target as HTMLElement | null)?.closest<HTMLTableRowElement>('tr[data-expand-key]');
      if (!tr || !tr.dataset.expandKey) return;
      const key = tr.dataset.expandKey;
      if (this.expandedKeys.has(key)) this.expandedKeys.delete(key);
      else this.expandedKeys.add(key);
      this.renderTable();
    });

    this.searchEl.addEventListener('input', () => {
      this.query = this.searchEl.value;
      this.renderTable();
    });
    this.locationSelectEl.addEventListener('change', () => {
      this.locationId = this.locationSelectEl.value || 'all';
      this.renderLocationChips();
      this.renderTable();
    });
    this.storageSelectEl.addEventListener('change', () => {
      this.storageFilter = this.storageSelectEl.value || 'all';
      this.renderTable();
    });
    this.accountSourceSelectEl.addEventListener('change', () => {
      this.accountSourceFilter = (this.accountSourceSelectEl.value as KnickAccountSourceFilter) || 'rsi_hangar';
      this.renderCategories();
      this.renderLocationChips();
      this.renderTable();
    });
    this.sortSelectEl.addEventListener('change', () => {
      this.sort = (this.sortSelectEl.value as KnickSortKey) || 'qty_desc';
      this.renderTable();
    });
    this.clearBtn.addEventListener('click', () => {
      this.query = '';
      this.searchEl.value = '';
      if (this.activeTab === 'spare') {
        this.category = 'all';
        this.locationId = 'all';
        this.storageFilter = 'all';
        this.locationSelectEl.value = 'all';
        this.storageSelectEl.value = 'all';
      } else if (this.activeTab === 'account') {
        this.accountCategory = 'all';
        this.accountSourceFilter = 'rsi_hangar';
        this.accountSourceSelectEl.value = 'rsi_hangar';
      } else {
        this.shipCategory = 'all';
      }
      this.renderCategories();
      this.renderLocationChips();
      this.renderTable();
    });
    this.refreshBtn.addEventListener('click', () => {
      void this.triggerRefresh();
    });
  }

  private async triggerRefresh(): Promise<void> {
    this.refreshBtn.disabled = true;
    this.refreshBtn.textContent = 'Syncing…';
    try {
      await this.bridge.sendCommand({ action: 'knick_knacks_refresh' });
      this.hooks?.onNotice?.('Refreshing station storage & RSI Hangar entitlements…');
    } catch (err) {
      this.hooks?.onNotice?.(err instanceof Error ? err.message : 'Unable to request refresh');
      this.refreshBtn.disabled = false;
      this.refreshBtn.textContent = 'Refresh';
    }
  }

  public updateFromSnapshot(snap: PeopleSnapshot): void {
    if (!snap.knick_knacks) return;
    this.state = snap.knick_knacks;
    this.renderAll();
  }

  private setTab(tab: KnickViewTab): void {
    if (this.activeTab === tab) return;
    this.activeTab = tab;
    this.renderAll();
  }

  private renderViewTabs(): void {
    const st = this.state;
    const spareCount = st?.unique_items ?? st?.items.length ?? 0;
    const rsiCount = st?.account_counts?.rsi_hangar ?? (st?.account_items ?? []).filter((x) => x.source_kind === 'rsi_hangar').length;
    const shipCount = st?.ship_counts?.all ?? st?.ships?.length ?? 0;
    const tabs: Array<{ key: KnickViewTab; label: string; count: number }> = [
      { key: 'spare', label: 'Spare Storage', count: spareCount },
      { key: 'account', label: 'Account Hangar (RSI)', count: rsiCount },
      { key: 'ships', label: 'Ships & Fleet', count: shipCount },
    ];
    this.viewTabsEl.innerHTML = '';
    for (const t of tabs) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `ss-kk-view-tab${this.activeTab === t.key ? ' is-active' : ''}`;
      btn.dataset.tab = t.key;
      btn.innerHTML = `${esc(t.label)} <span class="ss-kk-cat-count ss-mono">${t.count.toLocaleString()}</span>`;
      btn.addEventListener('click', () => this.setTab(t.key));
      this.viewTabsEl.appendChild(btn);
    }
  }

  private renderAll(): void {
    const st = this.state;
    if (!st) return;

    this.renderViewTabs();

    const syncing = Boolean(st.syncing);
    this.refreshBtn.disabled = syncing;
    this.refreshBtn.textContent = syncing ? 'Syncing…' : 'Refresh';

    this.statusBadgeEl.className = 'ss-pill';
    if (syncing) {
      this.statusBadgeEl.classList.add('ss-pill-warn');
      this.statusBadgeEl.textContent = 'Syncing';
    } else if (st.status === 'ok') {
      this.statusBadgeEl.classList.add('ss-pill-ok');
      this.statusBadgeEl.textContent = 'Live Sync';
    } else if (st.status === 'offline' || st.status === 'idle') {
      this.statusBadgeEl.classList.add('ss-pill-warn');
      this.statusBadgeEl.textContent = 'Sign In Needed';
    } else {
      this.statusBadgeEl.classList.add('ss-pill-bad');
      this.statusBadgeEl.textContent = 'Sync Issue';
    }

    this.metaEl.textContent = formatAge(st.updated_at);

    const isSpare = this.activeTab === 'spare';
    const isAccount = this.activeTab === 'account';
    this.locationSelectEl.hidden = !isSpare;
    this.storageSelectEl.hidden = !isSpare;
    this.accountSourceSelectEl.hidden = !isAccount;
    if (isSpare) {
      this.searchEl.placeholder = 'Search spare components, ores, Wikelo turn-ins, Comp Boards, stations…';
      this.excludedHintEl.textContent = 'Ship-mounted parts, worn loadout & starter respawn gear excluded automatically';
      this.colHeaderRowEl.innerHTML =
        '<th>Item</th><th>Category</th><th>Location</th><th>Container</th><th class="ss-kk-num-col">Qty</th>';
    } else if (isAccount) {
      this.searchEl.placeholder = 'Search RSI Hangar ships, liveries, flair, armor, weapons, LTP items…';
      this.excludedHintEl.textContent = 'Permanent RSI Hangar pledges, flair & Long-Term Persistence items bound to your account';
      this.colHeaderRowEl.innerHTML =
        '<th>Item</th><th>Category</th><th>Attribution</th><th>Status</th><th class="ss-kk-num-col">Qty</th>';
    } else {
      this.searchEl.placeholder = 'Search earned ships, pledged fleet, dealerships (New Deal, Astro Armada), Wikelo…';
      this.excludedHintEl.textContent = 'Compares your live owned fleet (earned in-game + pledged) against earnable dealership, Wikelo & Executive Hangar ships';
      this.colHeaderRowEl.innerHTML =
        '<th>Ship / Vehicle</th><th>Ownership</th><th>How to Earn / Dealer</th><th>Role</th><th class="ss-kk-num-col">aUEC / Qty</th>';
    }

    if (isSpare) {
      const unique = st.unique_items ?? st.items.length ?? 0;
      const totalQty = st.total_quantity ?? 0;
      const locCount = st.locations?.length ?? 0;
      const excluded = st.mounted_excluded_count ?? 0;
      this.statsEl.innerHTML = `
        <div class="ss-kk-stat"><span>Spare Stacks</span><strong class="ss-mono">${unique.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Total Spare Units</span><strong class="ss-mono">${totalQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Locations</span><strong class="ss-mono">${locCount.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Ship / Worn Hidden</span><strong class="ss-mono ss-text-ok">${excluded.toLocaleString()}</strong></div>
      `;

      const currentLoc = this.locationId;
      const locs = st.locations ?? [];
      this.locationSelectEl.innerHTML = '<option value="all">All locations</option>';
      for (const loc of locs) {
        const opt = document.createElement('option');
        opt.value = loc.id;
        const sysLabel = loc.system ? ` · ${loc.system}` : '';
        opt.textContent = `${loc.name}${sysLabel} (${loc.quantity.toLocaleString()})`;
        this.locationSelectEl.appendChild(opt);
      }
      const stillValid = currentLoc === 'all' || locs.some((l) => l.id === currentLoc);
      this.locationId = stillValid ? currentLoc : 'all';
      this.locationSelectEl.value = this.locationId;
    } else if (isAccount) {
      const ac = st.account_counts ?? {};
      const rsiQty = ac.rsi_hangar ?? 0;
      const ltpQty = ac.ingame_ltp ?? 0;
      const shipsQty = ac.ships ?? 0;
      const paintsFlairQty = (ac.paints ?? 0) + (ac.flair ?? 0);
      this.statsEl.innerHTML = `
        <div class="ss-kk-stat"><span>RSI Hangar</span><strong class="ss-mono">${rsiQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>In-Game LTP</span><strong class="ss-mono">${ltpQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Ships &amp; Vehicles</span><strong class="ss-mono">${shipsQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Paints &amp; Flair</span><strong class="ss-mono ss-text-ok">${paintsFlairQty.toLocaleString()}</strong></div>
      `;
      this.accountSourceSelectEl.value = this.accountSourceFilter;
    } else {
      const sc = st.ship_counts ?? {};
      const earnedQty = sc.ingame_earned ?? 0;
      const pledgedQty = sc.pledged ?? 0;
      const unownedQty = sc.unowned ?? 0;
      const specialOwned = (st.ships ?? []).filter(
        (s) => s.owned && (s.channel === 'wikelo' || s.channel === 'exec_hangar'),
      ).length;
      this.statsEl.innerHTML = `
        <div class="ss-kk-stat"><span>Earned In-Game</span><strong class="ss-mono ss-text-ok">${earnedQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>RSI Hangar (Pledged)</span><strong class="ss-mono">${pledgedQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Not Owned (Earnable)</span><strong class="ss-mono">${unownedQty.toLocaleString()}</strong></div>
        <div class="ss-kk-stat"><span>Wikelo / Exec Owned</span><strong class="ss-mono ss-text-ok">${specialOwned.toLocaleString()}</strong></div>
      `;
    }

    this.renderCategories();
    this.renderLocationChips();
    this.renderTable();
  }

  private renderCategories(): void {
    this.categoryBarEl.innerHTML = '';
    if (this.activeTab === 'spare') {
      const counts = this.state?.category_counts ?? {};
      const defs: Array<{ key: KnickCategoryFilter; label: string }> = [
        { key: 'all', label: 'All Spare' },
        { key: 'crafted', label: 'Crafted Gear & Lasers' },
        { key: 'ship_components', label: 'Ship Components' },
        { key: 'mining_crafting', label: 'Mining & Crafting' },
        { key: 'wikelo', label: 'Wikelo Turn-Ins' },
        { key: 'comp_boards', label: 'Comp Boards & Keys' },
        { key: 'gear_weapons', label: 'FPS Gear & Paints' },
        { key: 'other', label: 'Cargo & Other' },
      ];
      for (const d of defs) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `ss-kk-cat-btn${this.category === d.key ? ' is-active' : ''}`;
        btn.dataset.category = d.key;
        const cnt = counts[d.key] ?? 0;
        btn.innerHTML = `${esc(d.label)} <span class="ss-kk-cat-count ss-mono">${cnt.toLocaleString()}</span>`;
        btn.addEventListener('click', () => {
          this.category = d.key;
          this.renderCategories();
          this.renderTable();
        });
        this.categoryBarEl.appendChild(btn);
      }
      return;
    }

    if (this.activeTab === 'ships') {
      const sc = this.state?.ship_counts ?? {};
      const defs: Array<{ key: KnickShipCategoryFilter; label: string }> = [
        { key: 'all', label: 'All Ships' },
        { key: 'ingame_earned', label: 'Earned In-Game' },
        { key: 'pledged', label: 'RSI Hangar' },
        { key: 'unowned', label: 'Not Owned (Earnable)' },
        { key: 'dealership', label: 'Dealership (aUEC)' },
        { key: 'wikelo', label: 'Wikelo Emporium' },
        { key: 'exec_hangar', label: 'Executive Hangar' },
      ];
      for (const d of defs) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `ss-kk-cat-btn${this.shipCategory === d.key ? ' is-active' : ''}`;
        btn.dataset.category = d.key;
        const cnt = sc[d.key] ?? 0;
        btn.innerHTML = `${esc(d.label)} <span class="ss-kk-cat-count ss-mono">${cnt.toLocaleString()}</span>`;
        btn.addEventListener('click', () => {
          this.shipCategory = d.key;
          this.renderCategories();
          this.renderTable();
        });
        this.categoryBarEl.appendChild(btn);
      }
      return;
    }

    const accountItems = (this.state?.account_items ?? []).filter(
      (it) => this.accountSourceFilter === 'all' || it.source_kind === this.accountSourceFilter,
    );
    const catTotals: Record<string, number> = { all: 0 };
    for (const it of accountItems) {
      catTotals.all += it.quantity;
      catTotals[it.category] = (catTotals[it.category] ?? 0) + it.quantity;
    }
    const defs: Array<{ key: KnickAccountCategoryFilter; label: string }> = [
      { key: 'all', label: 'All Account' },
      { key: 'ships', label: 'Ships & Vehicles' },
      { key: 'paints', label: 'Paints & Liveries' },
      { key: 'gear_weapons', label: 'FPS Gear & Weapons' },
      { key: 'ship_components', label: 'Ship Components' },
      { key: 'flair', label: 'Flair & Hangars' },
    ];
    for (const d of defs) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `ss-kk-cat-btn${this.accountCategory === d.key ? ' is-active' : ''}`;
      btn.dataset.category = d.key;
      const cnt = catTotals[d.key] ?? 0;
      btn.innerHTML = `${esc(d.label)} <span class="ss-kk-cat-count ss-mono">${cnt.toLocaleString()}</span>`;
      btn.addEventListener('click', () => {
        this.accountCategory = d.key;
        this.renderCategories();
        this.renderTable();
      });
      this.categoryBarEl.appendChild(btn);
    }
  }

  private renderLocationChips(): void {
    this.locationChipsEl.innerHTML = '';
    if (this.activeTab === 'ships') {
      return;
    }
    if (this.activeTab === 'spare') {
      const locs = this.state?.locations ?? [];
      if (locs.length === 0) return;
      for (const loc of locs.slice(0, 12)) {
        const chip = document.createElement('button');
        chip.type = 'button';
        const active = this.locationId === loc.id;
        chip.className = `ss-kk-loc-chip${active ? ' is-active' : ''}`;
        const sysTag = loc.system ? ` · ${loc.system}` : '';
        chip.innerHTML = `<span class="ss-kk-loc-name">${esc(loc.name)}</span><span class="ss-kk-loc-sys">${esc(sysTag)}</span> <strong class="ss-mono">${loc.quantity.toLocaleString()}</strong>`;
        chip.addEventListener('click', () => {
          this.locationId = active ? 'all' : loc.id;
          this.locationSelectEl.value = this.locationId;
          this.renderLocationChips();
          this.renderTable();
        });
        this.locationChipsEl.appendChild(chip);
      }
      return;
    }

    const ac = this.state?.account_counts ?? {};
    const defs: Array<{ key: KnickAccountSourceFilter; label: string; count: number }> = [
      { key: 'rsi_hangar', label: 'RSI Hangar (Permanent)', count: ac.rsi_hangar ?? 0 },
      { key: 'ingame_ltp', label: 'In-Game Persistent (LTP)', count: ac.ingame_ltp ?? 0 },
      { key: 'all', label: 'All Account Items', count: ac.all ?? 0 },
    ];
    for (const d of defs) {
      const chip = document.createElement('button');
      chip.type = 'button';
      const active = this.accountSourceFilter === d.key;
      chip.className = `ss-kk-loc-chip${active ? ' is-active' : ''}`;
      chip.dataset.source = d.key;
      chip.innerHTML = `<span class="ss-kk-loc-name">${esc(d.label)}</span> <strong class="ss-mono">${d.count.toLocaleString()}</strong>`;
      chip.addEventListener('click', () => {
        this.accountSourceFilter = d.key;
        this.accountSourceSelectEl.value = d.key;
        this.renderCategories();
        this.renderLocationChips();
        this.renderTable();
      });
      this.locationChipsEl.appendChild(chip);
    }
  }

  private renderTable(): void {
    if (this.activeTab === 'account') {
      this.renderAccountTable();
      return;
    }
    if (this.activeTab === 'ships') {
      this.renderShipsTable();
      return;
    }
    const items = this.state?.items ?? [];
    const visible = filterAndSortItems(items, {
      query: this.query,
      category: this.category,
      locationId: this.locationId,
      storageFilter: this.storageFilter,
      sort: this.sort,
    });
    const totalVisibleQty = visible.reduce((acc, item) => acc + item.quantity, 0);
    this.countEl.textContent = `${visible.length.toLocaleString()} stacks · ${totalVisibleQty.toLocaleString()} units shown`;

    if (visible.length === 0) {
      const msg = items.length === 0
        ? (this.state?.message || 'No synced inventory items yet. Click Refresh while signed in to Star Citizen.')
        : 'No spare items match your current filters.';
      this.tbodyEl.innerHTML = `<tr><td colspan="5" class="ss-kk-empty">${esc(msg)}</td></tr>`;
      return;
    }

    const cap = visible.slice(0, 500);
    const htmlParts: string[] = [];
    for (const item of cap) {
      const sub = formatSizeGrade(item);
      const badges: string[] = [];
      const tiers = item.quality_tiers ?? [];
      const craftedIngs = item.crafted_ingredients ?? [];
      const canExpand = tiers.length > 0 || craftedIngs.length > 0;
      const key = canExpand ? rowExpandKey(item) : '';
      const isExpanded = canExpand && this.expandedKeys.has(key);

      if (item.is_crafted) {
        const qSuffix = typeof item.crafted_quality === 'number' ? ` · Avg Q${item.crafted_quality}` : '';
        badges.push(`<span class="ss-kk-tag ss-kk-tag-crafted">Crafted${qSuffix}</span>`);
      }
      if (tiers.length > 0 && typeof item.max_quality === 'number') {
        const highCls = item.max_quality >= 900 ? ' is-high' : '';
        const qLabel =
          typeof item.min_quality === 'number' && item.min_quality !== item.max_quality
            ? `Q${item.min_quality}–${item.max_quality} · ${tiers.length} tiers`
            : `Q${item.max_quality}`;
        badges.push(`<span class="ss-kk-tag ss-kk-tag-quality${highCls}">${esc(qLabel)}</span>`);
      }
      if (item.is_wikelo) badges.push('<span class="ss-kk-tag ss-kk-tag-wikelo">Wikelo</span>');
      if (item.is_crafting) badges.push('<span class="ss-kk-tag ss-kk-tag-craft">Crafting</span>');
      if (item.is_comp_board) badges.push('<span class="ss-kk-tag ss-kk-tag-board">Comp Board</span>');

      const sysBadge = item.system
        ? `<span class="ss-kk-sys-tag">${esc(item.system)}</span>`
        : '';
      const storageCls =
        item.storage_kind === 'hangar'
          ? 'ss-kk-store-hangar'
          : item.container.startsWith('In ')
            ? 'ss-kk-store-nested'
            : 'ss-kk-store-local';

      const chevronHtml = canExpand
        ? `<span class="ss-kk-chevron" aria-hidden="true">${isExpanded ? '▾' : '▸'}</span>`
        : '';
      const rowAttrs = canExpand
        ? ` class="ss-kk-row-expandable" data-expand-key="${esc(key)}" aria-expanded="${isExpanded ? 'true' : 'false'}"`
        : '';

      let qtyHtml = `<strong>${item.quantity.toLocaleString()}×</strong>`;
      if (item.is_cargo_scu && typeof item.total_scu === 'number' && item.total_scu > 0) {
        qtyHtml = `<strong>${formatScu(item.total_scu)} SCU</strong><div class="ss-kk-qty-sub">${item.quantity.toLocaleString()} ${item.quantity === 1 ? 'box' : 'boxes'}</div>`;
      } else if (typeof item.total_scu === 'number' && item.total_scu > 0) {
        qtyHtml = `<strong>${item.quantity.toLocaleString()}×</strong><div class="ss-kk-qty-sub">${formatScu(item.total_scu)} SCU</div>`;
      }

      htmlParts.push(`
        <tr${rowAttrs}>
          <td>
            <div class="ss-kk-item-title">${chevronHtml}${esc(item.name)} ${badges.join('')}</div>
            ${sub ? `<div class="ss-kk-item-sub">${esc(sub)}</div>` : ''}
          </td>
          <td><span class="ss-kk-cat-pill ss-kk-cat-${esc(item.category)}">${esc(item.category_label)}</span></td>
          <td><span class="ss-kk-loc-cell">${esc(item.location_name)}</span> ${sysBadge}</td>
          <td><span class="ss-kk-store-pill ${storageCls}">${esc(item.container)}</span></td>
          <td class="ss-kk-num-col ss-mono">${qtyHtml}</td>
        </tr>
      `);

      if (isExpanded) {
        const chipsHtml: string[] = [];
        let detailHeading = '';
        if (tiers.length > 0) {
          detailHeading = `Quality &amp; Exact Quantity Breakdown (${tiers.length} ${tiers.length === 1 ? 'quality tier' : 'quality tiers'})`;
          for (const t of tiers) {
            const hiCls = t.quality >= 900 ? ' is-high' : '';
            const primaryAmt = item.is_cargo_scu
              ? `${formatScu(t.scu)} SCU`
              : `${t.units.toLocaleString()}×`;
            const subAmt = item.is_cargo_scu
              ? `${t.units.toLocaleString()} ${t.units === 1 ? 'box' : 'boxes'} · ${t.uscu.toLocaleString()} µSCU`
              : `${formatScu(t.scu)} SCU`;
            chipsHtml.push(`
              <div class="ss-kk-tier-chip">
                <span class="ss-kk-tier-q ss-mono${hiCls}">Q${t.quality}</span>
                <span class="ss-kk-tier-amt ss-mono">${esc(primaryAmt)}</span>
                <span class="ss-kk-tier-sub ss-mono">${esc(subAmt)}</span>
              </div>
            `);
          }
        } else if (craftedIngs.length > 0) {
          detailHeading = `Crafted Recipe Materials${typeof item.crafted_quality === 'number' ? ` · Avg Q${item.crafted_quality}` : ''}`;
          for (const ing of craftedIngs) {
            const hiCls = ing.quality >= 900 ? ' is-high' : '';
            const amtLabel = ing.amount >= 1000 ? `${formatScu(ing.amount / 1_000_000)} SCU` : `${ing.amount.toLocaleString()}×`;
            chipsHtml.push(`
              <div class="ss-kk-tier-chip">
                <span class="ss-kk-tier-q ss-mono${hiCls}">Q${ing.quality}</span>
                <span class="ss-kk-tier-amt">${esc(ing.name)}</span>
                <span class="ss-kk-tier-sub ss-mono">${esc(amtLabel)}</span>
              </div>
            `);
          }
        }
        htmlParts.push(`
          <tr class="ss-kk-detail-row">
            <td colspan="5">
              <div class="ss-kk-detail-head">${detailHeading}</div>
              <div class="ss-kk-tier-grid">${chipsHtml.join('')}</div>
            </td>
          </tr>
        `);
      }
    }
    if (visible.length > cap.length) {
      htmlParts.push(
        `<tr><td colspan="5" class="ss-kk-empty">Showing top ${cap.length.toLocaleString()} of ${visible.length.toLocaleString()} matching stacks — refine search or station filter to narrow further.</td></tr>`,
      );
    }
    this.tbodyEl.innerHTML = htmlParts.join('');
  }

  private renderAccountTable(): void {
    const items = this.state?.account_items ?? [];
    const visible = filterAndSortAccountItems(items, {
      query: this.query,
      category: this.accountCategory,
      sourceFilter: this.accountSourceFilter,
      sort: this.sort,
    });
    const totalQty = visible.reduce((acc, item) => acc + item.quantity, 0);
    this.countEl.textContent = `${visible.length.toLocaleString()} entries · ${totalQty.toLocaleString()} permanent items shown`;

    if (visible.length === 0) {
      const msg = items.length === 0
        ? (this.state?.message || 'No account entitlements synced yet. Click Refresh while signed in to Star Citizen.')
        : 'No account-attributed items match your current filters.';
      this.tbodyEl.innerHTML = `<tr><td colspan="5" class="ss-kk-empty">${esc(msg)}</td></tr>`;
      return;
    }

    const cap = visible.slice(0, 500);
    const htmlParts: string[] = [];
    for (const item of cap) {
      const sub = formatSizeGrade(item);
      const badge = item.real_money
        ? '<span class="ss-kk-tag ss-kk-tag-rm">Account Permanent</span>'
        : '';
      const attrCls = item.source_kind === 'rsi_hangar' ? 'ss-kk-attr-hangar' : 'ss-kk-attr-ltp';
      const statusCls = item.status_label === 'Delivered' ? 'ss-kk-store-local' : 'ss-kk-store-nested';

      htmlParts.push(`
        <tr>
          <td>
            <div class="ss-kk-item-title">${esc(item.name)} ${badge}</div>
            ${sub ? `<div class="ss-kk-item-sub">${esc(sub)}</div>` : ''}
          </td>
          <td><span class="ss-kk-cat-pill ss-kk-cat-${esc(item.category)}">${esc(item.category_label)}</span></td>
          <td><span class="ss-kk-store-pill ${attrCls}">${esc(item.source_label)}</span></td>
          <td><span class="ss-kk-store-pill ${statusCls}">${esc(item.status_label)}</span></td>
          <td class="ss-kk-num-col ss-mono"><strong>${item.quantity.toLocaleString()}×</strong></td>
        </tr>
      `);
    }
    if (visible.length > cap.length) {
      htmlParts.push(
        `<tr><td colspan="5" class="ss-kk-empty">Showing top ${cap.length.toLocaleString()} of ${visible.length.toLocaleString()} matching items — refine search to narrow further.</td></tr>`,
      );
    }
    this.tbodyEl.innerHTML = htmlParts.join('');
  }

  private renderShipsTable(): void {
    const ships = this.state?.ships ?? [];
    const visible = filterAndSortShips(ships, {
      query: this.query,
      filter: this.shipCategory,
      sort: this.sort,
    });
    const earnedVis = visible.filter((s) => s.owned).length;
    const unownedVis = visible.length - earnedVis;
    if (this.shipCategory === 'exec_hangar') {
      this.countEl.textContent = `Executive Hangar Checklist: ${earnedVis.toLocaleString()} / ${visible.length.toLocaleString()} collected · ${unownedVis.toLocaleString()} remaining`;
    } else {
      this.countEl.textContent = `${visible.length.toLocaleString()} ships · ${earnedVis.toLocaleString()} owned · ${unownedVis.toLocaleString()} earnable`;
    }

    if (visible.length === 0) {
      const msg = ships.length === 0
        ? (this.state?.message || 'No fleet data synced yet. Click Refresh while signed in to Star Citizen.')
        : 'No ships match your current filters.';
      this.tbodyEl.innerHTML = `<tr><td colspan="5" class="ss-kk-empty">${esc(msg)}</td></tr>`;
      return;
    }

    const cap = visible.slice(0, 500);
    const htmlParts: string[] = [];
    for (const s of cap) {
      const hasRecipe = Boolean(s.recipe);
      const expandKey = hasRecipe ? `ship:${s.crc}:${s.ownership}:${s.name}` : '';
      const isExpanded = hasRecipe && this.expandedKeys.has(expandKey);
      const chevronHtml = hasRecipe
        ? `<span class="ss-kk-chevron" aria-hidden="true">${isExpanded ? '▾' : '▸'}</span>`
        : '';
      const rowAttrs = hasRecipe
        ? ` class="ss-kk-row-expandable" data-expand-key="${esc(expandKey)}" aria-expanded="${isExpanded ? 'true' : 'false'}"`
        : '';

      const ownCls =
        s.ownership === 'ingame_earned'
          ? 'ss-kk-ship-earned'
          : s.ownership === 'pledged'
            ? 'ss-kk-ship-pledged'
            : 'ss-kk-ship-unowned';
      const channelBadge =
        s.channel === 'wikelo' || s.also_wikelo || s.channel === 'exec_hangar' || !s.owned
          ? `<span class="ss-kk-tag ss-kk-tag-${s.channel === 'wikelo' ? 'wikelo' : s.channel === 'exec_hangar' ? 'board' : 'craft'}">${esc(s.channel_label)}</span>`
          : '';

      const subParts: string[] = [];
      if (s.company) subParts.push(s.company);
      if (s.scu > 0) subParts.push(`${s.scu} SCU cargo`);
      const subText = subParts.join(' · ');

      const sourceText = s.dealer_label || (s.owned ? s.channel_label : 'In-Game');
      let costHtml = '';
      if (s.price_auec > 0) {
        costHtml = `<strong>${s.price_auec.toLocaleString()} aUEC</strong>`;
        if (s.owned && s.quantity > 1) {
          costHtml += `<div class="ss-kk-qty-sub">${s.quantity.toLocaleString()}× owned</div>`;
        }
      } else if (s.owned) {
        costHtml = `<strong>${Math.max(1, s.quantity).toLocaleString()}× Owned</strong>`;
      } else {
        costHtml = `<strong>${s.channel === 'wikelo' ? 'Barter' : 'Vault Reward'}</strong>`;
      }

      const checkPrefix =
        s.channel === 'exec_hangar'
          ? `<span class="ss-kk-tag ${s.owned ? 'ss-kk-tag-crafted' : 'ss-kk-tag-board'}" aria-label="${s.owned ? 'Collected' : 'Uncollected'}">${s.owned ? '✓ Collected' : '☐ Uncollected'}</span> `
          : '';
      const ownLabel =
        this.shipCategory === 'exec_hangar'
          ? s.owned
            ? '✓ Collected'
            : '☐ Uncollected'
          : s.ownership_label;

      htmlParts.push(`
        <tr${rowAttrs}>
          <td>
            <div class="ss-kk-item-title">${chevronHtml}${checkPrefix}${esc(s.name)} ${channelBadge}</div>
            ${subText ? `<div class="ss-kk-item-sub">${esc(subText)}</div>` : ''}
          </td>
          <td><span class="ss-kk-store-pill ${ownCls}">${esc(ownLabel)}</span></td>
          <td><span class="ss-kk-loc-cell">${esc(sourceText)}</span></td>
          <td><span class="ss-kk-cat-pill ss-kk-cat-ships">${esc(s.role || 'Ship')}</span></td>
          <td class="ss-kk-num-col ss-mono">${costHtml}</td>
        </tr>
      `);

      if (isExpanded && s.recipe) {
        const parts = s.recipe.split(';').map((p) => p.trim()).filter(Boolean);
        const chipsHtml = parts.map((p) => `<div class="ss-kk-tier-chip"><span class="ss-kk-tier-amt">${esc(p)}</span></div>`).join('');
        htmlParts.push(`
          <tr class="ss-kk-detail-row">
            <td colspan="5">
              <div class="ss-kk-detail-head">${esc(s.channel_label)} Acquisition Requirements</div>
              <div class="ss-kk-tier-grid">${chipsHtml}</div>
            </td>
          </tr>
        `);
      }
    }
    this.tbodyEl.innerHTML = htmlParts.join('');
  }

  public destroy(): void {
    this.root.innerHTML = '';
  }
}
