import type {
  DesktopBridge,
  FlightSortieEntry,
  FlightState,
  FleetShipEntry,
  PiracyPullEntry,
  PiracySnapshotPayload,
  PiracyWatchState,
  ShipCombatEntry,
} from './bridge';
import {
  QED_SHIPS,
  TRADE_LANE_PRESETS,
  calculateCrewSplit,
  calculateGpsIntercept,
  calculateSnareGeometry,
  formatAuec,
  formatCompactHours,
  formatDurationHms,
  parseShowLocationText,
  type GpsPoint,
} from './piracy_data';

export interface PiracyViewOptions {
  onNotice?: (msg: string) => void;
}

export type PiracySubView = 'flight' | 'piracy';

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

function formatGpsKm(pt: GpsPoint): string {
  const kx = (pt.x / 1000).toFixed(1);
  const ky = (pt.y / 1000).toFixed(1);
  const kz = (pt.z / 1000).toFixed(1);
  return `X:${kx} km · Y:${ky} km · Z:${kz} km`;
}

export class PiracyViewController {
  private readonly container: HTMLElement;
  private readonly bridge: DesktopBridge;
  private readonly options: PiracyViewOptions;

  private flight: FlightState = {};
  private watch: PiracyWatchState = {};
  private sessionToken = '';
  private gameRunning = false;

  // Local sub-navigation & interactive calculator state (Flight first, Piracy second)
  private subView: PiracySubView = 'flight';
  private selectedHullFocus = '';
  private combatFilter: 'all' | 'kill' | 'loss' = 'all';

  // Snare planner inputs
  private selectedLaneId = TRADE_LANE_PRESETS[0].id;
  private selectedQedId = QED_SHIPS[0].id;
  private offsetMkm = 1.1;
  private doglegKm = 4.0;

  // /showlocation GPS coordinate verifier state
  private gpsOrigin: GpsPoint | null = null;
  private gpsDest: GpsPoint | null = null;
  private gpsShip: GpsPoint | null = null;

  // Crew cut splitter inputs
  private splitTotalLoot = 2_400_000;
  private splitCrewSize = 3;
  private splitSnareBonusPct = 10;
  private splitFencePct = 0;

  // Cached DOM references
  private subtabBtns: HTMLButtonElement[] = [];
  private flightSectionEl!: HTMLElement;
  private piracySectionEl!: HTMLElement;

  // Hero telemetry DOM (Flight tab)
  private statusPillEl!: HTMLElement;
  private activeShipEl!: HTMLElement;
  private activeMetaEl!: HTMLElement;
  private activeHelmEl!: HTMLElement;
  private activeBoardedEl!: HTMLElement;
  private activeJumpsEl!: HTMLElement;
  private activeContractsEl!: HTMLElement;
  private activeKillsEl!: HTMLElement;
  private activeRouteEl!: HTMLElement;
  private copyFlightCardBtn!: HTMLButtonElement;

  // Jurisdiction & stakeout DOM (Piracy tab)
  private jurisBadgeEl!: HTMLElement;
  private jurisDetailEl!: HTMLElement;
  private waitTimerEl!: HTMLElement;
  private waitToggleBtn!: HTMLButtonElement;
  private waitResetBtn!: HTMLButtonElement;

  // Flight telemetry DOM
  private kpiSortiesEl!: HTMLElement;
  private kpiHelmEl!: HTMLElement;
  private kpiJumpsEl!: HTMLElement;
  private kpiContractsEl!: HTMLElement;
  private kpiKillsEl!: HTMLElement;
  private kpiLossesEl!: HTMLElement;
  private kpiSurvivalEl!: HTMLElement;
  private donutSvgEl!: HTMLElement;
  private donutCenterValEl!: HTMLElement;
  private donutCenterSubEl!: HTMLElement;
  private fleetListEl!: HTMLElement;
  private sortiesTbodyEl!: HTMLElement;
  private combatSummaryEl!: HTMLElement;
  private combatFilterBtns: HTMLButtonElement[] = [];
  private combatTbodyEl!: HTMLElement;

  // Snare Planner & GPS Verifier DOM
  private laneSelectEl!: HTMLSelectElement;
  private qedSelectEl!: HTMLSelectElement;
  private offsetInputEl!: HTMLInputElement;
  private doglegInputEl!: HTMLInputElement;
  private snareSvgWrapEl!: HTMLElement;
  private snareReadoutEl!: HTMLElement;
  private snareAdviceEl!: HTMLElement;

