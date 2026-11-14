import {
  Body,
  bodyFromRecord,
  forecast,
  type BodyRecord,
  type SiteRecord,
  type Forecast,
} from './daylight_math';
import type { DaylightState, DesktopBridge } from './bridge';
import defaultCatalogueJson from './data/daylight_catalogue.json';

export type ArrivalMode = 'now' | 'minutes' | 'custom';

export interface DaylightViewOptions {
  onCopyNotice?: (msg: string) => void;
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.max(0, Math.round(seconds / 60));
  if (totalMinutes < 60) return `${totalMinutes}m`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${String(minutes).padStart(2, '0')}m`;
}

export function formatLocalStamp(epochSeconds: number, showSeconds = true): string {
  const d = new Date(epochSeconds * 1000);
  const datePart = d.toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
  const timePart = d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: showSeconds ? '2-digit' : undefined,
    hour12: false,
  });
  return `${datePart} · ${timePart}`;
}

export function formatTimeOnly(epochSeconds: number, showSeconds = true): string {
  const d = new Date(epochSeconds * 1000);
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: showSeconds ? '2-digit' : undefined,
    hour12: false,
  });
}

const MAJOR_PLANET_NAMES = new Set([
  'Crusader',
  'Hurston',
  'microTech',
  'ArcCorp',
  'Pyro I',
  'Monox',
  'Bloom',
  'Pyro IV',
  'Terminus',
]);

const DEFAULT_LANDING_ZONES: Record<string, string> = {
  Crusader: 'Orison',
  Hurston: 'Lorville',
  microTech: 'New Babbage',
  ArcCorp: 'Area18',
  Daymar: 'Jumptown',
  Adir: "Prophet's Peak",
};

export class DaylightViewController {
  private container: HTMLElement;
  private bridge: DesktopBridge;
  private options: DaylightViewOptions;

  private bodies: BodyRecord[] = [];
  private sites: SiteRecord[] = [];
  private bodyModels = new Map<string, Body>();

  private selectedSystem = 'Stanton';
  private selectedBody = 'Crusader';
  private selectedSiteName = 'Orison';

  private arrivalMode: ArrivalMode = 'now';
  private offsetMinutes = 15;
  private customDateString = '';

  private verseSearchQuery = '';

  private timerId: number | null = null;
  private lastCalculationResult: Forecast | null = null;
  private lastCalculatedAt = 0;

  private observationModalOpen = false;
  private observationKind: 'sunrise' | 'sunset' = 'sunrise';
  private observationTimeString = '';

  private currentCalibrationText = 'Community estimate · not calibrated';
  private syncStatusText = 'Catalogue ready';

  constructor(container: HTMLElement, bridge: DesktopBridge, options: DaylightViewOptions = {}) {
    this.container = container;
    this.bridge = bridge;
    this.options = options;

    this.loadInitialCatalogue();
    this.renderSkeleton();
    this.bindEvents();
    this.applyPreferences();
    this.recalculate();
    this.startLiveTimer();
  }

  public destroy(): void {
    if (this.timerId !== null) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
  }

  private loadInitialCatalogue(): void {
    const raw = defaultCatalogueJson as {
      bodies: BodyRecord[];
      sites: SiteRecord[];
    };
    this.updateCatalogueData(raw.bodies, raw.sites);
  }

  private updateCatalogueData(bodies: BodyRecord[], sites: SiteRecord[]): void {
    this.bodies = bodies;
    this.sites = sites;
    this.bodyModels.clear();
    for (const b of bodies) {
      try {
        this.bodyModels.set(b.name, bodyFromRecord(b));
      } catch {
        // ignore invalid body record
      }
    }
  }

  public updateFromDaylightState(state?: DaylightState): void {
    if (!state) return;

    if (state.catalogue?.bodies && state.catalogue?.sites) {
      this.updateCatalogueData(state.catalogue.bodies, state.catalogue.sites);
    }

    if (state.preferences) {
      if (state.preferences.system && this.getAvailableSystems().includes(state.preferences.system)) {
        this.selectedSystem = state.preferences.system;
      }
      if (
        state.preferences.body &&
        this.getAvailableBodies(this.selectedSystem).some((b) => b.name === state.preferences?.body)
      ) {
        this.selectedBody = state.preferences.body;
      }
      if (
        state.preferences.site &&
        this.getAvailableSites(this.selectedSystem, this.selectedBody).some((s) => s.name === state.preferences?.site)
      ) {
        this.selectedSiteName = state.preferences.site;
      }
    }

    if (state.calibration && state.calibration[this.selectedBody]) {
      this.currentCalibrationText = state.calibration[this.selectedBody].quality;
    } else if (state.build?.patch) {
      this.currentCalibrationText = `Community estimate · not calibrated for ${state.build.patch}`;
    }

    if (state.sync?.message) {
      this.syncStatusText = state.sync.message;
      const syncEl = this.container.querySelector('#dl-sync-text');
      if (syncEl) syncEl.textContent = this.syncStatusText;
    }

    if (state.notice) {
      if (this.options.onCopyNotice) {
        this.options.onCopyNotice(state.notice.message);
      }
      if (state.notice.ok && this.observationModalOpen) {
        this.closeObservationModal();
      }
    }

    this.updateSystemPills();
    this.populateBodySelect();
    this.populateSiteSelect();
    this.recalculate();
  }

  private getAvailableSystems(): string[] {
    const set = new Set<string>();
    for (const s of this.sites) set.add(s.system);
    const sorted = Array.from(set).sort();
    if (sorted.includes('Stanton') && sorted[0] !== 'Stanton') {
      return ['Stanton', ...sorted.filter((s) => s !== 'Stanton')];
    }
    return sorted;
  }

  private getAvailableBodies(system: string): BodyRecord[] {
    const bodyNames = new Set<string>();
    for (const s of this.sites) {
      if (s.system === system) bodyNames.add(s.body);
    }
    const filtered = this.bodies.filter((b) => bodyNames.has(b.name));

    // Sort major planets first, then alphabetically
    return filtered.sort((a, b) => {
      const aMajor = MAJOR_PLANET_NAMES.has(a.name) ? 0 : 1;
      const bMajor = MAJOR_PLANET_NAMES.has(b.name) ? 0 : 1;
      if (aMajor !== bMajor) return aMajor - bMajor;
      return a.name.localeCompare(b.name);
    });
  }

  private getAvailableSites(system: string, body: string): SiteRecord[] {
    const sites = this.sites.filter((s) => s.system === system && s.body === body);
    const preferredDZ = DEFAULT_LANDING_ZONES[body];

    return sites.sort((a, b) => {
      if (preferredDZ) {
        if (a.name === preferredDZ) return -1;
        if (b.name === preferredDZ) return 1;
      }
      const aCity = a.kind?.toLowerCase().includes('landing zone') || a.kind?.toLowerCase().includes('city') ? 0 : 1;
      const bCity = b.kind?.toLowerCase().includes('landing zone') || b.kind?.toLowerCase().includes('city') ? 0 : 1;
      if (aCity !== bCity) return aCity - bCity;
      return a.name.localeCompare(b.name);
    });
  }

  private searchVerseSites(query: string): SiteRecord[] {
    const q = query.trim().toLowerCase();
    if (!q) return [];

    return this.sites
      .filter((s) => {
        return (
          s.name.toLowerCase().includes(q) ||
          s.body.toLowerCase().includes(q) ||
          s.system.toLowerCase().includes(q) ||
          (s.kind && s.kind.toLowerCase().includes(q))
        );
      })
      .slice(0, 25);
  }

  private applyPreferences(): void {
    const systems = this.getAvailableSystems();
    if (!systems.includes(this.selectedSystem) && systems.length > 0) {
      this.selectedSystem = systems[0];
    }

    const bodies = this.getAvailableBodies(this.selectedSystem);
    if (!bodies.some((b) => b.name === this.selectedBody)) {
      if (this.selectedSystem === 'Stanton' && bodies.some((b) => b.name === 'Crusader')) {
        this.selectedBody = 'Crusader';
      } else {
        this.selectedBody = bodies.length > 0 ? bodies[0].name : '';
      }
    }

    const sites = this.getAvailableSites(this.selectedSystem, this.selectedBody);
    if (!sites.some((s) => s.name === this.selectedSiteName)) {
      const preferred = DEFAULT_LANDING_ZONES[this.selectedBody];
      if (preferred && sites.some((s) => s.name === preferred)) {
        this.selectedSiteName = preferred;
      } else {
        this.selectedSiteName = sites.length > 0 ? sites[0].name : '';
      }
    }
  }

  private startLiveTimer(): void {
    if (this.timerId !== null) clearInterval(this.timerId);
    const setTimerFn =
      typeof window !== 'undefined' && typeof window.setInterval === 'function' ? window.setInterval : setInterval;
    this.timerId = setTimerFn(() => {
      if (this.arrivalMode === 'now') {
        this.recalculate();
      }
    }, 1000) as unknown as number;
  }

  private getEffectiveArrivalTime(): number {
    const now = Date.now() / 1000;
    if (this.arrivalMode === 'now') {
      return now;
    }
    if (this.arrivalMode === 'minutes') {
      return now + Math.max(0, this.offsetMinutes) * 60;
    }
    if (this.customDateString) {
      const parsed = Date.parse(this.customDateString);
      if (!Number.isNaN(parsed)) return parsed / 1000;
    }
    return now;
  }

  private recalculate(): void {
    const bodyModel = this.bodyModels.get(this.selectedBody);
    const site = this.sites.find(
      (s) => s.system === this.selectedSystem && s.body === this.selectedBody && s.name === this.selectedSiteName,
    );

    if (!bodyModel || !site) {
      this.lastCalculationResult = null;
      this.renderEmptyState();
      return;
    }

    const arrivalAt = this.getEffectiveArrivalTime();
    this.lastCalculatedAt = arrivalAt;

    try {
      this.lastCalculationResult = forecast(bodyModel, site.coordinates_km, arrivalAt, 0.0, 3);
      this.renderActiveForecast(bodyModel, site, this.lastCalculationResult);
    } catch {
      this.lastCalculationResult = null;
      this.renderEmptyState('Could not calculate celestial horizon for this coordinate.');
    }
  }

  private renderSkeleton(): void {
    this.container.innerHTML = `
      <div class="ss-daylight-shell">
        <!-- Main Controls Panel -->
        <div class="ss-daylight-controls-card ss-card">
          <!-- Top Row: Systems Navigation & Live Sync Status -->
          <div class="ss-daylight-row ss-daylight-header-row">
            <div class="ss-daylight-nav-group">
              <span class="ss-nav-label">System:</span>
              <div class="ss-daylight-systems-nav" role="tablist" aria-label="Star systems">
                <!-- System buttons injected dynamically -->
              </div>
            </div>
            <div class="ss-daylight-sync-info">
              <span class="ss-daylight-sync-dot"></span>
              <span id="dl-sync-text" class="ss-daylight-sync-text">${this.syncStatusText}</span>
              <button id="dl-refresh-btn" type="button" class="ss-btn ss-btn-sm" title="Refresh public catalogue">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
                Sync
              </button>
            </div>
          </div>

