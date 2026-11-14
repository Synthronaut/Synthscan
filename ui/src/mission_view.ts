import type {
  DesktopBridge,
  MissionAnalyticsFaction,
  MissionAnalyticsPromotion,
  MissionLogEntry,
  MissionLogSession,
  MissionLogState,
} from './bridge';

const PALETTE = ['#62ccff', '#53d09f', '#f6b95e', '#c58cff', '#ff8a8f', '#5fd6d0', '#e5d26b', '#7f9bff'];

const MODES: [string, string][] = [
  ['all', 'All activity'],
  ['missions', 'Missions'],
  ['rewards', 'Mission rewards'],
  ['wallet', 'aUEC ledger'],
  ['reputation', 'Reputation'],
  ['sessions', 'Session recaps'],
];

const CATEGORY_OPTIONS: [string, string][] = [
  ['', 'All wallet categories'],
  ['unclassified', 'Unclassified'],
  ['mission_reward', 'Mission reward'],
  ['player_transfer', 'Player transfer'],
  ['repair', 'Repairs'],
  ['refuel', 'Refueling'],
  ['store_purchase', 'Store purchase'],
  ['vehicle_purchase', 'Vehicle / equipment'],
  ['cargo_trade', 'Cargo trading'],
  ['fees', 'Fees / fines'],
  ['other', 'Other'],
];