  private gpsInputEl!: HTMLInputElement;
  private gpsPasteBtn!: HTMLButtonElement;
  private gpsSetOriginBtn!: HTMLButtonElement;
  private gpsSetDestBtn!: HTMLButtonElement;
  private gpsVerifyShipBtn!: HTMLButtonElement;
  private gpsClearBtn!: HTMLButtonElement;
  private gpsStatusEl!: HTMLElement;

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
    this.setSubView(this.subView);
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
    this.flightSectionEl.hidden = next !== 'flight';
    this.piracySectionEl.hidden = next !== 'piracy';
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

    this.container.innerHTML = `
      <div class="ss-piracy-root">
        <!-- View Switcher Bar: Flight first, Piracy second -->
        <div class="ss-piracy-subnav" role="tablist" aria-label="Flight and Piracy sections">
          <button type="button" class="ss-subtab-btn is-active" data-piracy-subtab="flight">Flight</button>
          <button type="button" class="ss-subtab-btn" data-piracy-subtab="piracy">Piracy</button>
        </div>

        <!-- FLIGHT TAB -->
        <section id="piracy-section-flight" class="ss-piracy-deck">
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
              <div class="ss-stat-cell">
                <span class="ss-stat-label">SHIP KILLS</span>
                <strong id="piracy-active-kills" class="ss-stat-value">0</strong>
              </div>
            </div>
            <div class="ss-piracy-route-line">
              <span class="ss-route-k">QT ROUTE:</span>
              <span id="piracy-active-route" class="ss-route-v">No active quantum waypoint</span>
            </div>
          </div>

          <div class="ss-piracy-kpi-row">
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">TOTAL FLIGHTS</span>
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
              <span class="ss-stat-label">SHIP KILLS</span>
              <strong id="piracy-kpi-kills" class="ss-kpi-num">0</strong>
            </div>
            <div class="ss-kpi-tile">
              <span class="ss-stat-label">SHIP LOSSES</span>
              <strong id="piracy-kpi-losses" class="ss-kpi-num">0</strong>
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
                <span class="ss-hint-line">Click any hull to filter flights</span>
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
                <h2 class="ss-section-heading">RECENT FLIGHTS</h2>
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

          <div class="ss-card ss-combat-log-card">
            <div class="ss-card-title-row">
              <h2 class="ss-section-heading">SHIP COMBAT &amp; LOSS LOG</h2>
              <span id="piracy-combat-summary" class="ss-hint-line">0 kills · 0 losses</span>
              <span class="ss-grow"></span>
              <div class="ss-piracy-subnav" role="group" aria-label="Filter ship combat log">
                <button type="button" class="ss-subtab-btn is-active" data-combat-filter="all">All</button>
                <button type="button" class="ss-subtab-btn" data-combat-filter="kill">Kills</button>
                <button type="button" class="ss-subtab-btn" data-combat-filter="loss">Losses</button>
              </div>
            </div>
            <div class="ss-table-scroll ss-piracy-scroll">
              <table class="ss-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Vessel</th>
                    <th>Cause</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody id="piracy-combat-tbody"></tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- PIRACY TAB -->
        <section id="piracy-section-piracy" class="ss-piracy-deck" hidden>
          <div class="ss-card ss-piracy-radar-card">
            <div class="ss-piracy-card-head">
              <span class="ss-section-tag">JURISDICTION &amp; STAKEOUT</span>
              <span class="ss-grow"></span>
              <span id="piracy-juris-badge" class="ss-juris-pill is-unknown">AWAITING TRANSITION</span>
            </div>
            <div class="ss-piracy-radar-body">
              <p id="piracy-juris-detail" class="ss-muted-text">Reads live Monitored vs. Ungoverned transitions from Game.log instead of unreliable CrimeStat alerts.</p>
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

          <div class="ss-piracy-two-col">
            <!-- Snare Drop Geometry & Coverage Planner -->
            <div class="ss-card ss-snare-card">
              <div class="ss-card-title-row">
                <h2 class="ss-section-heading">QT SNARE GEOMETRY &amp; COVERAGE PLANNER</h2>
                <span class="ss-hint-line">SnarePlan-style cone coverage + /showlocation check</span>
              </div>
              <div class="ss-form-grid">
                <label class="ss-field-stack ss-span-2">
                  <span class="ss-field-label">Trade Corridor Preset</span>
                  <select id="piracy-lane-select" class="ss-select">${laneOpts}</select>
                </label>
                <label class="ss-field-stack ss-span-2">
                  <span class="ss-field-label">Interdictor / QED Bubble</span>
                  <select id="piracy-qed-select" class="ss-select">${qedOpts}</select>
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

              <!-- /showlocation GPS Coordinate Verifier -->
              <div class="ss-gps-panel">
                <div class="ss-gps-head">
                  <span class="ss-field-label">GPS COVERAGE CHECK (TYPE <code>/showlocation</code> IN GAME CHAT — NO DISPLAYINFO NEEDED)</span>
                </div>
                <div class="ss-gps-row">
                  <input id="piracy-gps-input" class="ss-input ss-grow" type="text" placeholder="Paste /showlocation (e.g. Coordinates: x:... y:... z:...)" />
                  <button id="piracy-gps-paste-btn" type="button" class="ss-btn ss-btn-sm">Paste</button>
                </div>
                <div class="ss-gps-actions">
                  <button id="piracy-gps-origin-btn" type="button" class="ss-btn ss-btn-sm">Set Origin</button>
                  <button id="piracy-gps-dest-btn" type="button" class="ss-btn ss-btn-sm">Set Dest</button>
                  <button id="piracy-gps-verify-btn" type="button" class="ss-btn ss-btn-sm ss-btn-accent">Verify My Position</button>
                  <button id="piracy-gps-clear-btn" type="button" class="ss-btn ss-btn-sm">Clear</button>
                </div>
                <div id="piracy-gps-status" class="ss-gps-status ss-muted-text">Type /showlocation in chat to copy your exact XYZ coordinates, then paste or click Verify My Position.</div>
              </div>

              <div id="piracy-snare-svg-wrap" class="ss-snare-visual"></div>
              <div id="piracy-snare-readout" class="ss-snare-readout"></div>
              <p id="piracy-snare-advice" class="ss-advice-banner"></p>
            </div>

            <!-- Crew Cut Splitter + Manual Snare Pull Ledger -->
            <div class="ss-ops-right-col">
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

              <!-- Manual Snare Pull & Hit Ledger -->
              <div class="ss-card ss-pulls-card">
                <div class="ss-card-title-row">
                  <h2 class="ss-section-heading">SNARE PULL &amp; INTERDICTION HIT LEDGER</h2>
                  <span id="piracy-pull-kpi" class="ss-status-line">0 pulls logged · 0% catch rate</span>
                </div>
                <div class="ss-toolbar-row ss-pull-form">
                  <input id="piracy-pull-target" class="ss-input ss-grow" type="text" placeholder="Target hull (e.g. Crusader C2 Hercules)" />
                  <input id="piracy-pull-lane" class="ss-input ss-grow" type="text" placeholder="Lane (e.g. Levski -> Pyro GW)" />
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
            </div>
          </div>
        </section>
      </div>
    `;

