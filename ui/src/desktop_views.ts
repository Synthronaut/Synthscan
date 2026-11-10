import {
  BlueprintDefinitionData,
  DaylightBodyData,
  DaylightCatalogueData,
  DaylightSiteData,
  DesktopBridge,
  DesktopCatalog,
  DesktopCommand,
  DesktopState,
  DirectoryItemData,
  MiningLocationData,
  PeopleSnapshot,
  RefineryLocationData,
  RefineryOrderData,
} from './bridge';

// --- Daylight Astronomical Calculator (client-side implementation of daylight.py) ---
const EPOCH = 1577836800.0; // 2020-01-01 UTC
const TAU = 2 * Math.PI;

function rotateVec(
  quaternion: [number, number, number, number],
  point: [number, number, number],
): [number, number, number] {
  const norm = Math.sqrt(
    quaternion[0] * quaternion[0] +
      quaternion[1] * quaternion[1] +
      quaternion[2] * quaternion[2] +
      quaternion[3] * quaternion[3],
  );
  if (norm < 1e-8) return point;
  const w = quaternion[0] / norm;
  const x = quaternion[1] / norm;
  const y = quaternion[2] / norm;
  const z = quaternion[3] / norm;
  const [a, b, c] = point;
  return [
    (1 - 2 * y * y - 2 * z * z) * a + (2 * x * y - 2 * z * w) * b + (2 * x * z + 2 * y * w) * c,
    (2 * x * y + 2 * z * w) * a + (1 - 2 * x * x - 2 * z * z) * b + (2 * y * z - 2 * x * w) * c,
    (2 * x * z - 2 * y * w) * a + (2 * y * z + 2 * x * w) * b + (1 - 2 * x * x - 2 * y * y) * c,
  ];
}

export interface SunlightForecast {
  daylight: boolean;
  altitude_degrees: number;
  sunrise?: string;
  sunset?: string;
}

export function calculateDaylight(
  body: DaylightBodyData,
  site: DaylightSiteData,
  nowSeconds: number,
): SunlightForecast {
  try {
    const center = body.center_km;
    const star = body.star_km;
    const diff: [number, number, number] = [
      star[0] - center[0],
      star[1] - center[1],
      star[2] - center[2],
    ];
    const [sx, sy, sz] = rotateVec(body.quaternion, diff);
    const dist = Math.sqrt(sx * sx + sy * sy + sz * sz);
    const starAngle = Math.asin(body.star_radius_km / Math.max(dist, body.star_radius_km + 1));
    const sunLongitude =
      Math.atan2(sy, sx) - Math.PI / 2 - (body.correction_degrees * Math.PI) / 180;
    const declination = Math.atan2(sz, Math.hypot(sx, sy));

    const [x, y, z] = site.coordinates;
    const radius = Math.sqrt(x * x + y * y + z * z);
    const lat = Math.atan2(z, Math.hypot(x, y));
    const lon = Math.atan2(y, x);
    const dip = radius > body.radius_km ? Math.acos(Math.min(1.0, body.radius_km / radius)) : 0.0;
    const threshold = -Math.min(Math.PI / 2, starAngle + dip);

    const a = Math.sin(lat) * Math.sin(declination);
    const b = Math.cos(lat) * Math.cos(declination);
    const period = Math.abs(body.period_seconds);
    const omega = period > 0 ? -TAU / body.period_seconds : 0.0;
    const hour = omega
      ? sunLongitude - lon + omega * ((nowSeconds - EPOCH) % period)
      : sunLongitude - lon;
    const sine = Math.max(-1.0, Math.min(1.0, a + b * Math.cos(hour)));
    const altitude = Math.asin(sine);
    const daylight = altitude >= threshold;

    return {
      daylight,
      altitude_degrees: Math.round((altitude * 180) / Math.PI * 10) / 10,
    };
  } catch {
    return { daylight: true, altitude_degrees: 45 };
  }
}

export class DesktopViewsManager {
  private bridge: DesktopBridge;
  private catalog: DesktopCatalog | null = null;
  private desktopState: DesktopState | null = null;
  private currentActivePage = 'people';

  // Navigation callbacks
  private onNavigateRequested?: (page: string) => void;

  // View DOM elements
  private sidebarEl!: HTMLElement;
  private captureBadgeEl!: HTMLElement;
  private viewsContainerEl!: HTMLElement;

  // Directory filter state
  private directoryQuery = '';
  private directoryKind = '';
  private directorySelectedId = '';

  // Blueprints filter state
  private blueprintQuery = '';
  private blueprintType = '';

  // Mining Planner filter state
  private plannerQuery = '';
  private plannerFamily = 'Ship';
  private plannerSystem = '';

  // Daylight state
  private daylightSystem = 'Stanton';
  private daylightBodyName = '';
  private daylightSiteName = '';

  // 1-second interval timer for live countdowns
  private tickTimer: number | null = null;

  constructor(
    bridge: DesktopBridge,
    sidebarContainer: HTMLElement,
    viewsContainer: HTMLElement,
    onNavigate: (page: string) => void,
  ) {
    this.bridge = bridge;
    this.sidebarEl = sidebarContainer;
    this.viewsContainerEl = viewsContainer;
    this.onNavigateRequested = onNavigate;

    this.buildSidebar();
    this.buildViewsContainers();
    this.startTickLoop();
  }