          <!-- Universal Verse Search across all 416 locations -->
          <div class="ss-daylight-field ss-verse-search-field">
            <label class="ss-field-label" for="dl-poi-search">
              Universal Verse Search
              <span class="ss-field-hint">(Instant jump across all 416 Stanton &amp; Pyro landing sites)</span>
            </label>
            <div class="ss-poi-input-wrap">
              <svg class="ss-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
              <input
                id="dl-poi-search"
                class="ss-input ss-daylight-poi-input ss-verse-search-input"
                type="text"
                placeholder="Type any location (e.g. Orison, New Babbage, Lorville, Area18, Ghost Hollow, Jumptown...)"
                autocomplete="off"
              />
              <button id="dl-poi-clear-btn" type="button" class="ss-poi-clear-btn" title="Clear search" aria-label="Clear destination filter">&times;</button>
            </div>
            <div id="dl-poi-dropdown" class="ss-poi-dropdown ss-verse-dropdown" hidden></div>
          </div>

          <!-- Responsive Dropdowns: Planet/Moon and Destination -->
          <div class="ss-daylight-selectors-grid">
            <!-- Celestial Body / Planet / Moon Dropdown -->
            <div class="ss-daylight-field">
              <label class="ss-field-label" for="dl-body-select">Planet / Moon</label>
              <div class="ss-select-wrap">
                <select id="dl-body-select" class="ss-select ss-daylight-select"></select>
              </div>
            </div>