    this.subtabBtns = Array.from(this.container.querySelectorAll<HTMLButtonElement>('button[data-piracy-subtab]'));
    this.flightSectionEl = this.container.querySelector('#piracy-section-flight')!;
    this.piracySectionEl = this.container.querySelector('#piracy-section-piracy')!;

    this.statusPillEl = this.container.querySelector('#piracy-flight-state-pill')!;
    this.activeShipEl = this.container.querySelector('#piracy-active-ship')!;
    this.activeMetaEl = this.container.querySelector('#piracy-active-meta')!;
    this.activeHelmEl = this.container.querySelector('#piracy-active-helm')!;
    this.activeBoardedEl = this.container.querySelector('#piracy-active-boarded')!;
    this.activeJumpsEl = this.container.querySelector('#piracy-active-jumps')!;
    this.activeContractsEl = this.container.querySelector('#piracy-active-contracts')!;
    this.activeKillsEl = this.container.querySelector('#piracy-active-kills')!;
    this.activeRouteEl = this.container.querySelector('#piracy-active-route')!;
    this.copyFlightCardBtn = this.container.querySelector('#piracy-copy-card-btn')!;

    this.jurisBadgeEl = this.container.querySelector('#piracy-juris-badge')!;
    this.jurisDetailEl = this.container.querySelector('#piracy-juris-detail')!;
    this.waitTimerEl = this.container.querySelector('#piracy-wait-timer')!;
    this.waitToggleBtn = this.container.querySelector('#piracy-wait-toggle-btn')!;
    this.waitResetBtn = this.container.querySelector('#piracy-wait-reset-btn')!;

