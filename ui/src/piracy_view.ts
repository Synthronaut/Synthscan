import type {
  DesktopBridge,
  FlightSortieEntry,
  FlightState,
  FleetShipEntry,
  PiracyPullEntry,
  PiracySnapshotPayload,
  PiracyWatchState,
} from './bridge';
import {
  COMMODITY_TIERS,
  PREY_SHIPS,
  QED_SHIPS,
  TRADE_LANE_PRESETS,
  calculateCrewSplit,
  calculateSnareGeometry,
  formatAuec,
  formatCompactHours,
  formatDurationHms,
} from './piracy_data';

export interface PiracyViewOptions {
  onNotice?: (msg: string) => void;
}

export type PiracySubView = 'all' | 'flight' | 'ops';

function escapeHtml(text: string): string {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function sanitizeHexColor(raw: string | undefined, fallback = '#62ccff'): string {
  if (raw && /^#[0-9a-fA-F]{6}$/.test(raw)) {
    return raw;
  }
  return fallback;
}

export class PiracyViewController {
  private readonly container: HTMLElement;
  private readonly bridge: DesktopBridge;
  private readonly options: PiracyViewOptions;

  private flight: FlightState = {};
  private watch: PiracyWatchState = {};
  private sessionToken = '';
  private gameRunning = false;

  // Local sub-navigation & interactive calculator state
  private subView: PiracySubView = 'all';
  private selectedHullFocus = '';

  // Snare planner inputs
  private selectedLaneId = TRADE_LANE_PRESETS[0].id;
  private selectedQedId = QED_SHIPS[0].id;
  private offsetMkm = 1.1;
  private doglegKm = 4.0;
  private targetQtKms = 165_000;

  // Prey appraiser inputs
  private selectedPreyId = PREY_SHIPS[0].id;
  private selectedCommodityId = COMMODITY_TIERS[4].id; // Gold default
  private preyFillPct = 65;

  // Crew cut splitter inputs
  private splitTotalLoot = 2_400_000;
  private splitCrewSize = 3;
  private splitSnareBonusPct = 10;
  private splitFencePct = 0;

  // Cached DOM references
  private subtabBtns: HTMLButtonElement[] = [];
  private flightSectionEl!: HTMLElement;
  private opsSectionEl!: HTMLElement;

  // Hero telemetry DOM
  private statusPillEl!: HTMLElement;
  private activeShipEl!: HTMLElement;
  private activeMetaEl!: HTMLElement;
  private activeHelmEl!: HTMLElement;
  private activeBoardedEl!: HTMLElement;
  private activeJumpsEl!: HTMLElement;
  private activeContractsEl!: HTMLElement;
  private activeRouteEl!: HTMLElement;

  private jurisBadgeEl!: HTMLElement;
  private jurisDetailEl!: HTMLElement;
  private waitTimerEl!: HTMLElement;
  private waitToggleBtn!: HTMLButtonElement;
  private waitResetBtn!: HTMLButtonElement;
  private copyFlightCardBtn!: HTMLButtonElement;

  // Flight telemetry DOM
  private kpiSortiesEl!: HTMLElement;
  private kpiHelmEl!: HTMLElement;
  private kpiJumpsEl!: HTMLElement;
  private kpiContractsEl!: HTMLElement;
  private kpiSurvivalEl!: HTMLElement;
  private donutSvgEl!: HTMLElement;
  private donutCenterValEl!: HTMLElement;
  private donutCenterSubEl!: HTMLElement;
  private fleetListEl!: HTMLElement;
  private sortiesTbodyEl!: HTMLElement;

  // Snare Planner DOM
  private laneSelectEl!: HTMLSelectElement;
  private qedSelectEl!: HTMLSelectElement;
  private offsetInputEl!: HTMLInputElement;
  private doglegInputEl!: HTMLInputElement;
  private qtDriveSelectEl!: HTMLSelectElement;
  private snareSvgWrapEl!: HTMLElement;
  private snareReadoutEl!: HTMLElement;
  private snareAdviceEl!: HTMLElement;

  // Prey Appraiser DOM
  private preySelectEl!: HTMLSelectElement;
  private commoditySelectEl!: HTMLSelectElement;
  private preyFillInputEl!: HTMLInputElement;
  private preyFillLabelEl!: HTMLElement;
  private preyReadoutEl!: HTMLElement;
  private preySendBtn!: HTMLButtonElement;

  // Crew Splitter DOM
  private splitLootInputEl!: HTMLInputElement;
  private splitCrewInputEl!: HTMLInputElement;
  private splitBonusInputEl!: HTMLInputElement;
  private splitFenceInputEl!: HTMLInputElement;
  private splitSummaryEl!: HTMLElement;
  private splitCopyBtn!: HTMLButtonElement;

  // Pull Ledger DOM
  private pullTargetInputEl!: HTMLInputElement;
  private pullLaneInputEl!: HTMLInputElement;
  private pullOutcomeSelectEl!: HTMLSelectElement;
  private pullValueInputEl!: HTMLInputElement;
  private pullNotesInputEl!: HTMLInputElement;
  private pullLogBtn!: HTMLButtonElement;
  private pullKpiEl!: HTMLElement;
  private pullTbodyEl!: HTMLElement;

  constructor(container: HTMLElement, bridge: DesktopBridge, options: PiracyViewOptions = {}) {
    this.container = container;
    this.bridge = bridge;
    this.options = options;
    this.buildDom();
    this.bindEvents();
    this.renderStaticCalculators();
    this.renderTelemetry();
  }

  public destroy(): void {
    // Cleanup if needed
  }

  public getSubView(): PiracySubView {
    return this.subView;
  }

  public setSubView(next: PiracySubView): void {
    this.subView = next;
    for (const btn of this.subtabBtns) {
      const active = btn.dataset.piracySubtab === next;
      btn.classList.toggle('is-active', active);
    }
    this.flightSectionEl.hidden = next === 'ops';
    this.opsSectionEl.hidden = next === 'flight';
  }

  public updateFromSnapshot(payload: PiracySnapshotPayload | undefined, sessionToken = ''): void {
    const p = payload ?? {};
    this.flight = p.flight ?? p.piracy_watch?.flight ?? {};
    this.watch = p.piracy_watch ?? {};
    this.sessionToken = p.session_token ?? sessionToken ?? '';
    this.gameRunning = Boolean(p.game_running);
    this.renderTelemetry();
  }

  private buildDom(): void {
    const laneOpts = TRADE_LANE_PRESETS.map(
      (l) => `<option value="${escapeHtml(l.id)}">[${escapeHtml(l.system)} · ${escapeHtml(l.comms)}] ${escapeHtml(l.label)} (${l.distanceMkm} Mkm)</option>`,
    ).join('');
    const qedOpts = QED_SHIPS.map(
      (q) => `<option value="${escapeHtml(q.id)}">${escapeHtml(q.name)}</option>`,
    ).join('');
    const preyOpts = PREY_SHIPS.map(
      (s) => `<option value="${escapeHtml(s.id)}">${escapeHtml(s.name)} (${s.scu} SCU · max ${s.maxBoxScu} SCU crates)</option>`,
    ).join('');
    const commodityOpts = COMMODITY_TIERS.map(
      (c) => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)} (~${c.avgPricePerScu.toLocaleString('en-US')} aUEC/SCU)</option>`,
    ).join('');

    this.container.innerHTML = `
      <div class="ss-piracy-root">
        <!-- Top Hero Telemetry & Stakeout Bar -->
        <div class="ss-piracy-hero-grid">
          <div class="ss-card ss-piracy-vessel-card">
            <div class="ss-piracy-card-head">
              <span id="piracy-flight-state-pill" class="ss-status-pill is-idle">ON FOOT</span>
              <span class="ss-section-tag">LIVE AVIONICS</span>
              <span class="ss-grow"></span>
              <button id="piracy-copy-card-btn" type="button" class="ss-btn ss-btn-accent ss-btn-sm">Share Flight Card</button>
            </div>
            <div class="ss-piracy-vessel-main">
              <div id="piracy-active-ship" class="ss-piracy-ship-title">No Active Vessel</div>
              <div id="piracy-active-meta" class="ss-muted-text">Board any ship to stream Game.log flight &amp; helm telemetry</div>
            </div>
            <div class="ss-piracy-stat-strip">
              <div class="ss-stat-cell">
                <span class="ss-stat-label">HELM TIME</span>
                <strong id="piracy-active-helm" class="ss-stat-value">00:00</strong>
              </div>
              <div class="ss-stat-cell">
                <span class="ss-stat-label">ABOARD</span>
                <strong id="piracy-active-boarded" class="ss-stat-value">00:00</strong>
              </div>
              <div class="ss-stat-cell">
                <span class="ss-stat-label">QT JUMPS</span>
                <strong id="piracy-active-jumps" class="ss-stat-value">0</strong>
              </div>
              <div class="ss-stat-cell">
                <span class="ss-stat-label">CONTRACTS</span>
                <strong id="piracy-active-contracts" class="ss-stat-value">0</strong>
              </div>
            </div>
            <div class="ss-piracy-route-line">
              <span class="ss-route-k">QT ROUTE:</span>
              <span id="piracy-active-route" class="ss-route-v">No active quantum waypoint</span>
            </div>
          </div>

          <div class="ss-card ss-piracy-radar-card">
            <div class="ss-piracy-card-head">
              <span class="ss-section-tag">JURISDICTION &amp; STAKEOUT</span>
            </div>
            <div class="ss-juris-box">
              <span id="piracy-juris-badge" class="ss-juris-pill is-unknown">AWAITING TRANSITION</span>
              <p id="piracy-juris-detail" class="ss-muted-text">Reads live Monitored vs. Ungoverned transitions from Game.log instead of unreliable CrimeStat alerts.</p>
            </div>
            <div class="ss-wait-box">
              <div>
                <span class="ss-stat-label">MANUAL STAKEOUT CLOCK</span>
                <div id="piracy-wait-timer" class="ss-wait-readout">00:00</div>
              </div>
              <div class="ss-wait-actions">
                <button id="piracy-wait-toggle-btn" type="button" class="ss-btn ss-btn-accent">Start Watch</button>
                <button id="piracy-wait-reset-btn" type="button" class="ss-btn">Reset</button>
              </div>
            </div>
          </div>
        </div>

        <!-- View Switcher Bar -->
        <div class="ss-piracy-subnav" role="tablist" aria-label="Piracy and Flight sections">
          <button type="button" class="ss-subtab-btn is-active" data-piracy-subtab="all">Command Overview</button>
          <button type="button" class="ss-subtab-btn" data-piracy-subtab="flight">Flight &amp; Fleet Telemetry</button>
          <button type="button" class="ss-subtab-btn" data-piracy-subtab="ops">Snare Ops &amp; Loot Suite</button>
        </div>

        <!-- Flight & Fleet Telemetry Deck -->
        <section id="piracy-section-flight" class="ss-piracy-deck">
          <div class="ss-piracy-kpi-row">
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">TOTAL SORTIES</span>
              <strong id="piracy-kpi-sorties" class="ss-kpi-num">0</strong>
            </div>
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">TOTAL HELM TIME</span>
              <strong id="piracy-kpi-helm" class="ss-kpi-num">0s</strong>
            </div>
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">QUANTUM JUMPS</span>
              <strong id="piracy-kpi-jumps" class="ss-kpi-num">0</strong>
            </div>
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">CONTRACTS LOGGED</span>
              <strong id="piracy-kpi-contracts" class="ss-kpi-num">0</strong>
            </div>
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">SURVIVAL RATE</span>
              <strong id="piracy-kpi-survival" class="ss-kpi-num">100%</strong>
            </div>
          </div>

          <div class="ss-piracy-two-col">
            <div class="ss-card ss-fleet-card">
              <div class="ss-card-title-row">
                <h2 class="ss-section-heading">FLEET DISTRIBUTION &amp; HELM SHARE</h2>
                <span class="ss-hint-line">Click any hull to filter sorties</span>
              </div>
              <div class="ss-fleet-layout">
                <div class="ss-donut-stage">
                  <svg id="piracy-fleet-donut" class="ss-donut-svg" viewBox="0 0 180 180" aria-label="Fleet distribution ring chart"></svg>
                  <div class="ss-donut-center">
                    <strong id="piracy-donut-center-val">0h</strong>
                    <span id="piracy-donut-center-sub">FLEET TIME</span>
                  </div>
                </div>
                <div id="piracy-fleet-list" class="ss-fleet-bars"></div>
              </div>
            </div>

            <div class="ss-card ss-sorties-card">
              <div class="ss-card-title-row">
                <h2 class="ss-section-heading">RECENT SORTIES LEDGER</h2>
                <span class="ss-hint-line">Deterministic Game.log seat &amp; hangar events</span>
              </div>
              <div class="ss-table-scroll ss-piracy-scroll">
                <table class="ss-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Vessel</th>
                      <th>Route / Activity</th>
                      <th>Helm</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody id="piracy-sorties-tbody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <!-- Piracy Operations & Feasible Unmonitored Interdiction Suite -->
        <section id="piracy-section-ops" class="ss-piracy-deck">
          <div class="ss-piracy-two-col">
            <!-- Snare Drop Geometry Planner -->
            <div class="ss-card ss-snare-card">
              <div class="ss-card-title-row">
                <h2 class="ss-section-heading">QT SNARE GEOMETRY &amp; INTERCEPT PLANNER</h2>
                <span class="ss-hint-line">Works anywhere in deep or unmonitored space</span>
              </div>
              <div class="ss-form-grid">
                <label class="ss-field-stack ss-span-2">
                  <span class="ss-field-label">Trade Corridor Preset</span>
                  <select id="piracy-lane-select" class="ss-select">${laneOpts}</select>
                </label>
                <label class="ss-field-stack">
                  <span class="ss-field-label">Interdictor / QED Bubble</span>
                  <select id="piracy-qed-select" class="ss-select">${qedOpts}</select>
                </label>
                <label class="ss-field-stack">
                  <span class="ss-field-label">Expected Target QT Drive</span>
                  <select id="piracy-qtdrive-select" class="ss-select">
                    <option value="260000">S3 Fast (TS-2 / VK-class ~260k km/s)</option>
                    <option value="165000" selected>S2 Hauler (Hemera / Crossfield ~165k km/s)</option>
                    <option value="110000">S1 Industrial (Voyage / Atlas ~110k km/s)</option>
                  </select>
                </label>
                <label class="ss-field-stack">
                  <span class="ss-field-label">Drop Distance Before Dest (Mkm)</span>
                  <input id="piracy-offset-input" class="ss-input" type="number" step="0.1" min="0.1" max="50" value="1.1" />
                </label>
                <label class="ss-field-stack">
                  <span class="ss-field-label">Spline Lateral Offset (km)</span>
                  <input id="piracy-dogleg-input" class="ss-input" type="number" step="0.5" min="0" max="40" value="4.0" />
                </label>
              </div>
              <div id="piracy-snare-svg-wrap" class="ss-snare-visual"></div>
              <div id="piracy-snare-readout" class="ss-snare-readout"></div>
              <p id="piracy-snare-advice" class="ss-advice-banner"></p>
            </div>

            <!-- Prey Cargo Appraiser + Crew Cut Splitter -->
            <div class="ss-ops-right-col">
              <div class="ss-card ss-prey-card">
                <div class="ss-card-title-row">
                  <h2 class="ss-section-heading">PREY RECON &amp; CARGO APPRAISER</h2>
                  <button id="piracy-prey-send-btn" type="button" class="ss-btn ss-btn-sm ss-btn-accent">Send to Splitter &amp; Log →</button>
                </div>
                <div class="ss-form-grid">
                  <label class="ss-field-stack ss-span-2">
                    <span class="ss-field-label">Target Hull</span>
                    <select id="piracy-prey-select" class="ss-select">${preyOpts}</select>
                  </label>
                  <label class="ss-field-stack">
                    <span class="ss-field-label">Suspected Commodity</span>
                    <select id="piracy-commodity-select" class="ss-select">${commodityOpts}</select>
                  </label>
                  <label class="ss-field-stack">
                    <span class="ss-field-label">Bay Load Fill (<strong id="piracy-prey-fill-label">65%</strong>)</span>
                    <input id="piracy-prey-fill-input" class="ss-range" type="range" min="10" max="100" step="5" value="65" />
                  </label>
                </div>
                <div id="piracy-prey-readout" class="ss-prey-readout"></div>
              </div>

              <div class="ss-card ss-split-card">
                <div class="ss-card-title-row">
                  <h2 class="ss-section-heading">CREW LOOT &amp; SNARE CUT SPLITTER</h2>
                  <button id="piracy-split-copy-btn" type="button" class="ss-btn ss-btn-sm">Copy Payout</button>
                </div>
                <div class="ss-form-grid ss-grid-4">
                  <label class="ss-field-stack ss-span-2">
                    <span class="ss-field-label">Gross Haul (aUEC)</span>
                    <input id="piracy-split-loot-input" class="ss-input" type="number" min="0" step="50000" value="2400000" />
                  </label>
                  <label class="ss-field-stack">
                    <span class="ss-field-label">Crew</span>
                    <input id="piracy-split-crew-input" class="ss-input" type="number" min="1" max="16" value="3" />
                  </label>
                  <label class="ss-field-stack">
                    <span class="ss-field-label">Mantis %</span>
                    <input id="piracy-split-bonus-input" class="ss-input" type="number" min="0" max="40" value="10" />
                  </label>
                </div>
                <div class="ss-toolbar-row ss-toolbar-sub">
                  <label class="ss-inline-field">Fence / Escort Fee % <input id="piracy-split-fence-input" class="ss-input ss-input-sm" type="number" min="0" max="40" value="0" /></label>
                </div>
                <div id="piracy-split-summary" class="ss-split-summary"></div>
              </div>
            </div>
          </div>

          <!-- Persistent Snare Pull & Hit Ledger -->
          <div class="ss-card ss-pulls-card">
            <div class="ss-card-title-row">
              <h2 class="ss-section-heading">SNARE PULL &amp; INTERDICTION HIT LEDGER</h2>
              <span id="piracy-pull-kpi" class="ss-status-line">0 pulls logged · 0% catch rate</span>
            </div>
            <div class="ss-toolbar-row ss-pull-form">
              <input id="piracy-pull-target" class="ss-input ss-grow" type="text" placeholder="Target hull (e.g. Crusader C2 Hercules)" />
              <input id="piracy-pull-lane" class="ss-input ss-grow" type="text" placeholder="Lane (e.g. Monox -> Checkmate)" />
              <select id="piracy-pull-outcome" class="ss-select" aria-label="Pull outcome">
                <option value="catch">Catch / Looted</option>
                <option value="combat">Combat / Destroyed</option>
                <option value="escaped">Escaped</option>
                <option value="dry">Dry Pull</option>
              </select>
              <input id="piracy-pull-value" class="ss-input ss-input-md" type="number" min="0" step="10000" placeholder="Loot aUEC" />
              <input id="piracy-pull-notes" class="ss-input ss-grow" type="text" placeholder="Notes (optional)" />
              <button id="piracy-pull-log-btn" type="button" class="ss-btn ss-btn-accent">Log Pull</button>
            </div>
            <div class="ss-table-scroll ss-piracy-pulls-scroll">
              <table class="ss-table">
                <thead>
                  <tr>
                    <th>Target</th>
                    <th>Corridor / Lane</th>
                    <th>Outcome</th>
                    <th>Loot Value</th>
                    <th>Notes</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody id="piracy-pulls-tbody"></tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    `;

    this.subtabBtns = Array.from(this.container.querySelectorAll<HTMLButtonElement>('button[data-piracy-subtab]'));
    this.flightSectionEl = this.container.querySelector('#piracy-section-flight')!;
    this.opsSectionEl = this.container.querySelector('#piracy-section-ops')!;

    this.statusPillEl = this.container.querySelector('#piracy-flight-state-pill')!;
    this.activeShipEl = this.container.querySelector('#piracy-active-ship')!;
    this.activeMetaEl = this.container.querySelector('#piracy-active-meta')!;
    this.activeHelmEl = this.container.querySelector('#piracy-active-helm')!;
    this.activeBoardedEl = this.container.querySelector('#piracy-active-boarded')!;
    this.activeJumpsEl = this.container.querySelector('#piracy-active-jumps')!;
    this.activeContractsEl = this.container.querySelector('#piracy-active-contracts')!;
    this.activeRouteEl = this.container.querySelector('#piracy-active-route')!;

    this.jurisBadgeEl = this.container.querySelector('#piracy-juris-badge')!;
    this.jurisDetailEl = this.container.querySelector('#piracy-juris-detail')!;
    this.waitTimerEl = this.container.querySelector('#piracy-wait-timer')!;
    this.waitToggleBtn = this.container.querySelector('#piracy-wait-toggle-btn')!;
    this.waitResetBtn = this.container.querySelector('#piracy-wait-reset-btn')!;
    this.copyFlightCardBtn = this.container.querySelector('#piracy-copy-card-btn')!;

    this.kpiSortiesEl = this.container.querySelector('#piracy-kpi-sorties')!;
    this.kpiHelmEl = this.container.querySelector('#piracy-kpi-helm')!;
    this.kpiJumpsEl = this.container.querySelector('#piracy-kpi-jumps')!;
    this.kpiContractsEl = this.container.querySelector('#piracy-kpi-contracts')!;
    this.kpiSurvivalEl = this.container.querySelector('#piracy-kpi-survival')!;
    this.donutSvgEl = this.container.querySelector('#piracy-fleet-donut')!;
    this.donutCenterValEl = this.container.querySelector('#piracy-donut-center-val')!;
    this.donutCenterSubEl = this.container.querySelector('#piracy-donut-center-sub')!;
    this.fleetListEl = this.container.querySelector('#piracy-fleet-list')!;
    this.sortiesTbodyEl = this.container.querySelector('#piracy-sorties-tbody')!;

    this.laneSelectEl = this.container.querySelector('#piracy-lane-select')!;
    this.qedSelectEl = this.container.querySelector('#piracy-qed-select')!;
    this.offsetInputEl = this.container.querySelector('#piracy-offset-input')!;
    this.doglegInputEl = this.container.querySelector('#piracy-dogleg-input')!;
    this.qtDriveSelectEl = this.container.querySelector('#piracy-qtdrive-select')!;
    this.snareSvgWrapEl = this.container.querySelector('#piracy-snare-svg-wrap')!;
    this.snareReadoutEl = this.container.querySelector('#piracy-snare-readout')!;
    this.snareAdviceEl = this.container.querySelector('#piracy-snare-advice')!;

    this.preySelectEl = this.container.querySelector('#piracy-prey-select')!;
    this.commoditySelectEl = this.container.querySelector('#piracy-commodity-select')!;
    this.preyFillInputEl = this.container.querySelector('#piracy-prey-fill-input')!;
    this.preyFillLabelEl = this.container.querySelector('#piracy-prey-fill-label')!;
    this.preyReadoutEl = this.container.querySelector('#piracy-prey-readout')!;
    this.preySendBtn = this.container.querySelector('#piracy-prey-send-btn')!;

    this.splitLootInputEl = this.container.querySelector('#piracy-split-loot-input')!;
    this.splitCrewInputEl = this.container.querySelector('#piracy-split-crew-input')!;
    this.splitBonusInputEl = this.container.querySelector('#piracy-split-bonus-input')!;
    this.splitFenceInputEl = this.container.querySelector('#piracy-split-fence-input')!;
    this.splitSummaryEl = this.container.querySelector('#piracy-split-summary')!;
    this.splitCopyBtn = this.container.querySelector('#piracy-split-copy-btn')!;

    this.pullTargetInputEl = this.container.querySelector('#piracy-pull-target')!;
    this.pullLaneInputEl = this.container.querySelector('#piracy-pull-lane')!;
    this.pullOutcomeSelectEl = this.container.querySelector('#piracy-pull-outcome')!;
    this.pullValueInputEl = this.container.querySelector('#piracy-pull-value')!;
    this.pullNotesInputEl = this.container.querySelector('#piracy-pull-notes')!;
    this.pullLogBtn = this.container.querySelector('#piracy-pull-log-btn')!;
    this.pullKpiEl = this.container.querySelector('#piracy-pull-kpi')!;
    this.pullTbodyEl = this.container.querySelector('#piracy-pulls-tbody')!;
  }

  private bindEvents(): void {
    for (const btn of this.subtabBtns) {
      btn.addEventListener('click', () => {
        const mode = (btn.dataset.piracySubtab as PiracySubView) || 'all';
        this.setSubView(mode);
      });
    }

    this.waitToggleBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'piracy_toggle_wait' });
    });
    this.waitResetBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'piracy_reset_wait' });
    });
    this.copyFlightCardBtn.addEventListener('click', () => {
      this.copyText(this.buildShareableFlightSummary(), 'Flight & Fleet summary copied to clipboard.');
    });

    // Fleet hull focus click (toggle filter)
    this.fleetListEl.addEventListener('click', (ev) => {
      const target = (ev.target as HTMLElement).closest<HTMLElement>('button[data-hull-name]');
      if (!target) return;
      const hull = target.dataset.hullName ?? '';
      this.selectedHullFocus = this.selectedHullFocus === hull ? '' : hull;
      this.renderTelemetry();
    });

    // Snare geometry inputs
    const updateSnare = () => {
      this.selectedLaneId = this.laneSelectEl.value;
      this.selectedQedId = this.qedSelectEl.value;
      this.offsetMkm = Number(this.offsetInputEl.value) || 0.5;
      this.doglegKm = Number(this.doglegInputEl.value) || 0;
      this.targetQtKms = Number(this.qtDriveSelectEl.value) || 165_000;
      this.renderSnarePlanner();
    };
    this.laneSelectEl.addEventListener('change', updateSnare);
    this.qedSelectEl.addEventListener('change', updateSnare);
    this.qtDriveSelectEl.addEventListener('change', updateSnare);
    this.offsetInputEl.addEventListener('input', updateSnare);
    this.doglegInputEl.addEventListener('input', updateSnare);

    // Prey Appraiser inputs
    const updatePrey = () => {
      this.selectedPreyId = this.preySelectEl.value;
      this.selectedCommodityId = this.commoditySelectEl.value;
      this.preyFillPct = Number(this.preyFillInputEl.value) || 50;
      this.renderPreyAppraiser();
    };
    this.preySelectEl.addEventListener('change', updatePrey);
    this.commoditySelectEl.addEventListener('change', updatePrey);
    this.preyFillInputEl.addEventListener('input', updatePrey);
    this.preySendBtn.addEventListener('click', () => {
      const prey = PREY_SHIPS.find((s) => s.id === this.selectedPreyId) ?? PREY_SHIPS[0];
      const comm = COMMODITY_TIERS.find((c) => c.id === this.selectedCommodityId) ?? COMMODITY_TIERS[0];
      const estScu = Math.round((prey.scu * this.preyFillPct) / 100);
      const estValue = estScu * comm.avgPricePerScu;
      this.splitTotalLoot = estValue;
      this.splitLootInputEl.value = String(estValue);
      this.pullTargetInputEl.value = prey.name;
      this.pullValueInputEl.value = String(estValue);
      const lane = TRADE_LANE_PRESETS.find((l) => l.id === this.selectedLaneId);
      if (lane && !this.pullLaneInputEl.value.trim()) {
        this.pullLaneInputEl.value = lane.label;
      }
      this.renderCrewSplitter();
      this.notify(`Appraised ${prey.name} (${formatAuec(estValue)}) staged in Splitter & Pull Logger.`);
    });

    // Crew Loot Splitter inputs
    const updateSplit = () => {
      this.splitTotalLoot = Number(this.splitLootInputEl.value) || 0;
      this.splitCrewSize = Number(this.splitCrewInputEl.value) || 1;
      this.splitSnareBonusPct = Number(this.splitBonusInputEl.value) || 0;
      this.splitFencePct = Number(this.splitFenceInputEl.value) || 0;
      this.renderCrewSplitter();
    };
    this.splitLootInputEl.addEventListener('input', updateSplit);
    this.splitCrewInputEl.addEventListener('input', updateSplit);
    this.splitBonusInputEl.addEventListener('input', updateSplit);
    this.splitFenceInputEl.addEventListener('input', updateSplit);
    this.splitCopyBtn.addEventListener('click', () => {
      const res = calculateCrewSplit({
        totalLootAuec: this.splitTotalLoot,
        crewCount: this.splitCrewSize,
        snareBonusPct: this.splitSnareBonusPct,
        fenceFeePct: this.splitFencePct,
      });
      const summary = [
        `Crew Loot Split (${this.splitCrewSize} pilots · Gross ${formatAuec(this.splitTotalLoot)})`,
        `• Net Distributable: ${formatAuec(res.netPoolAuec)}`,
        `• Snare / Mantis Lead (+${this.splitSnareBonusPct}%): ${formatAuec(res.snareShareAuec)}`,
        `• Wingman / Boarder Cut (×${res.otherCrewCount}): ${formatAuec(res.crewMemberShareAuec)} each`,
      ].join('\n');
      this.copyText(summary, 'Crew payout breakdown copied to clipboard.');
    });

    // Pull Logger actions
    this.pullLogBtn.addEventListener('click', () => {
      const target = this.pullTargetInputEl.value.trim() || 'Unknown Vessel';
      const lane = this.pullLaneInputEl.value.trim() || this.flight.active_route || 'Open Lane';
      const outcome = (this.pullOutcomeSelectEl.value as 'catch' | 'escaped' | 'dry' | 'combat') || 'catch';
      const valueUec = Math.max(0, Math.round(Number(this.pullValueInputEl.value) || 0));
      const notes = this.pullNotesInputEl.value.trim();
      void this.bridge.sendCommand({
        action: 'piracy_log_pull',
        target,
        lane,
        outcome,
        value_uec: valueUec,
        notes,
        observed_at: Date.now() / 1000,
      });
      this.pullNotesInputEl.value = '';
      this.notify(`Logged ${outcome} pull against ${target}.`);
    });

    this.pullTbodyEl.addEventListener('click', (ev) => {
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-delete-pull]');
      if (!btn) return;
      const pullId = btn.dataset.deletePull;
      if (pullId) {
        void this.bridge.sendCommand({ action: 'piracy_delete_pull', pull_id: pullId });
      }
    });
  }

  private renderStaticCalculators(): void {
    this.renderSnarePlanner();
    this.renderPreyAppraiser();
    this.renderCrewSplitter();
  }

  private renderTelemetry(): void {
    const f = this.flight;
    const w = this.watch;
    const fState = f.state ?? 'ON_FOOT';

    // Active vessel card
    this.statusPillEl.className = 'ss-status-pill';
    if (fState === 'IN_FLIGHT') {
      this.statusPillEl.classList.add('is-flight');
      this.statusPillEl.textContent = 'IN FLIGHT';
    } else if (fState === 'BOARDED') {
      this.statusPillEl.classList.add('is-boarded');
      this.statusPillEl.textContent = 'BOARDED';
    } else {
      this.statusPillEl.classList.add('is-idle');
      this.statusPillEl.textContent = 'ON FOOT';
    }

    const shipName = f.active_ship && f.active_ship !== '--' ? f.active_ship : 'No Active Vessel';
    this.activeShipEl.textContent = shipName;
    this.activeShipEl.style.color = sanitizeHexColor(f.active_color, '#eaf0f7');

    const mfgText = f.active_mfg && f.active_mfg !== '--' ? `${f.active_mfg} Hull` : 'Awaiting Ship Voice Channel';
    const entText = f.entitlements && f.entitlements > 0 ? ` · ${f.entitlements} Hangar Ships` : '';
    this.activeMetaEl.textContent = `${mfgText}${entText}`;

    this.activeHelmEl.textContent = formatDurationHms(f.active_helm_s ?? 0);
    this.activeBoardedEl.textContent = formatDurationHms(f.active_boarded_s ?? 0);
    this.activeJumpsEl.textContent = String(f.active_jumps ?? 0);
    this.activeContractsEl.textContent = String(f.active_contracts ?? 0);
    this.activeRouteEl.textContent = f.active_route ? f.active_route : 'No active quantum waypoint';

    // Jurisdiction radar
    const monitored = f.monitored;
    const juris = f.jurisdiction ?? 'Unknown';
    this.jurisBadgeEl.className = 'ss-juris-pill';
    if (monitored === false || juris === 'Ungoverned') {
      this.jurisBadgeEl.classList.add('is-ungoverned');
      this.jurisBadgeEl.textContent = 'UNGOVERNED · WEAPONS FREE';
      this.jurisDetailEl.textContent =
        'No active Comm Array monitoring observed in Game.log. Safe zone for QED interdiction without automated crimestat reporting.';
    } else if (monitored === true || juris === 'UEE Monitored') {
      this.jurisBadgeEl.classList.add('is-monitored');
      this.jurisBadgeEl.textContent = 'UEE MONITORED SPACE';
      this.jurisDetailEl.textContent =
        'Comm Array coverage active — disable array or pull deep mid-lane outside planetary sensor spheres.';
    } else {
      this.jurisBadgeEl.classList.add('is-unknown');
      this.jurisBadgeEl.textContent = 'AWAITING JURISDICTION';
      this.jurisDetailEl.textContent = this.gameRunning
        ? 'Jump or cross a jurisdiction boundary to read Monitored vs. Ungoverned transitions from Game.log.'
        : 'Start Star Citizen to stream live jurisdiction & comm-array transitions from Game.log.';
    }

    // Wait timer
    this.waitTimerEl.textContent = formatDurationHms(w.waiting_s ?? 0);
    const waitingActive = Boolean(w.waiting_active);
    this.waitToggleBtn.textContent = waitingActive ? 'Pause Watch' : 'Start Watch';

    // Flight KPI ribbon
    const totalSorties = f.total_sorties ?? 0;
    const totalLosses = f.total_losses ?? 0;
    const survivalPct = totalSorties > 0 ? Math.max(0, Math.round(((totalSorties - totalLosses) / totalSorties) * 100)) : 100;

    this.kpiSortiesEl.textContent = String(totalSorties);
    this.kpiHelmEl.textContent = formatCompactHours(f.total_helm_s ?? 0);
    this.kpiJumpsEl.textContent = String(f.total_jumps ?? 0);
    this.kpiContractsEl.textContent = String(f.total_contracts ?? 0);
    this.kpiSurvivalEl.textContent = `${survivalPct}%`;

    this.renderFleetCharts(f.fleet ?? [], f.total_helm_s ?? 0);
    this.renderSortiesLedger(f.recent ?? []);
    this.renderPullLedger(w.pulls ?? [], w.pull_stats);
  }

  private renderFleetCharts(fleet: FleetShipEntry[], totalHelmS: number): void {
    const cx = 90;
    const cy = 90;
    const r = 64;
    const circ = 2 * Math.PI * r;

    if (fleet.length === 0 || totalHelmS <= 0) {
      this.donutSvgEl.innerHTML = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(120,165,205,0.18)" stroke-width="16" />`;
      this.donutCenterValEl.textContent = '0h';
      this.donutCenterSubEl.textContent = 'NO FLIGHT DATA';
      this.fleetListEl.innerHTML = `<div class="ss-empty-note">Board and fly ships in Star Citizen to populate your live fleet distribution chart.</div>`;
      return;
    }

    let offset = 0;
    const segments: string[] = [];
    for (const entry of fleet) {
      const frac = Math.max(0.02, entry.seconds / totalHelmS);
      const dash = Math.max(2, frac * circ - 3);
      const color = sanitizeHexColor(entry.color, '#62ccff');
      const dim = this.selectedHullFocus && this.selectedHullFocus !== entry.name ? ' opacity="0.28"' : '';
      segments.push(
        `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="16" stroke-dasharray="${dash.toFixed(1)} ${circ.toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}" transform="rotate(-90 ${cx} ${cy})"${dim} />`,
      );
      offset += frac * circ;
    }
    this.donutSvgEl.innerHTML = segments.join('');

    const focused = this.selectedHullFocus
      ? fleet.find((f) => f.name === this.selectedHullFocus)
      : fleet[0];
    this.donutCenterValEl.textContent = formatCompactHours(focused?.seconds ?? totalHelmS);
    this.donutCenterSubEl.textContent = focused
      ? `${focused.pct}% · ${focused.mfg.toUpperCase()}`
      : 'TOTAL HELM';

    this.fleetListEl.innerHTML = fleet
      .map((row) => {
        const color = sanitizeHexColor(row.color, '#62ccff');
        const active = this.selectedHullFocus === row.name;
        return `
          <button type="button" class="ss-fleet-row${active ? ' is-selected' : ''}" data-hull-name="${escapeHtml(row.name)}">
            <div class="ss-fleet-row-top">
              <span class="ss-hull-dot" style="background:${color}"></span>
              <span class="ss-hull-name">${escapeHtml(row.name)}</span>
              <span class="ss-hull-time">${escapeHtml(formatCompactHours(row.seconds))} · ${row.pct}%</span>
            </div>
            <div class="ss-progress-track">
              <div class="ss-progress-fill" style="width:${Math.max(3, row.pct)}%;background:${color}"></div>
            </div>
            <div class="ss-fleet-row-meta">${row.sorties} sorties · ${row.jumps} jumps · ${row.contracts} contracts${row.losses > 0 ? ` · ${row.losses} loss` : ''}</div>
          </button>
        `;
      })
      .join('');
  }

  private renderSortiesLedger(recent: FlightSortieEntry[]): void {
    const rows = this.selectedHullFocus
      ? recent.filter((s) => s.ship === this.selectedHullFocus)
      : recent;

    if (rows.length === 0) {
      this.sortiesTbodyEl.innerHTML = `<tr><td colspan="5" class="ss-muted-text">No sorties recorded${this.selectedHullFocus ? ` for ${escapeHtml(this.selectedHullFocus)}` : ''} yet.</td></tr>`;
      return;
    }

    this.sortiesTbodyEl.innerHTML = rows
      .map((row) => {
        const hasIncident = Boolean(row.incident);
        const statusLabel = hasIncident ? row.incident! : row.reason || 'Landed';
        const badgeCls = hasIncident ? 'ss-pill-bad' : 'ss-pill-ok';
        const activity = row.destination
          ? `To ${row.destination} · ${row.jumps} QT`
          : `${row.jumps} QT jumps · ${row.contracts} contracts`;
        return `
          <tr>
            <td class="ss-mono">${escapeHtml(row.time)}</td>
            <td><strong>${escapeHtml(row.ship)}</strong></td>
            <td class="ss-muted-text">${escapeHtml(activity)}</td>
            <td class="ss-mono">${escapeHtml(formatDurationHms(row.duration_s))}</td>
            <td><span class="ss-outcome-pill ${badgeCls}">${escapeHtml(statusLabel)}</span></td>
          </tr>
        `;
      })
      .join('');
  }

  private renderSnarePlanner(): void {
    const lane = TRADE_LANE_PRESETS.find((l) => l.id === this.selectedLaneId) ?? TRADE_LANE_PRESETS[0];
    const qed = QED_SHIPS.find((q) => q.id === this.selectedQedId) ?? QED_SHIPS[0];

    const geom = calculateSnareGeometry({
      laneDistanceMkm: lane.distanceMkm,
      offsetMkmFromDest: this.offsetMkm,
      doglegKm: this.doglegKm,
      targetDriveSpeedKms: this.targetQtKms,
      qedRadiusKm: qed.radiusKm,
    });

    const snareX = 42 + (geom.snarePosPct / 100) * 356;
    const snareY = 64 + Math.min(24, Math.max(-24, (this.doglegKm / 30) * 24));
    const visualRadius = Math.max(10, Math.min(30, qed.radiusKm * 1.4));
    const bubbleColor = geom.inRange ? '#53d09f' : '#ff6b72';

    this.snareSvgWrapEl.innerHTML = `
      <svg class="ss-snare-svg" viewBox="0 0 440 128" aria-label="Quantum Snare corridor geometry diagram">
        <defs>
          <linearGradient id="ss-lane-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#62ccff" stop-opacity="0.35" />
            <stop offset="100%" stop-color="#53d09f" stop-opacity="0.85" />
          </linearGradient>
        </defs>
        <line x1="42" y1="64" x2="398" y2="64" stroke="url(#ss-lane-grad)" stroke-width="2.5" stroke-dasharray="6 4" />
        <polygon points="42,64 398,52 398,76" fill="rgba(98,204,255,0.08)" />
        <circle cx="${snareX.toFixed(1)}" cy="${snareY.toFixed(1)}" r="${visualRadius.toFixed(1)}" fill="${bubbleColor}" fill-opacity="0.16" stroke="${bubbleColor}" stroke-width="1.8" />
        <circle cx="${snareX.toFixed(1)}" cy="${snareY.toFixed(1)}" r="3.5" fill="${bubbleColor}" />
        <circle cx="42" cy="64" r="6" fill="#62ccff" />
        <circle cx="398" cy="64" r="7" fill="#53d09f" />
        <text x="42" y="24" fill="#8895a4" font-size="10" text-anchor="middle">ORIGIN</text>
        <text x="${snareX.toFixed(1)}" y="114" fill="${bubbleColor}" font-size="10" font-weight="700" text-anchor="middle">SNARE (${qed.radiusKm} km)</text>
        <text x="398" y="24" fill="#53d09f" font-size="10" text-anchor="middle">DESTINATION</text>
      </svg>
    `;

    this.snareReadoutEl.innerHTML = `
      <div class="ss-mini-metric"><span>LANE EXPOSURE</span><strong>${escapeHtml(lane.comms)}</strong></div>
      <div class="ss-mini-metric"><span>TARGET TRANSIT</span><strong>${geom.transitSeconds}s</strong></div>
      <div class="ss-mini-metric"><span>DROP POINT</span><strong>${geom.snarePosPct.toFixed(0)}% al. spline</strong></div>
      <div class="ss-mini-metric"><span>INTERCEPT STATUS</span><strong class="${geom.inRange ? 'ss-text-ok' : 'ss-text-bad'}">${geom.inRange ? 'IN BUBBLE' : 'OUT OF RANGE'}</strong></div>
    `;
    this.snareAdviceEl.textContent = `${geom.dropAdvice} (${lane.note})`;
  }

  private renderPreyAppraiser(): void {
    const prey = PREY_SHIPS.find((s) => s.id === this.selectedPreyId) ?? PREY_SHIPS[0];
    const comm = COMMODITY_TIERS.find((c) => c.id === this.selectedCommodityId) ?? COMMODITY_TIERS[0];
    const estScu = Math.round((prey.scu * this.preyFillPct) / 100);
    const estValue = estScu * comm.avgPricePerScu;
    const maxCrates = Math.max(1, Math.ceil(estScu / prey.maxBoxScu));

    this.preyFillLabelEl.textContent = `${this.preyFillPct}%`;
    this.preyReadoutEl.innerHTML = `
      <div class="ss-prey-stats">
        <div><span>ESTIMATED HAUL</span><strong class="ss-text-accent">${escapeHtml(formatAuec(estValue))}</strong></div>
        <div><span>CARGO LOAD</span><strong>${estScu} / ${prey.scu} SCU (~${maxCrates}×${prey.maxBoxScu} SCU)</strong></div>
        <div><span>CREW NEEDED</span><strong>${escapeHtml(prey.recommendedCrew)}</strong></div>
        <div><span>QT SIZE</span><strong>${escapeHtml(prey.qtSize)}</strong></div>
      </div>
      <p class="ss-hint-line ss-prey-note">${escapeHtml(prey.hullNote)} Typical: ${escapeHtml(prey.typicalCargo)}</p>
    `;
  }

  private renderCrewSplitter(): void {
    const res = calculateCrewSplit({
      totalLootAuec: this.splitTotalLoot,
      crewCount: this.splitCrewSize,
      snareBonusPct: this.splitSnareBonusPct,
      fenceFeePct: this.splitFencePct,
    });

    this.splitSummaryEl.innerHTML = `
      <div class="ss-split-row"><span>Snare / Mantis Lead Cut</span><strong class="ss-text-accent">${escapeHtml(formatAuec(res.snareShareAuec))}</strong></div>
      <div class="ss-split-row"><span>Each Crew Cut (×${res.otherCrewCount})</span><strong>${escapeHtml(formatAuec(res.crewMemberShareAuec))}</strong></div>
      <div class="ss-split-row"><span>Net Pool After Fence (${this.splitFencePct}%)</span><span class="ss-muted-text">${escapeHtml(formatAuec(res.netPoolAuec))}</span></div>
    `;
  }

  private renderPullLedger(
    pulls: PiracyPullEntry[],
    stats?: { total: number; catches: number; hit_rate: number; total_loot_uec: number },
  ): void {
    const total = stats?.total ?? pulls.length;
    const catches = stats?.catches ?? pulls.filter((p) => p.outcome === 'catch').length;
    const rate = stats?.hit_rate ?? (total > 0 ? Math.round((catches / total) * 100) : 0);
    const loot = stats?.total_loot_uec ?? pulls.reduce((acc, p) => acc + (p.value_uec || 0), 0);

    this.pullKpiEl.textContent = `${total} pulls · ${rate}% catch rate · ${formatAuec(loot)} stolen`;

    if (pulls.length === 0) {
      this.pullTbodyEl.innerHTML = `<tr><td colspan="6" class="ss-muted-text">No snare pulls logged yet. Stage a ship from Prey Recon or log an interdiction above.</td></tr>`;
      return;
    }

    this.pullTbodyEl.innerHTML = pulls
      .map((p) => {
        const cls =
          p.outcome === 'catch'
            ? 'ss-pill-ok'
            : p.outcome === 'combat'
              ? 'ss-pill-warn'
              : 'ss-pill-bad';
        return `
          <tr data-pull-id="${escapeHtml(p.id)}">
            <td><strong>${escapeHtml(p.target)}</strong></td>
            <td class="ss-muted-text">${escapeHtml(p.lane)}</td>
            <td><span class="ss-outcome-pill ${cls}">${escapeHtml(p.outcome.toUpperCase())}</span></td>
            <td class="ss-mono">${escapeHtml(formatAuec(p.value_uec))}</td>
            <td class="ss-muted-text">${escapeHtml(p.notes || '—')}</td>
            <td><button type="button" class="ss-btn ss-btn-sm" data-delete-pull="${escapeHtml(p.id)}" aria-label="Delete pull">×</button></td>
          </tr>
        `;
      })
      .join('');
  }

  private buildShareableFlightSummary(): string {
    const f = this.flight;
    const w = this.watch;
    const top = f.fleet?.[0];
    const pulls = w.pull_stats;
    const lines = [
      `**SynthScan Flight & Piracy Report**`,
      `• Status: ${f.state ?? 'ON_FOOT'} · Vessel: ${f.active_ship && f.active_ship !== '--' ? f.active_ship : 'None'}`,
      `• Total Sorties: ${f.total_sorties ?? 0} · Helm Time: ${formatCompactHours(f.total_helm_s ?? 0)} · QT Jumps: ${f.total_jumps ?? 0}`,
      top ? `• Most Flown Hull: ${top.name} (${formatCompactHours(top.seconds)}, ${top.pct}%)` : `• Most Flown Hull: None logged yet`,
      pulls ? `• Snare Ledger: ${pulls.catches}/${pulls.total} catches (${pulls.hit_rate}%) · Loot: ${formatAuec(pulls.total_loot_uec)}` : '',
    ];
    return lines.filter(Boolean).join('\n');
  }

  private notify(msg: string): void {
    this.options.onNotice?.(msg);
  }

  private copyText(content: string, notice: string): void {
    const clip = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
    if (clip?.writeText) {
      void clip.writeText(content).then(
        () => this.notify(notice),
        () => this.notify(notice),
      );
      return;
    }
    this.notify(notice);
  }
}