            <!-- Destination Dropdown -->
            <div class="ss-daylight-field">
              <label class="ss-field-label" for="dl-site-select">Destination on Body</label>
              <div class="ss-select-wrap">
                <select id="dl-site-select" class="ss-select ss-daylight-select"></select>
              </div>
            </div>
          </div>

          <!-- Arrival Planning Bar -->
          <div class="ss-daylight-arrival-bar">
            <span class="ss-arrival-title">Arrival Time:</span>
            <div class="ss-arrival-modes">
              <button type="button" class="ss-tab-pill is-active" data-arr="now">Now (Live)</button>
              <button type="button" class="ss-tab-pill" data-arr="minutes">In Minutes</button>
              <button type="button" class="ss-tab-pill" data-arr="custom">Specific Date &amp; Time</button>
            </div>

            <!-- Offset Minutes Quick Chips -->
            <div id="dl-minutes-row" class="ss-arrival-offsets" hidden>
              <button type="button" class="ss-offset-chip" data-mins="5">+5m</button>
              <button type="button" class="ss-offset-chip is-active" data-mins="15">+15m</button>
              <button type="button" class="ss-offset-chip" data-mins="30">+30m</button>
              <button type="button" class="ss-offset-chip" data-mins="45">+45m</button>
              <button type="button" class="ss-offset-chip" data-mins="60">+1h</button>
              <button type="button" class="ss-offset-chip" data-mins="120">+2h</button>
              <div class="ss-custom-mins-wrap">
                <input id="dl-custom-mins-input" class="ss-input ss-mins-input" type="number" min="0" max="10080" value="15" />
                <span class="ss-mins-unit">min</span>
              </div>
            </div>

            <!-- Custom DateTime input -->
            <div id="dl-custom-date-row" class="ss-custom-date-row" hidden>
              <input id="dl-custom-date-input" class="ss-input ss-date-input" type="datetime-local" />
            </div>
          </div>
        </div>

        <!-- Dynamic Solar Hero & Schedule Area -->
        <div id="dl-display-area" class="ss-daylight-display-area">
          <!-- Populated by renderActiveForecast -->
        </div>

        <!-- Action Footer -->
        <div class="ss-daylight-footer-card ss-card">
          <div class="ss-footer-left">
            <button id="dl-copy-forecast-btn" type="button" class="ss-btn ss-btn-accent">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copy Forecast
            </button>
            <button id="dl-observe-btn" type="button" class="ss-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
              Record Sunrise / Sunset
            </button>
          </div>
          <div class="ss-footer-right">
            <span id="dl-toast-msg" class="ss-footer-toast" hidden></span>
            <span id="dl-calib-summary" class="ss-calib-text">${this.currentCalibrationText}</span>
          </div>
        </div>
      </div>