    this.kpiSortiesEl = this.container.querySelector('#piracy-kpi-sorties')!;
    this.kpiHelmEl = this.container.querySelector('#piracy-kpi-helm')!;
    this.kpiJumpsEl = this.container.querySelector('#piracy-kpi-jumps')!;
    this.kpiContractsEl = this.container.querySelector('#piracy-kpi-contracts')!;
    this.kpiKillsEl = this.container.querySelector('#piracy-kpi-kills')!;
    this.kpiLossesEl = this.container.querySelector('#piracy-kpi-losses')!;
    this.kpiSurvivalEl = this.container.querySelector('#piracy-kpi-survival')!;
    this.donutSvgEl = this.container.querySelector('#piracy-fleet-donut')!;
    this.donutCenterValEl = this.container.querySelector('#piracy-donut-center-val')!;
    this.donutCenterSubEl = this.container.querySelector('#piracy-donut-center-sub')!;
    this.fleetListEl = this.container.querySelector('#piracy-fleet-list')!;
    this.sortiesTbodyEl = this.container.querySelector('#piracy-sorties-tbody')!;
    this.combatSummaryEl = this.container.querySelector('#piracy-combat-summary')!;
    this.combatFilterBtns = Array.from(this.container.querySelectorAll<HTMLButtonElement>('button[data-combat-filter]'));
    this.combatTbodyEl = this.container.querySelector('#piracy-combat-tbody')!;

    this.laneSelectEl = this.container.querySelector('#piracy-lane-select')!;
    this.qedSelectEl = this.container.querySelector('#piracy-qed-select')!;
    this.offsetInputEl = this.container.querySelector('#piracy-offset-input')!;
    this.doglegInputEl = this.container.querySelector('#piracy-dogleg-input')!;
    this.snareSvgWrapEl = this.container.querySelector('#piracy-snare-svg-wrap')!;
    this.snareReadoutEl = this.container.querySelector('#piracy-snare-readout')!;
    this.snareAdviceEl = this.container.querySelector('#piracy-snare-advice')!;

    this.gpsInputEl = this.container.querySelector('#piracy-gps-input')!;
    this.gpsPasteBtn = this.container.querySelector('#piracy-gps-paste-btn')!;
    this.gpsSetOriginBtn = this.container.querySelector('#piracy-gps-origin-btn')!;
    this.gpsSetDestBtn = this.container.querySelector('#piracy-gps-dest-btn')!;
    this.gpsVerifyShipBtn = this.container.querySelector('#piracy-gps-verify-btn')!;
    this.gpsClearBtn = this.container.querySelector('#piracy-gps-clear-btn')!;
    this.gpsStatusEl = this.container.querySelector('#piracy-gps-status')!;

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
        const mode = (btn.dataset.piracySubtab as PiracySubView) || 'flight';
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

    for (const btn of this.combatFilterBtns) {
      btn.addEventListener('click', () => {
        const next = (btn.dataset.combatFilter as 'all' | 'kill' | 'loss') || 'all';
        this.combatFilter = next;
        for (const b of this.combatFilterBtns) {
          b.classList.toggle('is-active', b.dataset.combatFilter === next);
        }
        this.renderCombatLog(this.flight.combat_log ?? []);
      });
    }

    // Snare geometry inputs
    const updateSnare = () => {
      this.selectedLaneId = this.laneSelectEl.value;
      this.selectedQedId = this.qedSelectEl.value;
      this.offsetMkm = Number(this.offsetInputEl.value) || 0.5;
      this.doglegKm = Number(this.doglegInputEl.value) || 0;
      this.renderSnarePlanner();
    };
    this.laneSelectEl.addEventListener('change', updateSnare);
    this.qedSelectEl.addEventListener('change', updateSnare);
    this.offsetInputEl.addEventListener('input', updateSnare);
    this.doglegInputEl.addEventListener('input', updateSnare);