export function escapeHtml(text: unknown): string {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function colorFor(name: string): string {
  let hash = 2166136261;
  for (let i = 0; i < name.length; i += 1) {
    hash ^= name.charCodeAt(i);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

export function formatAuecSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const rounded = Math.round(value);
  return `${rounded > 0 ? '+' : ''}${rounded.toLocaleString('en-US')}`;
}

export function formatAuecPlain(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return Math.round(value).toLocaleString('en-US');
}

export function formatSpan(seconds: number): string {
  const total = Math.max(0, Math.round(seconds / 60));
  if (total < 60) return `${total}m`;
  return `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m`;
}

function stamp(at: number | null | undefined): string {
  if (!at) return 'Unknown';
  const d = new Date(at * 1000);
  const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
  return `${date} · ${time}`;
}

export interface SessionDivider {
  kind: 'divider';
  key: string;
  session: string;
  label: string;
  detail: string;
  live: boolean;
}

export interface LedgerEntryRow {
  kind: 'entry';
  entry: MissionLogEntry;
}

export type LedgerRow = SessionDivider | LedgerEntryRow;

/** Insert one divider whenever the play session changes between consecutive entries. */
export function groupBySession(
  entries: MissionLogEntry[],
  sessions: MissionLogSession[],
  currentSession: string,
): LedgerRow[] {
  const byId = new Map(sessions.map((s) => [s.id, s]));
  const rows: LedgerRow[] = [];
  let previous: string | null = null;
  for (const entry of entries) {
    const id = entry.session ?? '';
    if (previous === null || id !== previous) {
      const meta = byId.get(id);
      let label = 'Outside a tracked session';
      let detail = 'Activity not tied to a recorded play session';
      if (meta) {
        const live = id === currentSession && !meta.ended_at;
        const end = meta.ended_at ?? 0;
        const span = end && meta.started_at ? ` · ${formatSpan(end - meta.started_at)}` : live ? ' · in progress' : '';
        label = `Session · ${stamp(meta.started_at)}${span}`;
        const auec = (meta.wallet ?? []).filter((w) => w.currency === 'AUEC' && w.delta !== null);
        const net = auec.reduce((acc, w) => acc + (w.delta ?? 0), 0);
        const parts = [`${meta.completed ?? 0} completed`];
        if (meta.failed) parts.push(`${meta.failed} failed`);
        if (meta.abandoned) parts.push(`${meta.abandoned} abandoned`);
        if (auec.length) parts.push(`aUEC ${formatAuecSigned(net)}`);
        detail = parts.join(' · ');
      }
      rows.push({
        kind: 'divider',
        key: `divider:${id}:${rows.length}`,
        session: id,
        label,
        detail,
        live: Boolean(meta && id === currentSession && !meta.ended_at),
      });
      previous = id;
    }
    rows.push({ kind: 'entry', entry });
  }
  return rows;
}

export interface MissionViewOptions {
  onNotice?: (msg: string) => void;
}

export class MissionViewController {
  private readonly container: HTMLElement;
  private readonly bridge: DesktopBridge;
  private readonly options: MissionViewOptions;

  private state: MissionLogState = {};
  private selectedId = '';
  private requested = false;

  private mode = 'all';
  private outcome = '';
  private direction = '';
  private category = '';
  private currentOnly = false;
  private query = '';

  private detailVisible = false;

  private kpiEl!: HTMLElement;
  private promotionsEl!: HTMLElement;
  private factionEl!: HTMLElement;
  private dailyEl!: HTMLElement;
  private sessionChartEl!: HTMLElement;
  private balanceHistoryEl!: HTMLElement;
  private noteEl!: HTMLElement;
  private theadEl!: HTMLElement;
  private tbodyEl!: HTMLElement;
  private detailEl!: HTMLElement;
  private pagerEl!: HTMLElement;
  private classifyRowEl!: HTMLElement;
  private classifySelectEl!: HTMLSelectElement;
  private searchEl!: HTMLInputElement;
  private modeEl!: HTMLSelectElement;
  private outcomeEl!: HTMLSelectElement;
  private sessionEl!: HTMLSelectElement;
  private directionEl!: HTMLSelectElement;
  private categoryFilterEl!: HTMLSelectElement;
  private prevBtn!: HTMLButtonElement;
  private nextBtn!: HTMLButtonElement;

  constructor(container: HTMLElement, bridge: DesktopBridge, options: MissionViewOptions = {}) {
    this.container = container;
    this.bridge = bridge;
    this.options = options;
    this.buildDom();
    this.bindEvents();
    this.render();
  }

  public destroy(): void {
    // no timers or global listeners
  }

  /** Called when the page becomes visible so the backend publishes the default view once. */
  public activate(): void {
    if (this.requested) return;
    this.requested = true;
    this.sendView(0);
  }

  public updateFromState(next: MissionLogState | undefined): void {
    this.state = next ?? {};
    this.render();
  }

  private option(value: string, label: string): string {
    return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
  }

  private buildDom(): void {
    this.container.innerHTML = `
      <div class="ss-mission-root">
        <div id="mission-kpis" class="ss-mission-kpis"></div>

        <div class="ss-card ss-mission-balance-card">
          <div class="ss-card-title-row">
            <h2 class="ss-section-heading">WALLET BALANCE HISTORY</h2>
            <span class="ss-hint-line">Observed aUEC balance from wallet reads</span>
          </div>
          <div id="mission-balance-history" class="ss-chart-box ss-chart-balance"></div>
        </div>

        <div id="mission-promotions-banner" class="ss-mission-promotions-banner" style="display:none"></div>

        <div class="ss-mission-analytics">
          <div class="ss-card ss-mission-faction-card">
            <div class="ss-card-title-row">
              <h2 class="ss-section-heading">FACTIONS & REPUTATION STANDING</h2>
              <span class="ss-hint-line">Earnings, standings, and next rank progression</span>
            </div>
            <div id="mission-factions" class="ss-faction-bars"></div>
          </div>
          <div class="ss-card ss-mission-daily-card">
            <div class="ss-card-title-row">
              <h2 class="ss-section-heading">DAILY aUEC FLOW</h2>
              <span class="ss-hint-line">Gains above, spending below</span>
            </div>
            <div id="mission-daily" class="ss-chart-box"></div>
            <div id="mission-sessions-chart" class="ss-chart-box ss-chart-short"></div>
          </div>
        </div>

        <p id="mission-note" class="ss-hint-line ss-mission-note"></p>

        <div class="ss-card ss-ledger-card">
          <div class="ss-toolbar-row ss-ledger-toolbar">
            <input id="mission-search" class="ss-input ss-grow" type="text" placeholder="Search missions, organizations or activity" autocomplete="off" />
            <button id="mission-search-btn" type="button" class="ss-btn ss-btn-accent">Search</button>
            <select id="mission-mode" class="ss-select" aria-label="Ledger view">${MODES.map(([v, l]) => this.option(v, l)).join('')}</select>
            <select id="mission-outcome" class="ss-select" aria-label="Outcome">${[
              ['', 'All outcomes'],
              ['completed', 'Completed'],
              ['failed', 'Failed / other'],
              ['abandoned', 'Abandoned'],
              ['active', 'Active'],
            ].map(([v, l]) => this.option(v, l)).join('')}</select>
            <select id="mission-session-filter" class="ss-select" aria-label="Session">${this.option('all', 'All sessions')}${this.option('current', 'This session')}</select>
            <select id="mission-direction" class="ss-select" aria-label="Direction">${[
              ['', 'All changes'],
              ['gains', 'Gains'],
              ['losses', 'Losses'],
            ].map(([v, l]) => this.option(v, l)).join('')}</select>
            <select id="mission-category-filter" class="ss-select" aria-label="Wallet category">${CATEGORY_OPTIONS.map(([v, l]) => this.option(v, l)).join('')}</select>
          </div>
          <div id="mission-ledger-body" class="ss-ledger-body">
            <div class="ss-table-scroll ss-ledger-scroll" tabindex="0" role="region" aria-label="Mission and wallet ledger">
              <table class="ss-table ss-ledger-table">
                <thead id="mission-thead"></thead>
                <tbody id="mission-tbody"></tbody>
              </table>
            </div>
            <div id="mission-detail-pane" class="ss-ledger-detail-pane" hidden>
              <pre id="mission-detail" class="ss-ledger-detail">Select an activity to inspect its evidence.</pre>
              <div id="mission-classify-row" class="ss-toolbar-row ss-toolbar-sub" hidden>
                <span class="ss-field-label">Classify this wallet change</span>
                <select id="mission-classify-select" class="ss-select ss-grow" aria-label="Classify wallet change">${CATEGORY_OPTIONS.slice(1).map(([v, l]) => this.option(v, l)).join('')}</select>
              </div>
            </div>
          </div>
          <div class="ss-toolbar-row ss-ledger-footer">
            <button id="mission-prev-btn" type="button" class="ss-btn">Previous</button>
            <button id="mission-next-btn" type="button" class="ss-btn">Next</button>
            <span id="mission-pager" class="ss-hint-line ss-grow"></span>
            <button id="mission-evidence-btn" type="button" class="ss-btn">Evidence ›</button>
            <button type="button" class="ss-btn" data-mission-export="csv">Export CSV</button>
            <button type="button" class="ss-btn" data-mission-export="json">Export JSON</button>
            <button type="button" class="ss-btn ss-btn-accent" data-mission-export="html">Export report</button>
          </div>
        </div>
      </div>
    `;
    const q = <T extends HTMLElement>(sel: string): T => this.container.querySelector(sel) as T;
    this.kpiEl = q('#mission-kpis');
    this.promotionsEl = q('#mission-promotions-banner');
    this.factionEl = q('#mission-factions');
    this.dailyEl = q('#mission-daily');
    this.sessionChartEl = q('#mission-sessions-chart');
    this.balanceHistoryEl = q('#mission-balance-history');
    this.noteEl = q('#mission-note');
    this.theadEl = q('#mission-thead');
    this.tbodyEl = q('#mission-tbody');
    this.detailEl = q('#mission-detail');
    this.pagerEl = q('#mission-pager');
    this.classifyRowEl = q('#mission-classify-row');
    this.classifySelectEl = q('#mission-classify-select');
    this.searchEl = q('#mission-search');
    this.modeEl = q('#mission-mode');
    this.outcomeEl = q('#mission-outcome');
    this.sessionEl = q('#mission-session-filter');
    this.directionEl = q('#mission-direction');
    this.categoryFilterEl = q('#mission-category-filter');
    this.prevBtn = q('#mission-prev-btn');
    this.nextBtn = q('#mission-next-btn');
  }

  private sendView(offset: number): void {
    void this.bridge.sendCommand({
      action: 'mission_view',
      query: this.query,
      mode: this.mode,
      outcome: this.outcome,
      direction: this.direction,
      category: this.category,
      current_session: this.currentOnly,
      offset: Math.max(0, offset),
    });
  }

  private bindEvents(): void {
    const apply = () => {
      this.query = this.searchEl.value.trim();
      this.mode = this.modeEl.value || 'all';
      this.outcome = this.outcomeEl.value;
      this.direction = this.directionEl.value;
      this.category = this.categoryFilterEl.value;
      this.currentOnly = this.sessionEl.value === 'current';
      this.requested = true;
      this.sendView(0);
    };
    this.container.querySelector('#mission-search-btn')!.addEventListener('click', apply);
    for (const el of [this.modeEl, this.outcomeEl, this.sessionEl, this.directionEl, this.categoryFilterEl]) {
      el.addEventListener('change', apply);
    }
    this.searchEl.addEventListener('keydown', (ev) => {
      if ((ev as KeyboardEvent).key === 'Enter') apply();
    });
    this.prevBtn.addEventListener('click', () => {
      const limit = this.state.display_limit ?? 100;
      this.sendView((this.state.display_offset ?? 0) - limit);
    });
    this.nextBtn.addEventListener('click', () => {
      const limit = this.state.display_limit ?? 100;
      this.sendView((this.state.display_offset ?? 0) + limit);
    });
    this.tbodyEl.addEventListener('click', (ev) => {
      const tr = (ev.target as HTMLElement).closest<HTMLElement>('tr[data-entry-id]');
      if (!tr) return;
      const clickedId = tr.dataset.entryId ?? '';
      if (clickedId !== this.selectedId) {
        this.selectedId = clickedId;
        // Auto-open the evidence pane when a new row is clicked
        this.setDetailVisible(true);
      } else {
        // Clicking the same row again toggles the pane
        this.setDetailVisible(!this.detailVisible);
      }
      this.render();
    });
    // Evidence toggle button in the footer
    this.container.querySelector('#mission-evidence-btn')!.addEventListener('click', () => {
      this.setDetailVisible(!this.detailVisible);
      this.render();
    });
    this.classifySelectEl.addEventListener('change', () => {
      const entry = this.selectedEntry();
      if (!entry?.is_wallet || !entry.change_id) return;
      void this.bridge.sendCommand({
        action: 'mission_classify',
        change_id: entry.change_id,
        category: this.classifySelectEl.value,
      });
      this.options.onNotice?.('Wallet category saved as a player classification.');
    });
    for (const btn of Array.from(this.container.querySelectorAll<HTMLButtonElement>('button[data-mission-export]'))) {
      btn.addEventListener('click', () => {
        const format = (btn.dataset.missionExport as 'csv' | 'json' | 'html') ?? 'csv';
        void this.bridge.sendCommand({ action: 'mission_export', format });
      });
    }
  }

  private setDetailVisible(visible: boolean): void {
    this.detailVisible = visible;
    const pane = this.container.querySelector<HTMLElement>('#mission-detail-pane');
    const body = this.container.querySelector<HTMLElement>('#mission-ledger-body');
    const btn = this.container.querySelector<HTMLElement>('#mission-evidence-btn');
    if (pane) pane.hidden = !visible;
    if (body) body.classList.toggle('ss-ledger-body-split', visible);
    if (btn) btn.textContent = visible ? '‹ Evidence' : 'Evidence ›';
  }

  private selectedEntry(): MissionLogEntry | undefined {
    return (this.state.entries ?? []).find((e) => e.id === this.selectedId);
  }

  private render(): void {
    this.renderKpis();
    this.renderPromotions(this.state.analytics?.promotions ?? []);
    this.renderFactions(this.state.analytics?.factions ?? []);
    this.renderDaily();
    this.renderSessionChart();
    this.renderBalanceHistory();
    this.renderLedger();
    const analytics = this.state.analytics;
    this.noteEl.textContent = [
      analytics?.note,
      this.state.error,
      this.state.wallet_error,
      this.state.recording === false ? 'Recording is paused: account access is not available.' : '',
    ].filter(Boolean).join(' · ');
  }

  private renderKpis(): void {
    const t = this.state.analytics?.totals;
    const bh = this.state.analytics?.balance_history ?? [];
    const currentBalance = bh.length ? bh[bh.length - 1].auec : null;
    const net = t?.net ?? 0;
    const tile = (label: string, value: string, cls = '') =>
      `<div class="ss-kpi-tile"><span class="ss-stat-label">${escapeHtml(label)}</span><strong class="ss-kpi-num ${cls}">${escapeHtml(value)}</strong></div>`;
    this.kpiEl.innerHTML = [
      currentBalance !== null ? tile('CURRENT BALANCE', formatAuecPlain(currentBalance) + ' aUEC', 'ss-text-ok') : '',
      tile('NET aUEC (OBSERVED)', formatAuecSigned(net), net > 0 ? 'ss-text-ok' : net < 0 ? 'ss-text-bad' : ''),
      tile('GAINS', formatAuecPlain(t?.gains ?? 0), 'ss-text-ok'),
      tile('SPENT', formatAuecPlain(t?.losses ?? 0), 'ss-text-bad'),
      tile('MISSIONS COMPLETED', String(t?.missions_completed ?? 0)),
      tile('SESSIONS TRACKED', String((this.state.analytics?.sessions ?? []).length)),
    ].join('');
  }

  private renderPromotions(promotions: MissionAnalyticsPromotion[]): void {
    if (!this.promotionsEl) return;
    if (!promotions || promotions.length === 0) {
      this.promotionsEl.style.display = 'none';
      this.promotionsEl.innerHTML = '';
      return;
    }
    this.promotionsEl.style.display = 'block';
    const cards = promotions.map((p) => {
      const timeStr = p.at ? stamp(p.at) : '';
      return `
        <div class="ss-promotion-banner-item">
          <span class="ss-promotion-icon">🎖️</span>
          <div class="ss-promotion-body">
            <div class="ss-promotion-headline">
              <strong>${escapeHtml(p.faction)}</strong>
              <span class="ss-promotion-rank-badge">▲ ${escapeHtml(p.rank)}</span>
              ${timeStr ? `<span class="ss-promotion-time">${escapeHtml(timeStr)}</span>` : ''}
            </div>
            <div class="ss-promotion-sub">
              ${p.previous_rank ? `Promoted from ${escapeHtml(p.previous_rank)} · ` : ''}Scope: ${escapeHtml(p.scope_display || p.scope)}${p.threshold !== undefined ? ` · Threshold reached: ${p.threshold.toLocaleString('en-US')} rep` : ''}
            </div>
          </div>
        </div>`;
    }).join('');

    this.promotionsEl.innerHTML = `
      <div class="ss-promotion-banner-header">
        <h3 class="ss-section-heading">RANK PROMOTIONS & MILESTONES</h3>
        <span class="ss-hint-line">${promotions.length} standing promotion${promotions.length === 1 ? '' : 's'} recorded</span>
      </div>
      <div class="ss-promotion-banner-items">${cards}</div>`;
  }

  private renderFactions(factions: MissionAnalyticsFaction[]): void {
    const earners = factions.filter((f) => f.auec > 0 || f.rep_net !== 0 || !!f.standing || (f.rep_score ?? 0) > 0);
    if (earners.length === 0) {
      this.factionEl.innerHTML =
        '<div class="ss-empty-note">Complete missions with the game running to see which factions pay you. Windows the logger cannot pin to a single mission stay out of this chart.</div>';
      return;
    }
    const max = Math.max(1, ...earners.map((f) => f.auec));
    this.factionEl.innerHTML = earners
      .map((f) => {
        const color = colorFor(f.name);
        const width = f.auec > 0 ? Math.max(3, Math.round((f.auec / max) * 100)) : 0;
        const rep = f.rep_net ? ` · rep net ${f.rep_net > 0 ? '+' : ''}${Math.round(f.rep_net).toLocaleString('en-US')}` : '';
        const avg = f.avg_per_mission ? ` · avg ${formatAuecPlain(f.avg_per_mission)}` : '';

        let standingHtml = '';
        if (f.standing) {
          const rankPill = `<span class="ss-rank-pill" title="Current Standing: ${escapeHtml(f.standing)}">${escapeHtml(f.standing)}</span>`;
          if (f.is_max_rank) {
            standingHtml = `
              <div class="ss-faction-rank-row">
                <div class="ss-rank-tier-labels">
                  ${rankPill}
                  <span class="ss-rank-next-note ss-rank-max">MAX RANK</span>
                  ${f.rep_score !== undefined ? `<span class="ss-rank-needed">${f.rep_score.toLocaleString('en-US')} rep</span>` : ''}
                </div>
              </div>`;
          } else if (f.next_standing && f.points_to_next !== undefined) {
            const pct = Math.min(100, Math.max(0, f.rep_progress_pct ?? 0));
            const neededFormatted = Math.round(f.points_to_next).toLocaleString('en-US');
            standingHtml = `
              <div class="ss-faction-rank-row">
                <div class="ss-rank-tier-labels">
                  ${rankPill}
                  <span class="ss-rank-next-arrow">➔</span>
                  <span class="ss-rank-next-target">${escapeHtml(f.next_standing)}</span>
                  <span class="ss-rank-needed">${neededFormatted} rep to rank up (${pct}%)</span>
                </div>
                <div class="ss-rank-track"><div class="ss-rank-fill" style="width:${pct}%"></div></div>
              </div>`;
          } else {
            standingHtml = `<div class="ss-faction-rank-row"><div class="ss-rank-tier-labels">${rankPill}</div></div>`;
          }
        }

        return `
          <div class="ss-faction-row">
            <div class="ss-faction-top">
              <span class="ss-hull-dot" style="background:${color}"></span>
              <span class="ss-hull-name">${escapeHtml(f.name)}</span>
              <div class="ss-faction-top-right">
                <strong class="ss-mono">${escapeHtml(formatAuecPlain(f.auec))} aUEC</strong>
              </div>
            </div>
            ${f.auec > 0 ? `<div class="ss-progress-track"><div class="ss-progress-fill" style="width:${width}%;background:${color}"></div></div>` : ''}
            ${standingHtml}
            <div class="ss-fleet-row-meta">${f.missions} mission${f.missions === 1 ? '' : 's'}${escapeHtml(avg)}${escapeHtml(rep)}</div>
          </div>`;
      })
      .join('');
  }

  private renderDaily(): void {
    const days = this.state.analytics?.daily ?? [];
    if (days.length === 0) {
      this.dailyEl.innerHTML = '<div class="ss-empty-note">No aUEC movement observed yet.</div>';
      return;
    }
    const width = 420;
    const height = 120;
    const mid = 66;
    const peakGain = Math.max(1, ...days.map((d) => d.gain));
    const peakLoss = Math.max(1, ...days.map((d) => d.loss));
    const slot = width / days.length;
    const bar = Math.max(4, Math.min(26, slot - 5));
    const bars = days
      .map((d, i) => {
        const x = i * slot + (slot - bar) / 2;
        const up = Math.round((d.gain / peakGain) * (mid - 10));
        const down = Math.round((d.loss / peakLoss) * (height - mid - 10));
        return `<rect x="${x.toFixed(1)}" y="${mid - up}" width="${bar}" height="${up}" rx="2" fill="#53d09f"><title>${escapeHtml(d.day)} +${formatAuecPlain(d.gain)}</title></rect>
                <rect x="${x.toFixed(1)}" y="${mid}" width="${bar}" height="${down}" rx="2" fill="#ff6b72"><title>${escapeHtml(d.day)} −${formatAuecPlain(d.loss)}</title></rect>`;
      })
      .join('');
    const first = escapeHtml(days[0].day.slice(5));
    const last = escapeHtml(days[days.length - 1].day.slice(5));
    this.dailyEl.innerHTML = `<svg class="ss-daily-svg" viewBox="0 0 ${width} ${height + 14}" aria-label="Daily aUEC gains and spending">
      <line x1="0" y1="${mid}" x2="${width}" y2="${mid}" stroke="rgba(154,185,206,0.3)" />${bars}
      <text x="0" y="${height + 11}" fill="#8895a4" font-size="9">${first}</text>
      <text x="${width}" y="${height + 11}" fill="#8895a4" font-size="9" text-anchor="end">${last}</text></svg>`;
  }

  private renderSessionChart(): void {
    const sessions = [...(this.state.analytics?.sessions ?? [])].reverse().filter((s) => s.net !== null);
    if (sessions.length === 0) {
      this.sessionChartEl.innerHTML = '';
      return;
    }
    const peak = Math.max(1, ...sessions.map((s) => Math.abs(s.net ?? 0)));
    const cells = sessions
      .map((s) => {
        const net = s.net ?? 0;
        const h = Math.max(3, Math.round((Math.abs(net) / peak) * 34));
        const color = net >= 0 ? '#53d09f' : '#ff6b72';
        return `<div class="ss-session-bar" title="${escapeHtml(stamp(s.started_at))} ${escapeHtml(formatAuecSigned(net))}"><span style="height:${h}px;background:${color}"></span></div>`;
      })
      .join('');
    this.sessionChartEl.innerHTML = `<div class="ss-hint-line">Net per session (oldest → newest)</div><div class="ss-session-bars">${cells}</div>`;
  }

  private renderCategories(): void { /* removed — categories shown in ledger */ }

  private renderTop(): void { /* removed — best paydays card removed */ }

  private renderBalanceHistory(): void {
    const pts = this.state.analytics?.balance_history ?? [];
    if (pts.length < 2) {
      if (this.balanceHistoryEl) this.balanceHistoryEl.innerHTML = '<div class="ss-empty-note">Wallet reads accumulate here as you play.</div>';
      return;
    }
    const W = 700, H = 174, padL = 70, padR = 16, padT = 14, padB = 24;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const minV = Math.min(...pts.map((p) => p.auec));
    const maxV = Math.max(...pts.map((p) => p.auec));
    const rangeV = maxV - minV || 1;
    const minT = pts[0].at;
    const maxT = pts[pts.length - 1].at;
    const rangeT = maxT - minT || 1;

    const cx = (at: number) => padL + ((at - minT) / rangeT) * plotW;
    const cy = (auec: number) => padT + plotH - ((auec - minV) / rangeV) * plotH;

    // Build area path
    const poly = pts.map((p) => `${cx(p.at).toFixed(1)},${cy(p.auec).toFixed(1)}`).join(' ');
    const areaPath = [
      `M ${cx(pts[0].at).toFixed(1)},${(padT + plotH).toFixed(1)}`,
      ...pts.map((p) => `L ${cx(p.at).toFixed(1)},${cy(p.auec).toFixed(1)}`),
      `L ${cx(pts[pts.length - 1].at).toFixed(1)},${(padT + plotH).toFixed(1)}`,
      'Z',
    ].join(' ');

    // Grid lines (4 horizontal)
    const gridLines = [0, 1, 2, 3].map((i) => {
      const frac = i / 3;
      const auec = minV + frac * rangeV;
      const y = cy(auec).toFixed(1);
      const label = formatAuecPlain(auec);
      return `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(154,185,206,0.15)" />
              <text x="${(padL - 6).toFixed(1)}" y="${y}" fill="#8895a4" font-size="9" text-anchor="end" dominant-baseline="middle">${escapeHtml(label)}</text>`;
    }).join('');

    // Date labels at start and end
    const dateLabel = (at: number) => {
      const d = new Date(at * 1000);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    };

    // Current balance dot
    const last = pts[pts.length - 1];
    const dotX = cx(last.at).toFixed(1);
    const dotY = cy(last.auec).toFixed(1);

    if (this.balanceHistoryEl) {
      this.balanceHistoryEl.innerHTML = `
        <svg class="ss-balance-svg" viewBox="0 0 ${W} ${H}" aria-label="Wallet balance over time">
          ${gridLines}
          <defs>
            <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#62ccff" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="#62ccff" stop-opacity="0.03"/>
            </linearGradient>
          </defs>
          <path d="${areaPath}" fill="url(#balGrad)" />
          <polyline points="${poly}" fill="none" stroke="#62ccff" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />
          <circle cx="${dotX}" cy="${dotY}" r="4" fill="#62ccff" />
          <text x="${dotX}" y="${(parseFloat(dotY) - 8).toFixed(1)}" fill="#62ccff" font-size="9.5" text-anchor="middle" font-weight="bold">${escapeHtml(formatAuecPlain(last.auec))}</text>
          <text x="${padL}" y="${H}" fill="#8895a4" font-size="9">${escapeHtml(dateLabel(pts[0].at))}</text>
          <text x="${W - padR}" y="${H}" fill="#8895a4" font-size="9" text-anchor="end">${escapeHtml(dateLabel(last.at))}</text>
        </svg>`;
    }
  }

  private renderLedger(): void {
    // Keep DOM in sync with detailVisible flag (render may be called without a click)
    this.setDetailVisible(this.detailVisible);

    const columns = this.state.columns ?? [];
    this.theadEl.innerHTML = columns.length
      ? `<tr>${columns.map(([name]) => `<th>${escapeHtml(name)}</th>`).join('')}</tr>`
      : '';
    const entries = this.state.entries ?? [];
    const span = Math.max(1, columns.length);
    if (entries.length === 0) {
      this.tbodyEl.innerHTML = `<tr><td colspan="${span}" class="ss-muted-text">No matching activity yet. Missions and balance changes appear here as they are observed.</td></tr>`;
    } else {
      const grouped = this.mode === 'sessions' ? entries.map((entry): LedgerRow => ({ kind: 'entry', entry })) : groupBySession(entries, this.state.sessions ?? [], this.state.current_session ?? '');
      this.tbodyEl.innerHTML = grouped
        .map((row) => {
          if (row.kind === 'divider') {
            return `<tr class="ss-session-divider${row.live ? ' is-live' : ''}" data-session="${escapeHtml(row.session)}"><td colspan="${span}"><span class="ss-divider-label">${row.live ? '<span class="ss-live-dot"></span> LIVE · ' : ''}${escapeHtml(row.label)}</span><span class="ss-divider-detail">${escapeHtml(row.detail)}</span></td></tr>`;
          }
          const e = row.entry;
          const isSelected = e.id === this.selectedId;
          const isPromo = e.is_promotion;
          const rowCls = [isSelected ? 'is-selected' : '', isPromo ? 'ss-row-promotion' : ''].filter(Boolean).join(' ');
          const sel = rowCls ? ` class="${rowCls}"` : '';
          return `<tr${sel} data-entry-id="${escapeHtml(e.id)}">${e.cells.map((c) => {
            if (isPromo && (c.startsWith('Promotion:') || c.startsWith('▲ '))) {
              return `<td><span class="ss-rank-pill ss-rank-pill-promo">${escapeHtml(c)}</span></td>`;
            }
            return `<td>${escapeHtml(c)}</td>`;
          }).join('')}</tr>`;
        })
        .join('');
    }

    const selected = this.selectedEntry();
    this.detailEl.textContent = selected ? selected.detail : 'Select an activity to inspect its evidence.';
    const canClassify = Boolean(selected?.is_wallet && selected.change_id);
    this.classifyRowEl.hidden = !canClassify;
    if (canClassify && selected?.category) this.classifySelectEl.value = selected.category;

    const offset = this.state.display_offset ?? 0;
    const limit = this.state.display_limit ?? 100;
    const count = this.state.display_count ?? entries.length;
    this.pagerEl.textContent = count
      ? `${offset + 1}–${Math.min(count, offset + limit)} of ${count}`
      : '0 entries';
    this.prevBtn.disabled = offset <= 0;
    this.nextBtn.disabled = offset + limit >= count;
  }
}