      <!-- Observation Modal Dialog -->
      <div id="dl-observe-modal" class="ss-modal-backdrop" hidden>
        <div class="ss-modal ss-daylight-modal" role="dialog" aria-modal="true" aria-labelledby="dl-modal-title">
          <div class="ss-modal-header">
            <h3 id="dl-modal-title" class="ss-modal-title">Record Observed Horizon Crossing</h3>
            <button id="dl-modal-close-x" type="button" class="ss-close-btn">&times;</button>
          </div>
          <p class="ss-modal-summary" id="dl-modal-destination-desc">
            Record an unobstructed horizon crossing to synchronize the rotation clock for this planetary body.
          </p>
          <div class="ss-modal-form">
            <div class="ss-form-row">
              <label class="ss-field-label">Observed Event:</label>
              <div class="ss-event-toggle">
                <button type="button" class="ss-tab-pill is-active" data-event="sunrise">Sunrise</button>
                <button type="button" class="ss-tab-pill" data-event="sunset">Sunset</button>
              </div>
            </div>
            <div class="ss-form-row">
              <label class="ss-field-label" for="dl-modal-time-input">Observed Local Time (YYYY-MM-DD HH:MM):</label>
              <input id="dl-modal-time-input" class="ss-input ss-grow" type="text" placeholder="2026-11-10 20:30" />
            </div>
            <p id="dl-modal-error" class="ss-modal-error" hidden></p>
            <div class="ss-modal-notes">
              Observation must be from the last 7 days and unobstructed by mountains, buildings, or eclipses.
            </div>
          </div>
          <div class="ss-modal-actions">
            <button id="dl-modal-save-btn" type="button" class="ss-btn ss-btn-accent">Save Local Observation</button>
            <button id="dl-modal-cancel-btn" type="button" class="ss-btn">Cancel</button>
          </div>
        </div>
      </div>
    `;

    this.updateSystemPills();
    this.populateBodySelect();
    this.populateSiteSelect();
  }

  private updateSystemPills(): void {
    const nav = this.container.querySelector('.ss-daylight-systems-nav');
    if (!nav) return;
    const systems = this.getAvailableSystems();
    nav.innerHTML = systems
      .map(
        (sys) => `
        <button type="button" class="ss-system-pill ${sys === this.selectedSystem ? 'is-active' : ''}" data-sys="${sys}">
          <span class="ss-sys-dot"></span>
          ${sys}
        </button>
      `,
      )
      .join('');
  }

  private populateBodySelect(): void {
    const sel = this.container.querySelector<HTMLSelectElement>('#dl-body-select');
    if (!sel) return;

    const bodies = this.getAvailableBodies(this.selectedSystem);
    const majorPlanets = bodies.filter((b) => MAJOR_PLANET_NAMES.has(b.name));
    const moonsAndOthers = bodies.filter((b) => !MAJOR_PLANET_NAMES.has(b.name));

    let html = '';
    if (majorPlanets.length > 0) {
      html += '<optgroup label="Major Planets">';
      for (const b of majorPlanets) {
        const periodHours = (Math.abs(b.period_seconds) / 3600).toFixed(1);
        const selAttr = b.name === this.selectedBody ? 'selected' : '';
        html += `<option value="${b.name}" ${selAttr}>${b.name} (${periodHours}h rotation)</option>`;
      }
      html += '</optgroup>';
    }

    if (moonsAndOthers.length > 0) {
      html += '<optgroup label="Moons &amp; Planetary Bodies">';
      for (const b of moonsAndOthers) {
        const periodHours = (Math.abs(b.period_seconds) / 3600).toFixed(1);
        const selAttr = b.name === this.selectedBody ? 'selected' : '';
        html += `<option value="${b.name}" ${selAttr}>${b.name} (${periodHours}h rotation)</option>`;
      }
      html += '</optgroup>';
    }

    sel.innerHTML = html;
  }

  private populateSiteSelect(): void {
    const sel = this.container.querySelector<HTMLSelectElement>('#dl-site-select');
    if (!sel) return;

    const sites = this.getAvailableSites(this.selectedSystem, this.selectedBody);
    sel.innerHTML = sites
      .map((s) => {
        const kindLabel = s.kind ? ` [${s.kind}]` : '';
        const selAttr = s.name === this.selectedSiteName ? 'selected' : '';
        return `<option value="${s.name}" ${selAttr}>${s.name}${kindLabel}</option>`;
      })
      .join('');
  }

  private renderDropdownResults(): void {
    const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
    if (!dd) return;

    const q = this.verseSearchQuery.trim();
    if (!q) {
      dd.hidden = true;
      dd.innerHTML = '';
      return;
    }

    const matches = this.searchVerseSites(q);
    if (matches.length === 0) {
      dd.innerHTML = `<div class="ss-poi-empty">No verse locations match "${q}".</div>`;
      dd.hidden = false;
      return;
    }

    dd.innerHTML = matches
      .map((s) => {
        const isCurrent =
          s.system === this.selectedSystem && s.body === this.selectedBody && s.name === this.selectedSiteName;
        return `
        <div class="ss-poi-item ${isCurrent ? 'is-selected' : ''}" data-site="${s.name}" data-body="${s.body}" data-system="${s.system}">
          <div class="ss-poi-item-main">
            <span class="ss-poi-name">${s.name}</span>
            <span class="ss-poi-badge">${s.kind ?? 'Surface Location'}</span>
          </div>
          <span class="ss-poi-location-tag">${s.system} &middot; ${s.body}</span>
        </div>
      `;
      })
      .join('');
    dd.hidden = false;
  }

  private bindEvents(): void {
    // Top-level delegated click handler
    this.container.addEventListener('click', (e) => {
      const target = e.target as HTMLElement;

      // System switcher pills
      const sysBtn = target.closest<HTMLButtonElement>('.ss-system-pill');
      if (sysBtn && sysBtn.dataset.sys) {
        this.selectedSystem = sysBtn.dataset.sys;
        this.updateSystemPills();
        const available = this.getAvailableBodies(this.selectedSystem);
        if (available.length > 0) {
          if (this.selectedSystem === 'Stanton' && available.some((b) => b.name === 'Crusader')) {
            this.selectedBody = 'Crusader';
          } else {
            this.selectedBody = available[0].name;
          }
          const sites = this.getAvailableSites(this.selectedSystem, this.selectedBody);
          const preferred = DEFAULT_LANDING_ZONES[this.selectedBody];
          if (preferred && sites.some((s) => s.name === preferred)) {
            this.selectedSiteName = preferred;
          } else {
            this.selectedSiteName = sites.length > 0 ? sites[0].name : '';
          }
        }
        this.populateBodySelect();
        this.populateSiteSelect();
        this.savePreferences();
        this.recalculate();
        return;
      }

      // Universal verse search item click
      const poiItem = target.closest<HTMLElement>('.ss-poi-item');
      if (poiItem && poiItem.dataset.site && poiItem.dataset.body && poiItem.dataset.system) {
        this.selectedSystem = poiItem.dataset.system;
        this.selectedBody = poiItem.dataset.body;
        this.selectedSiteName = poiItem.dataset.site;

        const searchInput = this.container.querySelector<HTMLInputElement>('#dl-poi-search');
        if (searchInput) searchInput.value = '';
        this.verseSearchQuery = '';

        const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
        if (dd) dd.hidden = true;

        this.updateSystemPills();
        this.populateBodySelect();
        this.populateSiteSelect();
        this.savePreferences();
        this.recalculate();
        return;
      }

      // Arrival mode pills
      const arrPill = target.closest<HTMLButtonElement>('.ss-tab-pill[data-arr]');
      if (arrPill && arrPill.dataset.arr) {
        this.container.querySelectorAll('.ss-tab-pill[data-arr]').forEach((p) => p.classList.remove('is-active'));
        arrPill.classList.add('is-active');
        this.arrivalMode = arrPill.dataset.arr as ArrivalMode;
        this.updateArrivalModeUI();
        this.recalculate();
        return;
      }

      // Offset minute chips
      const offsetChip = target.closest<HTMLButtonElement>('.ss-offset-chip');
      if (offsetChip && offsetChip.dataset.mins) {
        this.container.querySelectorAll('.ss-offset-chip').forEach((c) => c.classList.remove('is-active'));
        offsetChip.classList.add('is-active');
        this.offsetMinutes = parseInt(offsetChip.dataset.mins, 10) || 15;
        const numInput = this.container.querySelector<HTMLInputElement>('#dl-custom-mins-input');
        if (numInput) numInput.value = String(this.offsetMinutes);
        this.recalculate();
        return;
      }

      // Observation event toggle (sunrise vs sunset)
      const eventPill = target.closest<HTMLButtonElement>('.ss-event-toggle .ss-tab-pill');
      if (eventPill && eventPill.dataset.event) {
        this.container
          .querySelectorAll('.ss-event-toggle .ss-tab-pill')
          .forEach((p) => p.classList.remove('is-active'));
        eventPill.classList.add('is-active');
        this.observationKind = eventPill.dataset.event as 'sunrise' | 'sunset';
        return;
      }

      // If clicked outside dropdown, hide dropdown
      if (!target.closest('.ss-verse-search-field')) {
        const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
        if (dd) dd.hidden = true;
      }
    });

    // Body selection changed
    const bodySelect = this.container.querySelector<HTMLSelectElement>('#dl-body-select');
    if (bodySelect) {
      bodySelect.addEventListener('change', () => {
        this.selectedBody = bodySelect.value;
        const sites = this.getAvailableSites(this.selectedSystem, this.selectedBody);
        const preferred = DEFAULT_LANDING_ZONES[this.selectedBody];
        if (preferred && sites.some((s) => s.name === preferred)) {
          this.selectedSiteName = preferred;
        } else {
          this.selectedSiteName = sites.length > 0 ? sites[0].name : '';
        }
        this.populateSiteSelect();
        this.savePreferences();
        this.recalculate();
      });
    }

    // Site destination dropdown changed
    const siteSelect = this.container.querySelector<HTMLSelectElement>('#dl-site-select');
    if (siteSelect) {
      siteSelect.addEventListener('change', () => {
        this.selectedSiteName = siteSelect.value;
        this.savePreferences();
        this.recalculate();
      });
    }

    // Verse Search Input
    const searchInput = this.container.querySelector<HTMLInputElement>('#dl-poi-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        this.verseSearchQuery = searchInput.value;
        this.renderDropdownResults();
      });
      searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim()) {
          this.verseSearchQuery = searchInput.value;
          this.renderDropdownResults();
        }
      });
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
          if (dd) dd.hidden = true;
        } else if (e.key === 'Enter') {
          const matches = this.searchVerseSites(searchInput.value);
          if (matches.length > 0) {
            const first = matches[0];
            this.selectedSystem = first.system;
            this.selectedBody = first.body;
            this.selectedSiteName = first.name;
            searchInput.value = '';
            this.verseSearchQuery = '';
            const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
            if (dd) dd.hidden = true;

            this.updateSystemPills();
            this.populateBodySelect();
            this.populateSiteSelect();
            this.savePreferences();
            this.recalculate();
          }
        }
      });
    }

    // Clear search button
    const clearBtn = this.container.querySelector('#dl-poi-clear-btn');
    if (clearBtn && searchInput) {
      clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        this.verseSearchQuery = '';
        const dd = this.container.querySelector<HTMLElement>('#dl-poi-dropdown');
        if (dd) dd.hidden = true;
        searchInput.focus();
      });
    }

    // Custom minutes number input
    const numInput = this.container.querySelector<HTMLInputElement>('#dl-custom-mins-input');
    if (numInput) {
      numInput.addEventListener('change', () => {
        const val = parseInt(numInput.value, 10);
        this.offsetMinutes = Number.isNaN(val) ? 15 : Math.max(0, val);
        this.recalculate();
      });
    }

    // Custom datetime input
    const dateInput = this.container.querySelector<HTMLInputElement>('#dl-custom-date-input');
    if (dateInput) {
      dateInput.addEventListener('change', () => {
        this.customDateString = dateInput.value;
        this.recalculate();
      });
    }

    // Copy forecast action
    const copyBtn = this.container.querySelector('#dl-copy-forecast-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        this.copyForecastToClipboard();
      });
    }

    // Sync button
    const refreshBtn = this.container.querySelector('#dl-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        void this.bridge.sendCommand({ action: 'daylight_refresh' });
        this.showToast('Catalogue refresh requested…');
      });
    }

    // Open observation modal
    const observeBtn = this.container.querySelector('#dl-observe-btn');
    if (observeBtn) {
      observeBtn.addEventListener('click', () => {
        this.openObservationModal();
      });
    }

    // Close observation modal
    const closeXBtn = this.container.querySelector('#dl-modal-close-x');
    const cancelModalBtn = this.container.querySelector('#dl-modal-cancel-btn');
    if (closeXBtn) closeXBtn.addEventListener('click', () => this.closeObservationModal());
    if (cancelModalBtn) cancelModalBtn.addEventListener('click', () => this.closeObservationModal());

    // Save observation
    const saveModalBtn = this.container.querySelector('#dl-modal-save-btn');
    if (saveModalBtn) {
      saveModalBtn.addEventListener('click', () => {
        this.saveObservation();
      });
    }
  }

  private updateArrivalModeUI(): void {
    const minsRow = this.container.querySelector<HTMLElement>('#dl-minutes-row');
    const dateRow = this.container.querySelector<HTMLElement>('#dl-custom-date-row');
    if (minsRow) minsRow.hidden = this.arrivalMode !== 'minutes';
    if (dateRow) dateRow.hidden = this.arrivalMode !== 'custom';
  }

  private savePreferences(): void {
    void this.bridge.sendCommand({
      action: 'daylight_preferences',
      system: this.selectedSystem,
      body: this.selectedBody,
      site: this.selectedSiteName,
    });
  }

  private showToast(msg: string): void {
    const toast = this.container.querySelector<HTMLElement>('#dl-toast-msg');
    if (!toast) return;
    toast.textContent = msg;
    toast.hidden = false;
    setTimeout(() => {
      toast.hidden = true;
    }, 4000);
  }

  private openObservationModal(): void {
    this.observationModalOpen = true;
    const modal = this.container.querySelector<HTMLElement>('#dl-observe-modal');
    const desc = this.container.querySelector<HTMLElement>('#dl-modal-destination-desc');
    const timeInput = this.container.querySelector<HTMLInputElement>('#dl-modal-time-input');
    const errorEl = this.container.querySelector<HTMLElement>('#dl-modal-error');

    if (desc) {
      desc.textContent = `Observing at ${this.selectedSiteName} (${this.selectedBody}, ${this.selectedSystem}). Unobstructed horizon crossing synchronizes the rotation clock for this planetary body.`;
    }
    if (timeInput) {
      const now = new Date();
      const pad = (n: number) => String(n).padStart(2, '0');
      timeInput.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
      this.observationTimeString = timeInput.value;
    }
    if (errorEl) {
      errorEl.hidden = true;
      errorEl.textContent = '';
    }
    if (modal) modal.hidden = false;
  }

  private closeObservationModal(): void {
    this.observationModalOpen = false;
    const modal = this.container.querySelector<HTMLElement>('#dl-observe-modal');
    if (modal) modal.hidden = true;
  }

  private saveObservation(): void {
    const timeInput = this.container.querySelector<HTMLInputElement>('#dl-modal-time-input');
    const errorEl = this.container.querySelector<HTMLElement>('#dl-modal-error');
    if (!timeInput) return;

    const val = timeInput.value.trim();
    const parsed = Date.parse(val.replace(' ', 'T'));
    if (Number.isNaN(parsed)) {
      if (errorEl) {
        errorEl.textContent = 'Use valid date format: YYYY-MM-DD HH:MM';
        errorEl.hidden = false;
      }
      return;
    }

    const epochSeconds = parsed / 1000;
    const now = Date.now() / 1000;
    if (now - epochSeconds > 7 * 86400 || epochSeconds > now + 300) {
      if (errorEl) {
        errorEl.textContent = 'Observation must be from within the last 7 days.';
        errorEl.hidden = false;
      }
      return;
    }

    const defaultSig = (defaultCatalogueJson as { signature?: string }).signature ?? '';

    void this.bridge.sendCommand({
      action: 'daylight_observe',
      system: this.selectedSystem,
      body: this.selectedBody,
      site: this.selectedSiteName,
      kind: this.observationKind,
      observed_at: epochSeconds,
      signature: defaultSig,
    });

    this.showToast(`Saved ${this.observationKind} observation for ${this.selectedBody}.`);
    this.closeObservationModal();
    this.recalculate();
  }

  private renderEmptyState(message = 'Select a valid planetary destination to forecast daylight.'): void {
    const area = this.container.querySelector('#dl-display-area');
    if (!area) return;
    area.innerHTML = `
      <div class="ss-daylight-empty-card ss-card">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="ss-empty-icon"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        <p class="ss-empty-text">${message}</p>
      </div>
    `;
  }

  private renderActiveForecast(body: Body, site: SiteRecord, fc: Forecast): void {
    const area = this.container.querySelector('#dl-display-area');
    if (!area) return;

    const isDaylight = fc.daylight;
    const arrivalTime = fc.at;
    const now = Date.now() / 1000;
    const isLive = Math.abs(arrivalTime - now) < 5;

    // Status label
    let statusTitle = isDaylight ? 'DAYLIGHT ON ARRIVAL' : 'NIGHT ON ARRIVAL';
    let statusClass = isDaylight ? 'is-daylight' : 'is-night';
    if (fc.continuous === 'daylight') {
      statusTitle = 'CONTINUOUS DAYLIGHT';
      statusClass = 'is-continuous-daylight';
    } else if (fc.continuous === 'night') {
      statusTitle = 'CONTINUOUS NIGHT';
      statusClass = 'is-continuous-night';
    }

    const altDeg = fc.altitude_degrees.toFixed(1);
    const altSign = fc.altitude_degrees >= 0 ? '+' : '';

    // Horizon crossing events
    const nextSunriseText = fc.sunrise
      ? `${formatLocalStamp(fc.sunrise)} (in ${formatDuration(fc.sunrise - arrivalTime)})`
      : 'No sunrise in this rotation';

    const nextSunsetText = fc.sunset
      ? `${formatLocalStamp(fc.sunset)} (in ${formatDuration(fc.sunset - arrivalTime)})`
      : 'No sunset in this rotation';

    // Upcoming daylight windows
    const windowsHtml =
      fc.windows.length > 0
        ? fc.windows
            .slice(0, 3)
            .map(([start, end], idx) => {
              const dur = formatDuration(end - start);
              const startStr = formatLocalStamp(start);
              const endStr = formatTimeOnly(end);
              return `
                <div class="ss-window-item">
                  <div class="ss-window-badge">Window ${idx + 1}</div>
                  <div class="ss-window-times">
                    <span class="ss-window-range">${startStr} &rarr; ${endStr}</span>
                    <span class="ss-window-duration">${dur}</span>
                  </div>
                </div>
              `;
            })
            .join('')
        : `<div class="ss-no-windows">${fc.daylight ? 'Continuous sunlight during this planetary cycle.' : 'No daylight windows projected for this cycle.'}</div>`;

    // Coordinates and planetary rotation
    const periodHours = (body.period / 3600).toFixed(2);
    const radiusKm = body.radius.toLocaleString();
    const coordsStr = site.coordinates_km.map((c) => c.toFixed(1)).join(', ');
    const note =
      site.note ?? 'Spherical horizon estimate. Local mountains, craters and clouds may modify visible sunlight.';

    // Generate timeline SVG
    const timelineSvg = this.generateTimelineSvg(fc);

    area.innerHTML = `
      <div class="ss-daylight-hero ${statusClass}">
        <!-- Left: Primary Solar Elevation Gauge & Status -->
        <div class="ss-hero-left">
          <div class="ss-hero-status-tag">
            <span class="ss-hero-status-indicator"></span>
            ${statusTitle}
          </div>
          <div class="ss-hero-main-metric">
            <span class="ss-altitude-number">${altSign}${altDeg}&deg;</span>
            <span class="ss-altitude-label">Solar Elevation (${isDaylight ? 'Above Horizon' : 'Below Horizon'})</span>
          </div>
          <div class="ss-hero-arrival-stamp">
            ${isLive ? '<span class="ss-live-badge">LIVE</span>' : '<span class="ss-plan-badge">PROJECTED</span>'}
            <span class="ss-arrival-stamp-text">${formatLocalStamp(arrivalTime)}</span>
          </div>
        </div>