    // /showlocation GPS coordinate verifier
    const readGpsFromInput = (): GpsPoint | null => {
      const pt = parseShowLocationText(this.gpsInputEl.value);
      if (!pt) {
        this.notify('Paste valid /showlocation coordinates (e.g. Coordinates: x:... y:... z:...).');
      }
      return pt;
    };

    this.gpsPasteBtn.addEventListener('click', () => {
      const clip = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
      if (clip?.readText) {
        void clip.readText().then(
          (text) => {
            this.gpsInputEl.value = text;
            const pt = parseShowLocationText(text);
            if (pt) {
              this.gpsShip = pt;
              this.applyGpsToPlanner();
              this.notify('Read /showlocation GPS coordinates from clipboard.');
            } else {
              this.notify('Clipboard did not contain /showlocation coordinates.');
            }
          },
          () => {
            this.gpsInputEl.focus();
            this.notify('Paste your /showlocation coordinates into the GPS box.');
          },
        );
      } else {
        this.gpsInputEl.focus();
      }
    });

    this.gpsSetOriginBtn.addEventListener('click', () => {
      const pt = readGpsFromInput();
      if (!pt) return;
      this.gpsOrigin = pt;
      this.applyGpsToPlanner();
    });

    this.gpsSetDestBtn.addEventListener('click', () => {
      const pt = readGpsFromInput();
      if (!pt) return;
      this.gpsDest = pt;
      this.applyGpsToPlanner();
    });

    this.gpsVerifyShipBtn.addEventListener('click', () => {
      const pt = readGpsFromInput();
      if (!pt) return;
      this.gpsShip = pt;
      this.applyGpsToPlanner();
    });