  public destroy(): void {
    if (this.tickTimer !== null) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
  }

  public updateState(snap: PeopleSnapshot): void {
    if (snap.catalog) {
      this.catalog = snap.catalog;
    }
    if (snap.desktop) {
      this.desktopState = snap.desktop;
    }

    this.renderCaptureBadge();
    this.renderActiveView();
  }

  public setActivePage(page: string): void {
    this.currentActivePage = page;
    this.sidebarEl.querySelectorAll<HTMLButtonElement>('.ss-nav-btn[data-page]').forEach((btn) => {
      const active = btn.dataset.page === page;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    // Toggle view containers
    const pages = [
      'home',
      'directory',
      'people',
      'mission_log',
      'servers',
      'blueprints',
      'planner',
      'diary',
      'refinery',
      'executive_hangar',
      'hud_piracy',
      'daylight',
      'acceptance',
      'settings',
    ];
    for (const p of pages) {
      const el = this.viewsContainerEl.querySelector<HTMLElement>(`#ss-view-${p.replace(/_/g, '-')}`);
      if (el) {
        el.hidden = p !== page;
      }
    }

    this.renderActiveView();
  }

  private buildSidebar(): void {
    const navItems = [
      { id: 'home', label: 'Home', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
      { id: 'directory', label: 'Item & Ship Finder', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
      { id: 'people', label: 'People', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
      { id: 'mission_log', label: 'Mission & Wallet Log', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
      { id: 'servers', label: 'Server History', icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01' },
      { id: 'blueprints', label: 'Blueprint Library', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
      { id: 'planner', label: 'Mining Planner', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
      { id: 'diary', label: 'Mining Diary', icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
      { id: 'refinery', label: 'Refinery', icon: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z' },
      { id: 'executive_hangar', label: 'Executive Hangar', icon: 'M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z' },
      { id: 'hud_piracy', label: 'Piracy', icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
      { id: 'daylight', label: 'Day/Night Forecast', icon: 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z' },
      { id: 'acceptance', label: 'Automatic Acceptance', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
      { id: 'settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
    ];

    let navHtml = '';
    for (const item of navItems) {
      navHtml += `
        <button type="button" class="ss-nav-btn ${item.id === 'people' ? 'is-active' : ''}" data-page="${item.id}" role="tab" aria-selected="${item.id === 'people'}">
          <svg class="ss-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="${item.icon}"></path>
          </svg>
          <span class="ss-nav-label">${item.label}</span>
        </button>
      `;
    }

    this.sidebarEl.innerHTML = `
      <div class="ss-sidebar-brand">
        <span class="ss-brand-badge" aria-hidden="true">◆</span>
        <div class="ss-brand-text">
          <span class="ss-brand-title">SynthScan</span>
          <span class="ss-brand-subtitle">YOUR VERSE, CONNECTED</span>
        </div>
      </div>
      <nav class="ss-sidebar-nav" role="tablist" aria-label="Desktop Navigation">
        ${navHtml}
      </nav>
      <div class="ss-sidebar-footer">
        <div class="ss-sidebar-capture-badge" id="ss-capture-badge">
          <div class="ss-capture-status-line">
            <span class="ss-capture-indicator-dot"></span>
            <span class="ss-capture-status-text">READING GAME WINDOW</span>
          </div>
          <span class="ss-capture-subtext">LOCAL PROFILE · Records stay on this PC</span>
        </div>
        <button type="button" class="ss-nav-btn ss-exit-nav-btn" id="ss-sidebar-exit-btn">
          <svg class="ss-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
          </svg>
          <span class="ss-nav-label">Exit SynthScan</span>
        </button>
      </div>
    `;

    this.captureBadgeEl = this.sidebarEl.querySelector('#ss-capture-badge')!;

    // Bind sidebar clicks
    this.sidebarEl.querySelectorAll<HTMLButtonElement>('.ss-nav-btn[data-page]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const page = btn.dataset.page;
        if (page) {
          if (this.onNavigateRequested) {
            this.onNavigateRequested(page);
          }
          void this.bridge.sendCommand({ action: 'navigate', target: page });
        }
      });
    });

    const exitBtn = this.sidebarEl.querySelector('#ss-sidebar-exit-btn');
    if (exitBtn) {
      exitBtn.addEventListener('click', () => {
        void this.bridge.sendCommand({ action: 'open_dialog', target: 'exit' });
      });
    }
  }

  private buildViewsContainers(): void {
    // Inject non-people views placeholders if not present
    const viewsToInject = [
      { id: 'ss-view-directory', title: 'Item & Ship Finder' },
      { id: 'ss-view-mission-log', title: 'Mission & Wallet Log' },
      { id: 'ss-view-servers', title: 'Server History' },
      { id: 'ss-view-blueprints', title: 'Blueprint Library' },
      { id: 'ss-view-planner', title: 'Mining Planner' },
      { id: 'ss-view-diary', title: 'Mining Diary' },
      { id: 'ss-view-refinery', title: 'Refinery' },
      { id: 'ss-view-executive-hangar', title: 'Executive Hangar' },
      { id: 'ss-view-hud-piracy', title: 'Piracy' },
      { id: 'ss-view-daylight', title: 'Day/Night Forecast' },
      { id: 'ss-view-acceptance', title: 'Automatic Acceptance' },
    ];

    for (const v of viewsToInject) {
      if (!this.viewsContainerEl.querySelector(`#${v.id}`)) {
        const sec = document.createElement('section');
        sec.id = v.id;
        sec.className = 'ss-view';
        sec.hidden = true;
        this.viewsContainerEl.appendChild(sec);
      }
    }
  }

  private startTickLoop(): void {
    this.tickTimer = window.setInterval(() => {
      // 1s update for live countdowns (Refinery, Piracy, Executive Hangar)
      if (
        this.currentActivePage === 'refinery' ||
        this.currentActivePage === 'hud_piracy' ||
        this.currentActivePage === 'executive_hangar' ||
        this.currentActivePage === 'daylight'
      ) {
        this.renderActiveView();
      }
    }, 1000);
  }

  private renderCaptureBadge(): void {
    if (!this.captureBadgeEl) return;
    const status = this.desktopState?.capture_status ?? 'reading';
    const dot = this.captureBadgeEl.querySelector<HTMLElement>('.ss-capture-indicator-dot');
    const text = this.captureBadgeEl.querySelector<HTMLElement>('.ss-capture-status-text');
    if (dot && text) {
      if (status === 'paused') {
        dot.style.background = '#ffb05a';
        text.textContent = 'CAPTURE PAUSED';
      } else if (status === 'idle') {
        dot.style.background = '#98a3b3';
        text.textContent = 'CAPTURE IDLE · GAME ONLY';
      } else {
        dot.style.background = '#2de17a';
        text.textContent = 'READING GAME WINDOW';
      }
    }
  }

  private renderActiveView(): void {
    switch (this.currentActivePage) {
      case 'directory':
        this.renderDirectory();
        break;
      case 'mission_log':
        this.renderMissionLog();
        break;
      case 'servers':
        this.renderServers();
        break;
      case 'blueprints':
        this.renderBlueprints();
        break;
      case 'planner':
        this.renderPlanner();
        break;
      case 'diary':
        this.renderDiary();
        break;
      case 'refinery':
        this.renderRefinery();
        break;
      case 'executive_hangar':
        this.renderExecutiveHangar();
        break;
      case 'hud_piracy':
        this.renderPiracy();
        break;
      case 'daylight':
        this.renderDaylight();
        break;
      case 'acceptance':
        this.renderAcceptance();
        break;
    }
  }

  // --- Directory View ---
  private renderDirectory(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-directory');
    if (!el || el.hidden) return;

    const rows = this.catalog?.directory_rows ?? [];
    const kinds = Array.from(new Set(rows.map((r) => r.kind).filter(Boolean))) as string[];
    const filtered = rows.filter((r) => {
      if (this.directoryKind && r.kind !== this.directoryKind) return false;
      if (this.directoryQuery) {
        const q = this.directoryQuery.toLowerCase();
        return (
          r.name.toLowerCase().includes(q) ||
          (r.category && r.category.toLowerCase().includes(q)) ||
          (r.manufacturer && r.manufacturer.toLowerCase().includes(q))
        );
      }
      return true;
    });

    const kindOptions = ['<option value="">All Categories</option>']
      .concat(kinds.map((k) => `<option value="${k}" ${k === this.directoryKind ? 'selected' : ''}>${k}</option>`))
      .join('');

    const rowsHtml = filtered
      .slice(0, 100)
      .map(
        (r) => `
        <tr data-row-id="${r.id}" class="${r.id === this.directorySelectedId ? 'is-selected' : ''}">
          <td><strong>${r.name}</strong></td>
          <td>${r.kind ?? '—'}</td>
          <td>${r.category ?? '—'}</td>
          <td>${r.manufacturer ?? '—'}</td>
          <td>${r.price_buy ? `${r.price_buy.toLocaleString()} aUEC` : '—'}</td>
          <td>${r.location ?? 'Various'}</td>
        </tr>
      `,
      )
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="dir-search" class="ss-input ss-grow" type="text" placeholder="Search commodities, ships, weapons, armor..." value="${this.directoryQuery}" />
          <select id="dir-kind" class="ss-select">${kindOptions}</select>
          <span class="ss-muted-text">${filtered.length} matches</span>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr>
                <th>ITEM / SHIP</th>
                <th>KIND</th>
                <th>CATEGORY</th>
                <th>MANUFACTURER</th>
                <th>PRICE</th>
                <th>LOCATION</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml || '<tr><td colspan="6" class="ss-muted-text">No items matching criteria</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    const searchInput = el.querySelector<HTMLInputElement>('#dir-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        this.directoryQuery = searchInput.value;
        this.renderDirectory();
      });
    }

    const kindSelect = el.querySelector<HTMLSelectElement>('#dir-kind');
    if (kindSelect) {
      kindSelect.addEventListener('change', () => {
        this.directoryKind = kindSelect.value;
        this.renderDirectory();
      });
    }
  }

  // --- Mission & Wallet Log View ---
  private renderMissionLog(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-mission-log');
    if (!el || el.hidden) return;

    const missions = this.desktopState?.mission_log?.missions ?? [];
    const wallet = this.desktopState?.mission_log?.wallet_changes ?? [];
    const stats = this.desktopState?.mission_log?.stats ?? {
      total_completed: missions.filter((m) => m.status === 'completed').length,
      total_earned: missions.reduce((acc, m) => acc + (m.status === 'completed' ? m.payout : 0), 0),
      current_balance: 0,
    };

    const missionRows = missions
      .map(
        (m) => `
        <tr>
          <td><strong>${m.title}</strong></td>
          <td><span class="ss-badge ss-badge-${m.status}">${m.status}</span></td>
          <td>${m.category}</td>
          <td>${m.system}</td>
          <td>${m.payout.toLocaleString()} aUEC</td>
          <td>${m.completed_at ? new Date(m.completed_at * 1000).toLocaleTimeString() : 'In progress'}</td>
        </tr>
      `,
      )
      .join('');

    const walletRows = wallet
      .slice(0, 50)
      .map(
        (w) => `
        <tr>
          <td>${new Date(w.at * 1000).toLocaleTimeString()}</td>
          <td class="${w.amount >= 0 ? 'ss-income' : 'ss-expense'}">${w.amount >= 0 ? '+' : ''}${w.amount.toLocaleString()} aUEC</td>
          <td>${w.category}</td>
          <td>${w.note ?? '—'}</td>
        </tr>
      `,
      )
      .join('');

    el.innerHTML = `
      <div class="ss-log-grid">
        <div class="ss-card">
          <div class="ss-toolbar-row ss-space-between">
            <h2 class="ss-section-heading">CONTRACTS &amp; MISSIONS</h2>
            <div class="ss-toolbar-actions">
              <button id="ml-export-csv" class="ss-btn ss-btn-sm">Export CSV</button>
              <button id="ml-export-json" class="ss-btn ss-btn-sm">Export JSON</button>
            </div>
          </div>
          <div class="ss-stats-strip">
            <div class="ss-stat-chip"><strong>${stats.total_completed}</strong> completed</div>
            <div class="ss-stat-chip"><strong>${stats.total_earned.toLocaleString()} aUEC</strong> total earned</div>
          </div>
          <div class="ss-table-scroll ss-log-scroll">
            <table class="ss-table">
              <thead><tr><th>CONTRACT</th><th>STATUS</th><th>CATEGORY</th><th>SYSTEM</th><th>PAYOUT</th><th>TIME</th></tr></thead>
              <tbody>${missionRows || '<tr><td colspan="6" class="ss-muted-text">No mission logs recorded</td></tr>'}</tbody>
            </table>
          </div>
        </div>
        <div class="ss-card">
          <h2 class="ss-section-heading">WALLET TRANSACTIONS</h2>
          <div class="ss-table-scroll ss-log-scroll">
            <table class="ss-table">
              <thead><tr><th>TIME</th><th>AMOUNT</th><th>CATEGORY</th><th>NOTE</th></tr></thead>
              <tbody>${walletRows || '<tr><td colspan="4" class="ss-muted-text">No balance changes logged</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    el.querySelector('#ml-export-csv')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'mission_export', format: 'csv' });
    });
    el.querySelector('#ml-export-json')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'mission_export', format: 'json' });
    });
  }

  // --- Servers View ---
  private renderServers(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-servers');
    if (!el || el.hidden) return;

    const entries = this.desktopState?.servers?.entries ?? [];
    const currentShard = this.desktopState?.server?.shard_id ?? 'Unknown';
    const currentRegion = this.desktopState?.server?.region ?? 'US-East';

    const rows = entries
      .map((s) => {
        const isCurrent = s.shard_id === currentShard;
        return `
        <tr class="${isCurrent ? 'is-selected' : ''}">
          <td><strong>Shard ${s.shard_id}</strong> ${isCurrent ? '<span class="ss-tag ss-tag-accent">Current</span>' : ''}</td>
          <td>${s.region}</td>
          <td>${s.visit_count}</td>
          <td>${new Date(s.last_seen * 1000).toLocaleString()}</td>
          <td>${s.custom_name ?? '—'}</td>
          <td>${s.notes ?? '—'}</td>
        </tr>
      `;
      })
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">SERVER &amp; SHARD HISTORY</h2>
            <p class="ss-muted-text">Active connection: <strong>Shard ${currentShard}</strong> · ${currentRegion}</p>
          </div>
          <button id="server-refresh-btn" class="ss-btn ss-btn-accent">Refresh shard</button>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>SHARD ID</th><th>REGION</th><th>VISITS</th><th>LAST OBSERVED</th><th>LABEL</th><th>NOTES</th></tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" class="ss-muted-text">No server history available</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `;

    el.querySelector('#server-refresh-btn')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'refresh_people' });
    });
  }

  // --- Blueprint Library View ---
  private renderBlueprints(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-blueprints');
    if (!el || el.hidden) return;

    const blueprints = this.catalog?.blueprints ?? [];
    const types = this.catalog?.blueprint_types ?? [];
    const ownedSet = new Set(this.desktopState?.blueprints?.owned ?? []);

    const filtered = blueprints.filter((b) => {
      if (this.blueprintType && b.type !== this.blueprintType) return false;
      if (this.blueprintQuery) {
        const q = this.blueprintQuery.toLowerCase();
        return b.name.toLowerCase().includes(q);
      }
      return true;
    });

    const typeOptions = ['<option value="">All Types</option>']
      .concat(types.map((t) => `<option value="${t}" ${t === this.blueprintType ? 'selected' : ''}>${t}</option>`))
      .join('');

    const cards = filtered
      .slice(0, 100)
      .map((b) => {
        const isOwned = ownedSet.has(b.name);
        const slotsText = b.slots
          .map((s) => `${s.material_name} (${s.scu ? `${s.scu} SCU` : `${s.units} units`})`)
          .join(', ');
        return `
        <div class="ss-bp-card ${isOwned ? 'is-owned' : ''}">
          <div class="ss-bp-header">
            <div>
              <h3 class="ss-bp-title">${b.name}</h3>
              <span class="ss-bp-type">${b.type} · Grade ${b.grade || 'Standard'}</span>
            </div>
            <label class="ss-checkbox-label">
              <input type="checkbox" data-bp-index="${b.id}" ${isOwned ? 'checked' : ''} />
              <span>Owned</span>
            </label>
          </div>
          <div class="ss-bp-materials">
            <span class="ss-label-sm">Materials:</span>
            <span class="ss-bp-materials-list">${slotsText || 'Standard crafting bench components'}</span>
          </div>
        </div>
      `;
      })
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="bp-search" class="ss-input ss-grow" type="text" placeholder="Search crafting recipes and materials..." value="${this.blueprintQuery}" />
          <select id="bp-type" class="ss-select">${typeOptions}</select>
          <span class="ss-muted-text">${ownedSet.size} of ${blueprints.length} owned</span>
        </div>
        <div class="ss-bp-grid">
          ${cards || '<div class="ss-muted-text">No blueprints match your filter</div>'}
        </div>
      </div>
    `;

    el.querySelector('#bp-search')?.addEventListener('input', (e) => {
      this.blueprintQuery = (e.target as HTMLInputElement).value;
      this.renderBlueprints();
    });

    el.querySelector('#bp-type')?.addEventListener('change', (e) => {
      this.blueprintType = (e.target as HTMLSelectElement).value;
      this.renderBlueprints();
    });

    el.querySelectorAll<HTMLInputElement>('input[data-bp-index]').forEach((cb) => {
      cb.addEventListener('change', () => {
        const idx = Number(cb.dataset.bpIndex);
        void this.bridge.sendCommand({ action: 'toggle_blueprint_owned', blueprint_index: idx });
      });
    });
  }

  // --- Mining Planner View ---
  private renderPlanner(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-planner');
    if (!el || el.hidden) return;

    const locations = this.catalog?.mining_locations ?? [];
    const filtered = locations.filter((loc) => {
      if (this.plannerFamily && loc.family !== this.plannerFamily) return false;
      if (this.plannerSystem && loc.system !== this.plannerSystem) return false;
      if (this.plannerQuery) {
        const q = this.plannerQuery.toLowerCase();
        return loc.mineral.toLowerCase().includes(q) || loc.location.toLowerCase().includes(q);
      }
      return true;
    });

    const rows = filtered
      .map(
        (loc) => `
        <tr>
          <td><strong>${loc.mineral}</strong></td>
          <td><span class="ss-tag ss-tag-accent">${loc.family}</span></td>
          <td>${loc.location}</td>
          <td>${loc.system}</td>
          <td>${loc.kind}</td>
          <td><strong>${loc.chance.toFixed(1)}%</strong></td>
          <td>${loc.note || '—'}</td>
        </tr>
      `,
      )
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="planner-search" class="ss-input ss-grow" type="text" placeholder="Filter mineral (e.g. Agricium, Quantainium, Bexalite, Gold)..." value="${this.plannerQuery}" />
          <div class="ss-segmented">
            <button class="ss-btn ${this.plannerFamily === 'Ship' ? 'is-active' : ''}" data-fam="Ship">Ship</button>
            <button class="ss-btn ${this.plannerFamily === 'ROC' ? 'is-active' : ''}" data-fam="ROC">ROC</button>
            <button class="ss-btn ${this.plannerFamily === 'FPS' ? 'is-active' : ''}" data-fam="FPS">FPS</button>
          </div>
          <select id="planner-system" class="ss-select">
            <option value="" ${this.plannerSystem === '' ? 'selected' : ''}>All Systems</option>
            <option value="Stanton" ${this.plannerSystem === 'Stanton' ? 'selected' : ''}>Stanton</option>
            <option value="Pyro" ${this.plannerSystem === 'Pyro' ? 'selected' : ''}>Pyro</option>
            <option value="Nyx" ${this.plannerSystem === 'Nyx' ? 'selected' : ''}>Nyx</option>
          </select>
          <span class="ss-muted-text">${filtered.length} locations</span>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>MINERAL</th><th>METHOD</th><th>LOCATION</th><th>SYSTEM</th><th>TYPE</th><th>DEPOSIT CHANCE</th><th>NOTES</th></tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="7" class="ss-muted-text">No deposit locations match your criteria</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `;

    el.querySelector('#planner-search')?.addEventListener('input', (e) => {
      this.plannerQuery = (e.target as HTMLInputElement).value;
      this.renderPlanner();
    });

    el.querySelectorAll<HTMLButtonElement>('[data-fam]').forEach((b) => {
      b.addEventListener('click', () => {
        this.plannerFamily = b.dataset.fam || 'Ship';
        this.renderPlanner();
      });
    });

    el.querySelector('#planner-system')?.addEventListener('change', (e) => {
      this.plannerSystem = (e.target as HTMLSelectElement).value;
      this.renderPlanner();
    });
  }

  // --- Mining Diary View ---
  private renderDiary(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-diary');
    if (!el || el.hidden) return;

    const entries = this.desktopState?.diary?.entries ?? [];
    const autoLog = this.desktopState?.diary?.auto_log ?? true;

    const rows = entries
      .map(
        (e) => `
        <tr>
          <td>${new Date(e.timestamp * 1000).toLocaleString()}</td>
          <td>${e.system} / ${e.body}</td>
          <td>${e.ship}</td>
          <td>${e.ores.map((o) => `${o.name} (${o.scu} SCU)`).join(', ') || '—'}</td>
          <td><strong>${e.total_value ? `${e.total_value.toLocaleString()} aUEC` : '—'}</strong></td>
          <td>${e.notes ?? '—'}</td>
        </tr>
      `,
      )
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">MINING RUN DIARY</h2>
            <p class="ss-muted-text">Logs ore signatures, hauls, break metrics, and profits locally.</p>
          </div>
          <div class="ss-toolbar-actions">
            <label class="ss-checkbox-label">
              <input id="diary-auto-log" type="checkbox" ${autoLog ? 'checked' : ''} />
              <span>Auto-log completed runs</span>
            </label>
            <button id="diary-share-btn" class="ss-btn ss-btn-accent">Share summary</button>
          </div>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>DATE / TIME</th><th>LOCATION</th><th>VESSEL</th><th>ORES COLLECTED</th><th>HAUL VALUE</th><th>NOTES</th></tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" class="ss-muted-text">No recorded mining runs yet. Scan and extract ore to log entries automatically.</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `;

    el.querySelector('#diary-auto-log')?.addEventListener('change', (e) => {
      const checked = (e.target as HTMLInputElement).checked;
      void this.bridge.sendCommand({ action: 'diary_auto_log', auto_log: checked });
    });
  }

  // --- Refinery View ---
  private renderRefinery(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-refinery');
    if (!el || el.hidden) return;

    const orders = this.desktopState?.refinery?.orders ?? [];
    const now = Math.floor(Date.now() / 1000);

    const rows = orders
      .map((ord, idx) => {
        const remaining = Math.max(0, ord.due - now);
        const hours = Math.floor(remaining / 3600);
        const minutes = Math.floor((remaining % 3600) / 60);
        const seconds = remaining % 60;
        const timeStr =
          remaining === 0
            ? '<span class="ss-badge ss-badge-completed">READY TO COLLECT</span>'
            : `${hours}h ${minutes.toString().padStart(2, '0')}m ${seconds.toString().padStart(2, '0')}s remaining`;

        const partsStr = ord.parts.map((p) => `${p.material}: ${p.yield} cSCU`).join(', ');

        return `
        <tr>
          <td><strong>#${ord.number}</strong></td>
          <td>${ord.station}</td>
          <td>${ord.method || 'Standard'}</td>
          <td>${partsStr}</td>
          <td>${timeStr}</td>
          <td>
            ${
              remaining === 0
                ? `<button class="ss-btn ss-btn-accent ss-btn-sm" data-collect-order="${idx}">Collect</button>`
                : '<span class="ss-muted-text">Processing</span>'
            }
          </td>
        </tr>
      `;
      })
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">ACTIVE REFINERY ORDERS</h2>
            <p class="ss-muted-text">Automatically recorded from refinery terminal quote and processing panels.</p>
          </div>
          <button id="refinery-dismiss-btn" class="ss-btn">Dismiss alerts</button>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>ORDER</th><th>STATION</th><th>METHOD</th><th>YIELDS</th><th>COUNTDOWN</th><th>ACTION</th></tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" class="ss-muted-text">No active refinery orders being tracked</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `;

    el.querySelectorAll<HTMLButtonElement>('[data-collect-order]').forEach((b) => {
      b.addEventListener('click', () => {
        const orderIdx = Number(b.dataset.collectOrder);
        void this.bridge.sendCommand({ action: 'refinery_collected', order_index: orderIdx });
      });
    });

    el.querySelector('#refinery-dismiss-btn')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'dismiss_refinery' });
    });
  }

  // --- Executive Hangar View ---
  private renderExecutiveHangar(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-executive-hangar');
    if (!el || el.hidden) return;

    const hangar = this.desktopState?.executive_hangar ?? {};
    const timer = hangar.timer_seconds ?? 0;
    const ships = hangar.ships ?? [
      { name: 'RSI Perseus', bay: 'Bay 01', ready: true },
      { name: 'Anvil Carrack', bay: 'Bay 02', ready: true },
      { name: 'Aegis Eclipse', bay: 'Bay 03', ready: false, recall_seconds: timer },
    ];

    const cards = ships
      .map(
        (s) => `
        <div class="ss-hangar-card ${s.ready ? 'is-ready' : ''}">
          <div class="ss-hangar-top">
            <span class="ss-hangar-bay">${s.bay}</span>
            <span class="ss-badge ${s.ready ? 'ss-badge-completed' : 'ss-badge-pending'}">${s.ready ? 'READY' : 'IN RECALL'}</span>
          </div>
          <h3 class="ss-hangar-ship">${s.name}</h3>
          <div class="ss-hangar-actions">
            ${
              s.ready
                ? '<button class="ss-btn ss-btn-accent ss-btn-sm" data-hangar-act="recall">Depart Bay</button>'
                : `<span class="ss-muted-text">Arrives in ${s.recall_seconds ?? 0}s</span>`
            }
          </div>
        </div>
      `,
      )
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">EXECUTIVE HANGAR CONTROL</h2>
            <p class="ss-muted-text">Docking bay status, automated recall tracking, and departure sequencing.</p>
          </div>
          <button id="hangar-hud-btn" class="ss-btn ss-btn-accent">Open Hangar HUD</button>
        </div>
        <div class="ss-hangar-grid">
          ${cards}
        </div>
      </div>
    `;

    el.querySelector('#hangar-hud-btn')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'hud_mode', target: 'hud_hangars' });
    });
  }

  // --- Piracy View ---
  private renderPiracy(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-hud-piracy');
    if (!el || el.hidden) return;

    const piracy = this.desktopState?.piracy ?? {};
    const waitActive = piracy.wait_active ?? false;
    const waitSec = piracy.wait_seconds ?? 0;
    const snareAlerts = piracy.snare_alerts ?? true;

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">PIRACY &amp; INTERDICTION CONTROL</h2>
            <p class="ss-muted-text">Monitor quantum snare traps, interdiction cooldowns, and cargo hold yields.</p>
          </div>
          <button id="piracy-hud-btn" class="ss-btn ss-btn-accent">Open Piracy HUD</button>
        </div>
        <div class="ss-piracy-dashboard">
          <div class="ss-subcard">
            <h3>Quantum Snare Wait Timer</h3>
            <div class="ss-big-timer">${Math.floor(waitSec / 60)}m ${(waitSec % 60).toString().padStart(2, '0')}s</div>
            <div class="ss-toolbar-row">
              <button id="piracy-wait-toggle" class="ss-btn ${waitActive ? 'ss-btn-accent' : ''}">${waitActive ? 'Pause Timer' : 'Start Timer'}</button>
              <button id="piracy-wait-reset" class="ss-btn">Reset</button>
            </div>
          </div>
          <div class="ss-subcard">
            <h3>Snare Alerts &amp; Interdictions</h3>
            <label class="ss-checkbox-label">
              <input id="piracy-snare-toggle" type="checkbox" ${snareAlerts ? 'checked' : ''} />
              <span>Enable audio/visual HUD alerts on snare interdiction</span>
            </label>
          </div>
        </div>
      </div>
    `;

    el.querySelector('#piracy-hud-btn')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'hud_mode', target: 'hud_piracy' });
    });

    el.querySelector('#piracy-wait-toggle')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'piracy_action', sub_action: 'toggle_wait' });
    });

    el.querySelector('#piracy-wait-reset')?.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'piracy_action', sub_action: 'reset_wait' });
    });

    el.querySelector('#piracy-snare-toggle')?.addEventListener('change', (e) => {
      const enabled = (e.target as HTMLInputElement).checked;
      void this.bridge.sendCommand({ action: 'piracy_action', sub_action: 'snare_alerts', enabled });
    });
  }

  // --- Daylight View ---
  private renderDaylight(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-daylight');
    if (!el || el.hidden) return;

    const daylightData = this.catalog?.daylight;
    const systems = daylightData?.systems ? Object.keys(daylightData.systems) : ['Stanton', 'Pyro', 'Nyx'];
    const currentSys = daylightData?.systems?.[this.daylightSystem];
    const bodies = currentSys?.bodies ?? [];

    if (!this.daylightBodyName && bodies.length > 0) {
      this.daylightBodyName = bodies[0].name;
    }

    const currentBody = bodies.find((b) => b.name === this.daylightBodyName) ?? bodies[0];
    const sites = currentBody?.sites ?? [];
    if (!this.daylightSiteName && sites.length > 0) {
      this.daylightSiteName = sites[0].name;
    }
    const currentSite = sites.find((s) => s.name === this.daylightSiteName) ?? sites[0];

    const nowSec = Date.now() / 1000;
    const forecast =
      currentBody && currentSite
        ? calculateDaylight(currentBody, currentSite, nowSec)
        : { daylight: true, altitude_degrees: 42 };

    const sysOptions = systems
      .map((s) => `<option value="${s}" ${s === this.daylightSystem ? 'selected' : ''}>${s}</option>`)
      .join('');

    const bodyOptions = bodies
      .map((b) => `<option value="${b.name}" ${b.name === this.daylightBodyName ? 'selected' : ''}>${b.name}</option>`)
      .join('');

    const siteOptions = sites
      .map((s) => `<option value="${s.name}" ${s.name === this.daylightSiteName ? 'selected' : ''}>${s.name}</option>`)
      .join('');

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">DAY / NIGHT SOLAR FORECAST</h2>
            <p class="ss-muted-text">Real-time solar geometry and terminator line tracking for planetary surface approaches.</p>
          </div>
          <span class="ss-badge ${forecast.daylight ? 'ss-badge-completed' : 'ss-badge-pending'}">
            ${forecast.daylight ? '☀ SUNLIT (DAY)' : '☾ IN SHADOW (NIGHT)'}
          </span>
        </div>
        <div class="ss-toolbar-row">
          <label class="ss-inline-field">System: <select id="dl-sys" class="ss-select">${sysOptions}</select></label>
          <label class="ss-inline-field">Body: <select id="dl-body" class="ss-select">${bodyOptions}</select></label>
          <label class="ss-inline-field">Surface Outpost: <select id="dl-site" class="ss-select">${siteOptions}</select></label>
        </div>
        <div class="ss-daylight-info">
          <div class="ss-subcard">
            <h3>Solar Altitude</h3>
            <div class="ss-big-timer">${forecast.altitude_degrees}°</div>
            <p class="ss-muted-text">${forecast.daylight ? 'Above horizon' : 'Below horizon'}</p>
          </div>
          <div class="ss-subcard">
            <h3>Surface Site Details</h3>
            <p><strong>Site:</strong> ${currentSite?.name ?? '—'}</p>
            <p><strong>Body Radius:</strong> ${currentBody?.radius_km ?? 0} km</p>
            <p><strong>Rotation Period:</strong> ${Math.round(Math.abs(currentBody?.period_seconds ?? 0) / 3600)}h</p>
          </div>
        </div>
      </div>
    `;

    el.querySelector('#dl-sys')?.addEventListener('change', (e) => {
      this.daylightSystem = (e.target as HTMLSelectElement).value;
      this.daylightBodyName = '';
      this.daylightSiteName = '';
      this.renderDaylight();
    });

    el.querySelector('#dl-body')?.addEventListener('change', (e) => {
      this.daylightBodyName = (e.target as HTMLSelectElement).value;
      this.daylightSiteName = '';
      this.renderDaylight();
    });

    el.querySelector('#dl-site')?.addEventListener('change', (e) => {
      this.daylightSiteName = (e.target as HTMLSelectElement).value;
      this.renderDaylight();
    });
  }

  // --- Automatic Acceptance View ---
  private renderAcceptance(): void {
    const el = this.viewsContainerEl.querySelector<HTMLElement>('#ss-view-acceptance');
    if (!el || el.hidden) return;

    const acc = this.desktopState?.acceptance ?? {};
    const party = acc.party_enabled ?? true;
    const friend = acc.friend_enabled ?? true;
    const hideChat = acc.hide_global_chat ?? false;

    el.innerHTML = `
      <div class="ss-card ss-fill-pane">
        <h2 class="ss-section-heading">AUTOMATIC INVITATION ACCEPTANCE</h2>
        <p class="ss-muted-text">Hands-free handling of incoming requests while piloting or mining.</p>
        <div class="ss-settings-col">
          <label class="ss-checkbox-label">
            <input id="acc-party" type="checkbox" ${party ? 'checked' : ''} />
            <span>Automatically accept party invitations from recognized friends &amp; org members</span>
          </label>
          <label class="ss-checkbox-label">
            <input id="acc-friend" type="checkbox" ${friend ? 'checked' : ''} />
            <span>Automatically accept incoming friend requests</span>
          </label>
          <label class="ss-checkbox-label">
            <input id="acc-hide-chat" type="checkbox" ${hideChat ? 'checked' : ''} />
            <span>Hide global chat messages automatically upon entering session</span>
          </label>
          <div class="ss-toolbar-row">
            <button id="acc-save-btn" class="ss-btn ss-btn-accent">Save Settings</button>
          </div>
        </div>
      </div>
    `;

    el.querySelector('#acc-save-btn')?.addEventListener('click', () => {
      const p = el.querySelector<HTMLInputElement>('#acc-party')?.checked ?? true;
      const f = el.querySelector<HTMLInputElement>('#acc-friend')?.checked ?? true;
      const c = el.querySelector<HTMLInputElement>('#acc-hide-chat')?.checked ?? false;
      void this.bridge.sendCommand({
        action: 'save_acceptance',
        party_enabled: p,
        friend_enabled: f,
        hide_global_chat: c,
      });
    });
  }
}