        <!-- Right: Sun Crossings Card -->
        <div class="ss-hero-right">
          <div class="ss-crossing-card">
            <div class="ss-crossing-row">
              <div class="ss-crossing-icon ss-sunrise-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v6M4.93 4.93l4.24 4.24M2 18h20M20 18a8 8 0 1 0-16 0"/><path d="m16 10-4-4-4 4"/></svg>
              </div>
              <div class="ss-crossing-content">
                <span class="ss-crossing-title">Next Sunrise</span>
                <span class="ss-crossing-stamp">${nextSunriseText}</span>
              </div>
            </div>
            <div class="ss-crossing-row">
              <div class="ss-crossing-icon ss-sunset-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 10V2M4.93 4.93l4.24 4.24M2 18h20M20 18a8 8 0 1 0-16 0"/><path d="m8 6 4 4 4-4"/></svg>
              </div>
              <div class="ss-crossing-content">
                <span class="ss-crossing-title">Next Sunset</span>
                <span class="ss-crossing-stamp">${nextSunsetText}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Orbital Timeline Strip -->
      <div class="ss-daylight-timeline-card ss-card">
        <div class="ss-timeline-header">
          <span class="ss-timeline-title">Orbital Daylight Timeline</span>
          <div class="ss-timeline-legend">
            <span class="ss-leg-item"><span class="ss-leg-box ss-leg-day"></span> Daylight</span>
            <span class="ss-leg-item"><span class="ss-leg-box ss-leg-night"></span> Night</span>
            <span class="ss-leg-item"><span class="ss-leg-needle"></span> Arrival Marker</span>
          </div>
        </div>
        <div class="ss-timeline-render-wrap">
          ${timelineSvg}
        </div>
      </div>