    this.gpsClearBtn.addEventListener('click', () => {
      this.gpsOrigin = null;
      this.gpsDest = null;
      this.gpsShip = null;
      this.gpsInputEl.value = '';
      this.renderGpsStatus();
      this.renderSnarePlanner();
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

  private applyGpsToPlanner(): void {
    const qed = QED_SHIPS.find((q) => q.id === this.selectedQedId) ?? QED_SHIPS[0];
    if (this.gpsOrigin && this.gpsDest && this.gpsShip) {
      const intercept = calculateGpsIntercept(this.gpsOrigin, this.gpsDest, this.gpsShip, qed.radiusKm);
      if (intercept) {
        this.offsetMkm = Math.max(0.05, intercept.offsetMkmFromDest);
        this.doglegKm = intercept.lateralOffsetKm;
        this.offsetInputEl.value = String(this.offsetMkm);
        this.doglegInputEl.value = String(this.doglegKm);
      }
    }
    this.renderGpsStatus();
    this.renderSnarePlanner();
  }

  private renderGpsStatus(): void {
    const qed = QED_SHIPS.find((q) => q.id === this.selectedQedId) ?? QED_SHIPS[0];
    const parts: string[] = [];
    if (this.gpsOrigin) parts.push(`Origin locked (${formatGpsKm(this.gpsOrigin)})`);
    if (this.gpsDest) parts.push(`Dest locked (${formatGpsKm(this.gpsDest)})`);
    if (this.gpsShip) parts.push(`Ship GPS: ${formatGpsKm(this.gpsShip)}`);

    if (this.gpsOrigin && this.gpsDest && this.gpsShip) {
      const intercept = calculateGpsIntercept(this.gpsOrigin, this.gpsDest, this.gpsShip, qed.radiusKm);
      if (intercept) {
        this.gpsStatusEl.innerHTML = `<strong class="${intercept.inRange ? 'ss-text-ok' : 'ss-text-bad'}">${intercept.inRange ? 'GPS VERIFIED · IN BUBBLE' : 'GPS OFF-SPLINE'}</strong> · ${intercept.lateralOffsetKm} km off-axis · ${intercept.offsetMkmFromDest} Mkm to Dest (${intercept.progressPct}% along ${intercept.laneDistanceMkm} Mkm lane) · <strong>${intercept.coveragePct}% cone coverage</strong>`;
        return;
      }
    }

    if (parts.length === 0) {
      this.gpsStatusEl.textContent =
        'Type /showlocation in chat to copy your exact XYZ coordinates, then paste or click Verify My Position.';
    } else {
      const missing: string[] = [];
      if (!this.gpsOrigin) missing.push('Origin');
      if (!this.gpsDest) missing.push('Dest');
      if (!this.gpsShip) missing.push('Ship');
      this.gpsStatusEl.textContent = `${parts.join(' · ')}${missing.length ? ` — Set ${missing.join(' & ')} for 3D spline check.` : ''}`;
    }
  }

  private renderStaticCalculators(): void {
    this.renderGpsStatus();
    this.renderSnarePlanner();
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
    this.activeKillsEl.textContent = String(f.active_kills ?? 0);
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
    const totalKills = f.total_ship_kills ?? 0;
    const shipLosses = f.total_ship_losses ?? totalLosses;
    const survivalPct = totalSorties > 0 ? Math.max(0, Math.round(((totalSorties - totalLosses) / totalSorties) * 100)) : 100;

    this.kpiSortiesEl.textContent = String(totalSorties);
    this.kpiHelmEl.textContent = formatCompactHours(f.total_helm_s ?? 0);
    this.kpiJumpsEl.textContent = String(f.total_jumps ?? 0);
    this.kpiContractsEl.textContent = String(f.total_contracts ?? 0);
    this.kpiKillsEl.textContent = String(totalKills);
    this.kpiLossesEl.textContent = String(shipLosses);
    this.kpiSurvivalEl.textContent = `${survivalPct}%`;

    this.renderFleetCharts(f.fleet ?? [], f.total_helm_s ?? 0);
    this.renderSortiesLedger(f.recent ?? []);
    this.renderCombatLog(f.combat_log ?? []);
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
            <div class="ss-fleet-row-meta">${row.sorties} flights · ${row.jumps} jumps · ${row.contracts} contracts${(row.kills ?? 0) > 0 ? ` · ${row.kills} kills` : ''}${row.losses > 0 ? ` · ${row.losses} loss` : ''}</div>
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
      this.sortiesTbodyEl.innerHTML = `<tr><td colspan="5" class="ss-muted-text">No flights recorded${this.selectedHullFocus ? ` for ${escapeHtml(this.selectedHullFocus)}` : ''} yet.</td></tr>`;
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

  private renderCombatLog(entries: ShipCombatEntry[]): void {
    const f = this.flight;
    const totalKills = f.total_ship_kills ?? 0;
    const aiKills = f.ai_ship_kills ?? 0;
    const playerKills = f.player_ship_kills ?? 0;
    const totalLosses = f.total_ship_losses ?? 0;
    const kiaCount = f.pilot_kia_count ?? 0;

    const killBreak = totalKills > 0 ? ` (${aiKills} AI · ${playerKills} Player)` : '';
    const kiaBreak = kiaCount > 0 ? ` (${kiaCount} Pilot K.I.A.)` : '';
    this.combatSummaryEl.textContent = `${totalKills} kills${killBreak} · ${totalLosses} losses${kiaBreak}`;

    const rows = this.combatFilter === 'all'
      ? entries
      : entries.filter((ev) => ev.kind === this.combatFilter);

    if (rows.length === 0) {
      const label = this.combatFilter === 'kill' ? 'ship kills' : this.combatFilter === 'loss' ? 'ship losses' : 'ship combat events';
      this.combatTbodyEl.innerHTML = `<tr><td colspan="5" class="ss-muted-text">No ${label} logged yet. Destroyed targets and ship losses stream live from Game.log.</td></tr>`;
      return;
    }

    this.combatTbodyEl.innerHTML = rows
      .map((ev) => {
        const isKill = ev.kind === 'kill';
        const badgeCls = isKill ? 'ss-pill-ok' : 'ss-pill-bad';
        const eventLabel = isKill
          ? (ev.target_kind === 'player' ? 'PLAYER KILL' : 'SHIP KILL')
          : (ev.pilot_kia ? 'PILOT K.I.A.' : 'SHIP LOSS');
        const cause = ev.reason || 'Combat';
        let details = '';
        if (isKill) {
          const kindLabel = ev.target_kind === 'player' ? 'Player-owned hull' : 'AI target';
          details = ev.player_ship ? `${kindLabel} · from ${ev.player_ship}` : kindLabel;
        } else {
          details = ev.killer && ev.killer !== 'Unknown' ? `By ${ev.killer}` : 'Hull destroyed';
        }
        return `
          <tr>
            <td class="ss-mono">${escapeHtml(ev.time)}</td>
            <td><span class="ss-outcome-pill ${badgeCls}">${escapeHtml(eventLabel)}</span></td>
            <td><strong>${escapeHtml(ev.ship)}</strong></td>
            <td class="ss-muted-text">${escapeHtml(cause)}</td>
            <td class="ss-muted-text">${escapeHtml(details)}</td>
          </tr>
        `;
      })
      .join('');
  }

  private renderSnarePlanner(): void {
    const lane = TRADE_LANE_PRESETS.find((l) => l.id === this.selectedLaneId) ?? TRADE_LANE_PRESETS[0];
    const qed = QED_SHIPS.find((q) => q.id === this.selectedQedId) ?? QED_SHIPS[0];

    let effectiveLaneMkm = lane.distanceMkm;
    if (this.gpsOrigin && this.gpsDest) {
      const gpsLaneLenM = Math.hypot(
        this.gpsDest.x - this.gpsOrigin.x,
        this.gpsDest.y - this.gpsOrigin.y,
        this.gpsDest.z - this.gpsOrigin.z,
      );
      if (gpsLaneLenM >= 1e6) {
        effectiveLaneMkm = Number((gpsLaneLenM / 1_000_000_000).toFixed(2));
      }
    }

    const geom = calculateSnareGeometry({
      laneDistanceMkm: effectiveLaneMkm,
      offsetMkmFromDest: this.offsetMkm,
      doglegKm: this.doglegKm,
      qedRadiusKm: qed.radiusKm,
    });

    const snareX = 42 + (geom.snarePosPct / 100) * 356;
    const snareY = 64 + Math.min(24, Math.max(-24, (this.doglegKm / 30) * 24));
    const visualRadius = Math.max(10, Math.min(30, qed.radiusKm * 1.4));
    const bubbleColor = geom.inRange ? (geom.coveragePct >= 75 ? '#53d09f' : '#f6b95e') : '#ff6b72';

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
        <text x="${snareX.toFixed(1)}" y="114" fill="${bubbleColor}" font-size="10" font-weight="700" text-anchor="middle">SNARE (${qed.radiusKm} km · ${geom.coveragePct}%)</text>
        <text x="398" y="24" fill="#53d09f" font-size="10" text-anchor="middle">DESTINATION</text>
      </svg>
    `;

    this.snareReadoutEl.innerHTML = `
      <div class="ss-mini-metric"><span>CONE COVERAGE</span><strong class="${geom.coveragePct >= 75 ? 'ss-text-ok' : 'ss-text-bad'}">${geom.coveragePct}%</strong></div>
      <div class="ss-mini-metric"><span>DRIFT CONE</span><strong>${geom.driftConeWidthKm} km</strong></div>
      <div class="ss-mini-metric"><span>DROP POINT</span><strong>${geom.snarePosPct.toFixed(0)}% al. spline</strong></div>
      <div class="ss-mini-metric"><span>INTERCEPT STATUS</span><strong class="${geom.inRange ? 'ss-text-ok' : 'ss-text-bad'}">${geom.inRange ? 'IN BUBBLE' : 'OUT OF RANGE'}</strong></div>
    `;
    this.snareAdviceEl.textContent = `${geom.dropAdvice} (${lane.note})`;
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
      this.pullTbodyEl.innerHTML = `<tr><td colspan="6" class="ss-muted-text">No snare pulls logged yet. Log an interdiction manually above.</td></tr>`;
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
      `**SynthScan Flight / Piracy Report**`,
      `• Status: ${f.state ?? 'ON_FOOT'} · Vessel: ${f.active_ship && f.active_ship !== '--' ? f.active_ship : 'None'}`,
      `• Total Flights: ${f.total_sorties ?? 0} · Helm Time: ${formatCompactHours(f.total_helm_s ?? 0)} · QT Jumps: ${f.total_jumps ?? 0}`,
      `• Ship Combat: ${f.total_ship_kills ?? 0} kills (${f.ai_ship_kills ?? 0} AI · ${f.player_ship_kills ?? 0} Player) · ${f.total_ship_losses ?? f.total_losses ?? 0} losses`,
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