      <!-- Detail Grid: Upcoming Windows & Planetary Physics -->
      <div class="ss-daylight-info-grid">
        <div class="ss-windows-card ss-card">
          <div class="ss-card-header">
            <span class="ss-card-title">Upcoming Daylight Windows</span>
            <span class="ss-card-badge">Next Rotations</span>
          </div>
          <div class="ss-windows-list">
            ${windowsHtml}
          </div>
        </div>

        <div class="ss-physics-card ss-card">
          <div class="ss-card-header">
            <span class="ss-card-title">Celestial &amp; Terrain Data</span>
            <span class="ss-card-badge">${body.name}</span>
          </div>
          <div class="ss-physics-list">
            <div class="ss-physics-item">
              <span class="ss-physics-label">Rotation Period:</span>
              <span class="ss-physics-value">${periodHours} real hours</span>
            </div>
            <div class="ss-physics-item">
              <span class="ss-physics-label">Body Radius:</span>
              <span class="ss-physics-value">${radiusKm} km</span>
            </div>
            <div class="ss-physics-item">
              <span class="ss-physics-label">Surface Coordinates:</span>
              <span class="ss-physics-value">[${coordsStr}] km</span>
            </div>
            <div class="ss-physics-note">
              ${note}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  private generateTimelineSvg(fc: Forecast): string {
    const totalDuration = (fc.period_seconds * 2) || 86400;
    if (totalDuration <= 0) return '';

    const width = 1000;
    const height = 48;
    const arrivalX = 0; // Arrival time is t=0

    let rects = '';
    const windows = fc.continuous === 'daylight' ? [[fc.at, fc.at + totalDuration] as [number, number]] : fc.windows;
    for (const [start, end] of windows) {
      const left = Math.max(fc.at, start);
      const right = Math.min(fc.at + totalDuration, end);
      if (right > left) {
        const x1 = ((left - fc.at) / totalDuration) * width;
        const x2 = ((right - fc.at) / totalDuration) * width;
        const w = Math.max(0, x2 - x1);
        if (w > 0) {
          rects += `<rect x="${x1.toFixed(1)}" y="4" width="${w.toFixed(1)}" height="${height - 8}" fill="#ffd166" rx="4" opacity="0.9" />`;
        }
      }
    }

    // Time ticks every 1/4th duration
    let ticks = '';
    for (let i = 0; i <= 4; i++) {
      const frac = i / 4;
      const x = frac * width;
      const tickSeconds = fc.at + frac * totalDuration;
      const label = formatTimeOnly(tickSeconds, false);
      const anchor = i === 0 ? 'start' : i === 4 ? 'end' : 'middle';
      ticks += `
        <line x1="${x.toFixed(1)}" y1="0" x2="${x.toFixed(1)}" y2="${height}" stroke="rgba(167, 194, 219, 0.15)" stroke-dasharray="2,2" />
        <text x="${x.toFixed(1)}" y="${height + 12}" fill="#98a3b3" font-size="10" text-anchor="${anchor}">${label}</text>
      `;
    }

    return `
      <svg class="ss-timeline-svg" viewBox="0 0 ${width} ${height + 16}" width="100%" height="100%" preserveAspectRatio="none">
        <!-- Night background band -->
        <rect x="0" y="4" width="${width}" height="${height - 8}" fill="#1b2433" rx="4" />
        <!-- Sunlight windows -->
        ${rects}
        <!-- Ticks -->
        ${ticks}
        <!-- Arrival needle at x=0 -->
        <line x1="${arrivalX}" y1="0" x2="${arrivalX}" y2="${height}" stroke="#62ccff" stroke-width="3" />
        <circle cx="${arrivalX + 2}" cy="4" r="3" fill="#62ccff" />
      </svg>
    `;
  }

  private copyForecastToClipboard(): void {
    if (!this.lastCalculationResult) return;
    const fc = this.lastCalculationResult;
    const bodyModel = this.bodyModels.get(this.selectedBody);
    const site = this.sites.find(
      (s) => s.system === this.selectedSystem && s.body === this.selectedBody && s.name === this.selectedSiteName,
    );

    const isDaylight = fc.daylight;
    const stateStr = isDaylight ? 'DAYLIGHT' : 'NIGHT';
    const altStr = `${fc.altitude_degrees >= 0 ? '+' : ''}${fc.altitude_degrees.toFixed(1)}°`;
    const arrivalStr = formatLocalStamp(fc.at);

    const sunriseStr = fc.sunrise ? `${formatLocalStamp(fc.sunrise)} (in ${formatDuration(fc.sunrise - fc.at)})` : 'None';
    const sunsetStr = fc.sunset ? `${formatLocalStamp(fc.sunset)} (in ${formatDuration(fc.sunset - fc.at)})` : 'None';

    const windowsStr =
      fc.windows.length > 0
        ? fc.windows
            .slice(0, 3)
            .map(([s, e], i) => `  ${i + 1}. ${formatLocalStamp(s)} -> ${formatTimeOnly(e)} (${formatDuration(e - s)})`)
            .join('\n')
        : '  Continuous light or night during this planetary cycle';

    const text = [
      `SynthScan Day/Night Forecast · ${this.selectedSiteName} (${this.selectedBody}, ${this.selectedSystem})`,
      `Status on Arrival: ${stateStr} (${altStr} elevation)`,
      `Arrival Time: ${arrivalStr}`,
      `Next Sunrise: ${sunriseStr}`,
      `Next Sunset: ${sunsetStr}`,
      `Upcoming Daylight Windows:`,
      windowsStr,
      `Rotation: ${bodyModel ? (bodyModel.period / 3600).toFixed(2) : '?'} hours · Coordinates: [${site?.coordinates_km.map((c) => c.toFixed(0)).join(', ')}] km`,
      `Calibration: ${this.currentCalibrationText}`,
    ].join('\n');

    if (navigator?.clipboard?.writeText) {
      void navigator.clipboard.writeText(text);
    }

    void this.bridge.sendCommand({
      action: 'daylight_copy_forecast',
      system: this.selectedSystem,
      body: this.selectedBody,
      site: this.selectedSiteName,
      text,
    });

    this.showToast('Daylight forecast copied to clipboard!');
  }
}
