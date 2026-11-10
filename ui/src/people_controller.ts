import {
  ACTION_LIMIT,
  BuyerWatch,
  CompanionNotice,
  DesktopBridge,
  InviteQueueState,
  MarketCatalogItem,
  PeopleSnapshot,
  Player,
  normalizePlayer,
} from './bridge';
import { personColor, splitTags, tagColor } from './colors';
import { DesktopViewsManager } from './desktop_views';

export const ROW_HEIGHT_PX = 40;

export interface ScrollAnchorState {
  anchorId: string;
  offsetWithinRow: number;
  scrollTop: number;
  scrollLeft: number;
}

export class DesktopAppController {
  private readonly root: HTMLElement;
  private readonly bridge: DesktopBridge;
  private unsubscribe: (() => void) | null = null;
  private desktopViews: DesktopViewsManager | null = null;

  private snapshot: PeopleSnapshot | null = null;
  private activeMode: PeopleSnapshot['mode'] = 'people';
  private sourceIndex = 0; // 0: Shard, 1: Search, 2: Tagged, 3: Friends
  private taggedOnly = false;
  private searchQuery = '';
  private previousViewSignature = '';

  // Selection state (preserved across snapshots)
  private selectedIds = new Set<string>();
  private selectionAnchorId = '';
  private actionSelectedIds = new Set<string>();
  private actionSelectionAnchorId = '';
  private actionEditorSignature = '';

  // Keyed DOM row maps: never recreate unchanged rows
  private rosterRowMap = new Map<string, HTMLTableRowElement>();
  private rosterRowSignature = new Map<string, string>();
  private actionRowMap = new Map<string, HTMLTableRowElement>();
  private actionRowSignature = new Map<string, string>();
  private watchRowMap = new Map<string, HTMLTableRowElement>();

  // Filtered roster state
  private filteredPeople: Player[] = [];
  private actionPeople: Player[] = [];

  // Buyer alerts state
  private marketSearch = '';
  private selectedMarketItemId = 0;
  private selectedWatchId = '';
  private showMatches = false;

  // Confirmation / Queue modal state
  private modalOpen = false;
  private modalMode: 'confirm_friend' | 'confirm_party' | 'queue_report' = 'confirm_party';
  private modalRecipients: Player[] = [];
  private modalResend = false;

  // Home recap session toggle
  private homeShowPrevious = false;
  private virtualScrollTop = 0;
  private virtualScrollLeft = 0;

  // Instrumentation counters for 500-player regression verification
  public domRowCreatedCount = 0;
  public domRowUpdatedCount = 0;
  public domRowRemovedCount = 0;
  public lastUpdatedRowIds: string[] = [];

  // Cached DOM references
  private rosterScrollEl!: HTMLElement;
  private rosterTbodyEl!: HTMLTableSectionElement;
  private actionScrollEl!: HTMLElement;
  private actionTbodyEl!: HTMLTableSectionElement;
  private searchInputEl!: HTMLInputElement;
  private sourceSelectEl!: HTMLSelectElement;
  private taggedOnlyEl!: HTMLInputElement;
  private rosterStatusEl!: HTMLElement;
  private selectionSummaryEl!: HTMLElement;
  private actionHeaderEl!: HTMLElement;
  private stageTagSelectEl!: HTMLSelectElement;
  private applyTagSelectEl!: HTMLSelectElement;
  private tagDraftInputEl!: HTMLInputElement;
  private joinAlertsCheckboxEl!: HTMLInputElement;
  private queueStatusEl!: HTMLElement;
  private footerStatusEl!: HTMLElement;

  // Buttons
  private stageSelectedBtn!: HTMLButtonElement;
  private removeActionBtn!: HTMLButtonElement;
  private clearActionsBtn!: HTMLButtonElement;
  private stageByTagBtn!: HTMLButtonElement;
  private stageFriendsBtn!: HTMLButtonElement;
  private stageOrgBtn!: HTMLButtonElement;
  private addPresetTagBtn!: HTMLButtonElement;
  private applyTagsBtn!: HTMLButtonElement;
  private clearTagsBtn!: HTMLButtonElement;
  private sendFriendsBtn!: HTMLButtonElement;
  private invitePartyBtn!: HTMLButtonElement;
  private viewQueueBtn!: HTMLButtonElement;
  private pauseQueueBtn!: HTMLButtonElement;
  private cancelQueueBtn!: HTMLButtonElement;

  // Views & Modal
  private peopleSectionEl!: HTMLElement;
  private marketSectionEl!: HTMLElement;
  private homeSectionEl!: HTMLElement;
  private settingsSectionEl!: HTMLElement;
  private modalBackdropEl!: HTMLElement;
  private modalTitleEl!: HTMLElement;
  private modalSummaryEl!: HTMLElement;
  private modalTbodyEl!: HTMLTableSectionElement;
  private modalResendWrapEl!: HTMLElement;
  private modalResendCheckboxEl!: HTMLInputElement;
  private modalConfirmBtn!: HTMLButtonElement;
  private modalCancelBtn!: HTMLButtonElement;
  private modalPauseBtn!: HTMLButtonElement;
  private modalStopQueueBtn!: HTMLButtonElement;

  // Org Importer modal DOM elements
  private openOrgImportBtn!: HTMLButtonElement;
  private orgModalBackdropEl!: HTMLElement;
  private orgImportSymbolInput!: HTMLInputElement;
  private orgImportTagSelect!: HTMLSelectElement;
  private orgImportAlertCheckbox!: HTMLInputElement;
  private orgImportStatusEl!: HTMLElement;
  private orgImportSubmitBtn!: HTMLButtonElement;
  private orgImportCancelBtn!: HTMLButtonElement;

  // Buyer alerts DOM elements
  private marketSearchInputEl!: HTMLInputElement;
  private marketItemSelectEl!: HTMLSelectElement;
  private marketQualityInputEl!: HTMLInputElement;
  private marketPriceInputEl!: HTMLInputElement;
  private marketUnitInputEl!: HTMLInputElement;
  private marketWatchesTbodyEl!: HTMLTableSectionElement;
  private marketNoticesTbodyEl!: HTMLTableSectionElement;
  private marketNoticesHeadingEl!: HTMLElement;
  private marketShowMatchesBtn!: HTMLButtonElement;

  constructor(root: HTMLElement, bridge: DesktopBridge) {
    this.root = root;
    this.bridge = bridge;
    this.buildShell();
    this.unsubscribe = this.bridge.subscribePeople((snap) => {
      this.onSnapshot(snap);
    });
  }

  public destroy(): void {
    if (this.desktopViews) {
      this.desktopViews.destroy();
      this.desktopViews = null;
    }
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
  }

  public getFilteredPeople(): Player[] {
    return this.filteredPeople;
  }

  public getActionPeople(): Player[] {
    return this.actionPeople;
  }

  public getSelectedIds(): string[] {
    return Array.from(this.selectedIds);
  }

  public getActionSelectedIds(): string[] {
    return Array.from(this.actionSelectedIds);
  }

  public getRosterRowElement(playerId: string): HTMLTableRowElement | undefined {
    return this.rosterRowMap.get(playerId);
  }

  public getActionRowElement(playerId: string): HTMLTableRowElement | undefined {
    return this.actionRowMap.get(playerId);
  }

  public isModalOpen(): boolean {
    return this.modalOpen;
  }

  public getScrollAnchor(): ScrollAnchorState {
    const scrollTop = Math.round(this.virtualScrollTop);
    const scrollLeft = Math.round(this.virtualScrollLeft);
    const topIndex = Math.max(
      0,
      Math.min(
        this.filteredPeople.length - 1,
        Math.floor(scrollTop / ROW_HEIGHT_PX),
      ),
    );
    const anchorId =
      topIndex >= 0 && topIndex < this.filteredPeople.length
        ? this.filteredPeople[topIndex].id
        : '';
    const offsetWithinRow = scrollTop - topIndex * ROW_HEIGHT_PX;
    return { anchorId, offsetWithinRow, scrollTop, scrollLeft };
  }

  public setRosterScroll(scrollTop: number, scrollLeft = 0): void {
    this.virtualScrollTop = Math.max(0, Math.round(scrollTop));
    this.virtualScrollLeft = Math.max(0, Math.round(scrollLeft));
    this.rosterScrollEl.scrollTop = this.virtualScrollTop;
    this.rosterScrollEl.scrollLeft = this.virtualScrollLeft;
  }

  private buildShell(): void {
    this.root.innerHTML = `
      <div class="ss-app-layout">
        <aside class="ss-app-sidebar" id="ss-app-sidebar"></aside>
        <main class="ss-app-main" id="ss-app-main">
          <div class="ss-shell">
            <header class="ss-topbar">
              <div class="ss-brand">
                <span class="ss-brand-badge" aria-hidden="true">◆</span>
                <div>
                  <h1 class="ss-page-title" id="ss-page-title">People</h1>
                  <p class="ss-page-subtitle" id="ss-page-subtitle">A familiar face in a very large universe.</p>
                </div>
              </div>
              <nav class="ss-mode-tabs" role="tablist" aria-label="Workspace views">
                <button type="button" class="ss-tab is-active" data-mode="people" role="tab" aria-selected="true">Shard &amp; Friends</button>
                <button type="button" class="ss-tab" data-mode="buyer_alerts" role="tab" aria-selected="false">Buyer Alerts</button>
                <button type="button" class="ss-tab ss-tab-hosted-hidden" data-mode="home" role="tab" aria-selected="false">Session Recap</button>
                <button type="button" class="ss-tab ss-tab-hosted-hidden" data-mode="settings" role="tab" aria-selected="false">Settings &amp; Modules</button>
              </nav>
            </header>

            <section id="ss-view-people" class="ss-view">
          <div class="ss-people-grid">
            <!-- Left Column: Roster -->
            <div class="ss-card ss-roster-pane">
              <div class="ss-toolbar-row">
                <input id="people-search-input" class="ss-input ss-grow" type="text" placeholder="Filter this list by handle or tag" autocomplete="off" />
                <button id="people-clear-btn" type="button" class="ss-btn">Clear</button>
                <button id="people-find-btn" type="button" class="ss-btn ss-btn-accent">Find player</button>
              </div>
              <div class="ss-toolbar-row ss-toolbar-sub">
                <select id="people-source-select" class="ss-select" aria-label="Player list source">
                  <option value="0">Shard members</option>
                  <option value="1">Handle search results</option>
                  <option value="2">Saved player tags</option>
                  <option value="3">Friends</option>
                </select>
                <label class="ss-checkbox-label">
                  <input id="people-tagged-only" type="checkbox" />
                  <span>Tagged only</span>
                </label>
                <div class="ss-legend" aria-label="Relationship color priority">
                  <span class="ss-legend-dot ss-dot-self">You</span>
                  <span class="ss-legend-dot ss-dot-party">Party</span>
                  <span class="ss-legend-dot ss-dot-friend">Friend</span>
                </div>
              </div>
              <div class="ss-pane-meta">
                <span id="people-roster-status" class="ss-status-line">Loading player list…</span>
                <span class="ss-hint-line">Players · click to select / deselect</span>
              </div>
              <div id="people-roster-scroll" class="ss-table-scroll" tabindex="0" role="region" aria-label="Player roster">
                <table class="ss-table" id="people-roster-table">
                  <thead>
                    <tr>
                      <th class="col-player">PLAYER</th>
                      <th class="col-tags">TAGS</th>
                      <th class="col-rel">RELATIONSHIP</th>
                    </tr>
                  </thead>
                  <tbody id="people-roster-tbody"></tbody>
                </table>
              </div>
              <div class="ss-roster-footer">
                <button id="stage-selected-btn" type="button" class="ss-btn ss-btn-accent">Add to actions →</button>
                <span id="people-selection-summary" class="ss-muted-text">0 selected · 0 eligible</span>
              </div>
            </div>

            <!-- Right Column: Action List + Tagging & Social Queue -->
            <div class="ss-right-column">
              <div class="ss-card ss-actions-pane">
                <div class="ss-toolbar-row">
                  <button id="people-refresh-btn" type="button" class="ss-btn">Refresh shard</button>
                  <button id="remove-action-btn" type="button" class="ss-btn">Remove selected</button>
                  <button id="clear-actions-btn" type="button" class="ss-btn">Clear actions</button>
                </div>
                <div class="ss-toolbar-row ss-toolbar-sub">
                  <select id="stage-tag-select" class="ss-select ss-grow" aria-label="Stage players by tag"></select>
                  <button id="stage-by-tag-btn" type="button" class="ss-btn">Add by tag</button>
                  <button id="stage-friends-btn" type="button" class="ss-btn">Add friends →</button>
                  <button id="stage-org-btn" type="button" class="ss-btn">Add org →</button>
                  <button id="open-org-import-btn" type="button" class="ss-btn ss-btn-accent" title="Import organization roster from RSI">Import Org…</button>
                </div>
                <div class="ss-pane-meta">
                  <span id="people-action-header" class="ss-status-line">Action list · 0 / 50</span>
                  <span class="ss-hint-line">Tags: shard members · Friend: your friends list</span>
                </div>
                <div id="people-action-scroll" class="ss-table-scroll ss-action-scroll" tabindex="0" role="region" aria-label="Staged action list">
                  <table class="ss-table" id="people-action-table">
                    <thead>
                      <tr>
                        <th class="col-player">PLAYER</th>
                        <th class="col-tags">TAGS</th>
                        <th class="col-rel">RELATIONSHIP</th>
                      </tr>
                    </thead>
                    <tbody id="people-action-tbody"></tbody>
                  </table>
                </div>
              </div>

              <div class="ss-card ss-controls-pane">
                <div class="ss-toolbar-row">
                  <select id="apply-tag-select" class="ss-select ss-grow" aria-label="Preset tag"></select>
                  <button id="add-preset-tag-btn" type="button" class="ss-btn">Add tag</button>
                </div>
                <label class="ss-field-label" for="tag-draft-input">Custom tags (optional, comma separated)</label>
                <div class="ss-toolbar-row">
                  <input id="tag-draft-input" class="ss-input ss-grow" type="text" maxlength="240" placeholder="Custom tags, separated by commas" autocomplete="off" />
                  <button id="apply-tags-btn" type="button" class="ss-btn ss-btn-accent">Apply tags</button>
                </div>
                <div class="ss-toolbar-row ss-toolbar-sub">
                  <label class="ss-checkbox-label">
                    <input id="join-alerts-checkbox" type="checkbox" />
                    <span>Join alerts</span>
                  </label>
                  <button id="clear-tags-btn" type="button" class="ss-btn">Clear tags</button>
                </div>
                <div class="ss-toolbar-row ss-social-row">
                  <button id="send-friends-btn" type="button" class="ss-btn ss-btn-accent ss-grow">Send friend requests…</button>
                  <button id="invite-party-btn" type="button" class="ss-btn ss-btn-accent ss-grow">Invite to party…</button>
                </div>
                <div class="ss-toolbar-row ss-queue-row">
                  <button id="view-queue-btn" type="button" class="ss-btn">View queue</button>
                  <button id="pause-queue-btn" type="button" class="ss-btn">Pause</button>
                  <button id="cancel-queue-btn" type="button" class="ss-btn">Cancel</button>
                </div>
                <div id="queue-status-text" class="ss-queue-summary">Party invitations: idle · 0.09–0.99s paced gap</div>
              </div>
            </div>
          </div>
        </section>

        <!-- Buyer Alerts View -->
        <section id="ss-view-market" class="ss-view" hidden>
          <div class="ss-card ss-market-card">
            <div class="ss-toolbar-row">
              <input id="market-search-input" class="ss-input ss-grow" type="text" placeholder="Search UEX materials or items" autocomplete="off" />
              <button id="market-find-btn" type="button" class="ss-btn">Find material</button>
              <button id="market-refresh-btn" type="button" class="ss-btn ss-btn-accent">Refresh buyers</button>
            </div>
            <p class="ss-hint-line">Select the exact item · watches check every 30 minutes · quality 0 means any</p>
            <div class="ss-toolbar-row">
              <select id="market-item-select" class="ss-select ss-grow" aria-label="UEX market item"></select>
            </div>
            <div class="ss-toolbar-row">
              <label class="ss-inline-field">Quality <input id="market-quality-input" class="ss-input ss-input-sm" type="number" min="0" max="1000" value="1000" /></label>
              <label class="ss-inline-field">Minimum UEC <input id="market-price-input" class="ss-input ss-input-md" type="text" placeholder="Any" /></label>
              <label class="ss-inline-field">/ unit <input id="market-unit-input" class="ss-input ss-input-sm" type="text" value="unit" /></label>
              <button id="market-watch-btn" type="button" class="ss-btn ss-btn-accent">Watch buyers</button>
            </div>
            <div class="ss-table-scroll ss-market-scroll">
              <table class="ss-table">
                <thead>
                  <tr>
                    <th>Material / item</th>
                    <th>Quality</th>
                    <th>Minimum</th>
                    <th>Matches</th>
                    <th>Last check</th>
                  </tr>
                </thead>
                <tbody id="market-watches-tbody"></tbody>
              </table>
            </div>
            <div class="ss-toolbar-row">
              <button id="market-refresh-now-btn" type="button" class="ss-btn">Refresh now</button>
              <button id="market-toggle-watch-btn" type="button" class="ss-btn">Pause / resume</button>
              <button id="market-remove-watch-btn" type="button" class="ss-btn">Remove watch</button>
              <button id="market-show-matches-btn" type="button" class="ss-btn">Show matches</button>
            </div>
            <h3 id="market-notices-heading" class="ss-subhead">Recent HUD notices — buyer matches and tagged-player appearances</h3>
            <div class="ss-table-scroll ss-notices-scroll">
              <table class="ss-table">
                <thead>
                  <tr>
                    <th>Notification</th>
                    <th>Observed</th>
                  </tr>
                </thead>
                <tbody id="market-notices-tbody"></tbody>
              </table>
            </div>
            <div class="ss-toolbar-row">
              <button id="market-open-ad-btn" type="button" class="ss-btn">Open selected UEX ad</button>
              <button id="market-dismiss-notices-btn" type="button" class="ss-btn">Dismiss notices</button>
            </div>
          </div>
        </section>

        <!-- Home Session Recap View -->
        <section id="ss-view-home" class="ss-view" hidden>
          <div class="ss-home-grid">
            <div class="ss-card">
              <div class="ss-toolbar-row ss-space-between">
                <h2 class="ss-section-heading">SESSION RECAP</h2>
                <div class="ss-segmented">
                  <button id="home-session-current" type="button" class="ss-btn is-active">This session</button>
                  <button id="home-session-prev" type="button" class="ss-btn">Previous session</button>
                </div>
              </div>
              <div class="ss-metrics-row" id="home-metrics-row"></div>
              <div class="ss-recap-columns">
                <div class="ss-subcard">
                  <h3>Blueprints received</h3>
                  <ul id="home-blueprints-list" class="ss-clean-list"></ul>
                </div>
                <div class="ss-subcard">
                  <h3>Reputation balance changes</h3>
                  <ul id="home-rep-list" class="ss-clean-list"></ul>
                </div>
              </div>
              <div id="home-patch-banner" class="ss-patch-banner"></div>
            </div>
          </div>
        </section>

        <!-- Settings & Modules Quick View -->
        <section id="ss-view-settings" class="ss-view" hidden>
          <div class="ss-card">
            <h2 class="ss-section-heading">DESKTOP &amp; MODULE CONTROLS</h2>
            <p class="ss-muted-text">Manage native HUDs, privacy settings, and optional feature modules. Your player records stay on this PC.</p>
            <div class="ss-settings-grid">
              <button type="button" class="ss-tile-btn" data-nav="settings">
                <strong>Startup &amp; HUD Settings</strong>
                <span>Configure RSI Launcher auto-start, HUD modes, and F23/F24 shortcuts</span>
              </button>
              <button type="button" class="ss-tile-btn" data-nav="privacy">
                <strong>Privacy &amp; Capture</strong>
                <span>Inspect game-only capture policy and local account access controls</span>
              </button>
              <button type="button" class="ss-tile-btn" data-nav="modules">
                <strong>Feature Modules…</strong>
                <span>Add or remove optional feature packages with signed verification</span>
              </button>
              <button type="button" class="ss-tile-btn" data-nav="strings_settings">
                <strong>SynthStrings Text Settings</strong>
                <span>Review game localization status — Game text unchanged means no action needed</span>
              </button>
            </div>
          </div>
        </section>

        <footer class="ss-footer">
          <div id="companion-footer-status" class="ss-footer-text">Ready</div>
        </footer>

        <!-- Confirmation & Queue Modal -->
        <div id="ss-modal-backdrop" class="ss-modal-backdrop" hidden role="dialog" aria-modal="true" aria-labelledby="ss-modal-title">
          <div class="ss-modal">
            <h2 id="ss-modal-title" class="ss-modal-title">Confirm recipients</h2>
            <p id="ss-modal-summary" class="ss-modal-summary"></p>
            <div class="ss-table-scroll ss-modal-scroll">
              <table class="ss-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Result / Status</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody id="ss-modal-tbody"></tbody>
              </table>
            </div>
            <label id="ss-modal-resend-wrap" class="ss-checkbox-label ss-modal-resend">
              <input id="ss-modal-resend-checkbox" type="checkbox" />
              <span>Repeat previously attempted requests this session</span>
            </label>
            <div class="ss-modal-actions">
              <button id="ss-modal-pause-btn" type="button" class="ss-btn" hidden>Pause</button>
              <button id="ss-modal-stop-btn" type="button" class="ss-btn" hidden>Cancel queue</button>
              <div class="ss-grow"></div>
              <button id="ss-modal-confirm-btn" type="button" class="ss-btn ss-btn-accent">Start queue</button>
              <button id="ss-modal-cancel-btn" type="button" class="ss-btn ss-btn-default">Cancel</button>
            </div>
          </div>
        </div>

        <!-- RSI Org Importer Modal -->
        <div id="ss-org-modal-backdrop" class="ss-modal-backdrop" hidden role="dialog" aria-modal="true" aria-labelledby="ss-org-modal-title">
          <div class="ss-modal ss-org-modal" style="max-width: 480px;">
            <h2 id="ss-org-modal-title" class="ss-modal-title">Import Organization Roster from RSI</h2>
            <p id="ss-org-modal-summary" class="ss-modal-summary">
              Query public members for an RSI organization by Org Symbol / SID (e.g. <code>TEST</code>).
              Members are automatically tagged and will trigger the in-game HUD shutter notification upon joining your shard.
            </p>
            <div class="ss-org-modal-fields" style="display:flex; flex-direction:column; gap:8px;">
              <label class="ss-field-label" for="org-import-symbol-input">Org Symbol / SID</label>
              <input id="org-import-symbol-input" class="ss-input" type="text" maxlength="20" placeholder="e.g. TEST, PIRATES, ANVIL" autocomplete="off" />
              
              <label class="ss-field-label" for="org-import-tag-select" style="margin-top: 8px;">Tag Members As</label>
              <select id="org-import-tag-select" class="ss-select">
                <option value="Enemy Org">Enemy Org (Crimson Hostile)</option>
                <option value="Org">Org (Allied / Member)</option>
                <option value="Friendly">Friendly</option>
              </select>

              <label class="ss-checkbox-label" style="margin-top: 8px;">
                <input id="org-import-alert-checkbox" type="checkbox" checked />
                <span>Alert on shard arrival (10-second flip-down shutter HUD)</span>
              </label>

              <div id="org-import-status-text" class="ss-status-line" style="margin-top: 8px; min-height: 20px;"></div>
            </div>
            <div class="ss-modal-actions" style="margin-top: 18px;">
              <button id="ss-org-import-submit-btn" type="button" class="ss-btn ss-btn-accent">Import Roster</button>
              <button id="ss-org-import-cancel-btn" type="button" class="ss-btn ss-btn-default">Cancel</button>
            </div>
          </div>
        </div>
      </div>
          </div>
        </main>
      </div>
    `;

    this.rosterScrollEl = this.root.querySelector('#people-roster-scroll')!;
    this.rosterTbodyEl = this.root.querySelector('#people-roster-tbody')!;
    this.actionScrollEl = this.root.querySelector('#people-action-scroll')!;
    this.actionTbodyEl = this.root.querySelector('#people-action-tbody')!;
    this.searchInputEl = this.root.querySelector('#people-search-input')!;
    this.sourceSelectEl = this.root.querySelector('#people-source-select')!;
    this.taggedOnlyEl = this.root.querySelector('#people-tagged-only')!;
    this.rosterStatusEl = this.root.querySelector('#people-roster-status')!;
    this.selectionSummaryEl = this.root.querySelector('#people-selection-summary')!;
    this.actionHeaderEl = this.root.querySelector('#people-action-header')!;
    this.stageTagSelectEl = this.root.querySelector('#stage-tag-select')!;
    this.applyTagSelectEl = this.root.querySelector('#apply-tag-select')!;
    this.tagDraftInputEl = this.root.querySelector('#tag-draft-input')!;
    this.joinAlertsCheckboxEl = this.root.querySelector('#join-alerts-checkbox')!;
    this.queueStatusEl = this.root.querySelector('#queue-status-text')!;
    this.footerStatusEl = this.root.querySelector('#companion-footer-status')!;

    this.stageSelectedBtn = this.root.querySelector('#stage-selected-btn')!;
    this.removeActionBtn = this.root.querySelector('#remove-action-btn')!;
    this.clearActionsBtn = this.root.querySelector('#clear-actions-btn')!;
    this.stageByTagBtn = this.root.querySelector('#stage-by-tag-btn')!;
    this.stageFriendsBtn = this.root.querySelector('#stage-friends-btn')!;
    this.stageOrgBtn = this.root.querySelector('#stage-org-btn')!;
    this.addPresetTagBtn = this.root.querySelector('#add-preset-tag-btn')!;
    this.applyTagsBtn = this.root.querySelector('#apply-tags-btn')!;
    this.clearTagsBtn = this.root.querySelector('#clear-tags-btn')!;
    this.sendFriendsBtn = this.root.querySelector('#send-friends-btn')!;
    this.invitePartyBtn = this.root.querySelector('#invite-party-btn')!;
    this.viewQueueBtn = this.root.querySelector('#view-queue-btn')!;
    this.pauseQueueBtn = this.root.querySelector('#pause-queue-btn')!;
    this.cancelQueueBtn = this.root.querySelector('#cancel-queue-btn')!;

    this.peopleSectionEl = this.root.querySelector('#ss-view-people')!;
    this.marketSectionEl = this.root.querySelector('#ss-view-market')!;
    this.homeSectionEl = this.root.querySelector('#ss-view-home')!;
    this.settingsSectionEl = this.root.querySelector('#ss-view-settings')!;

    this.modalBackdropEl = this.root.querySelector('#ss-modal-backdrop')!;
    this.modalTitleEl = this.root.querySelector('#ss-modal-title')!;
    this.modalSummaryEl = this.root.querySelector('#ss-modal-summary')!;
    this.modalTbodyEl = this.root.querySelector('#ss-modal-tbody')!;
    this.modalResendWrapEl = this.root.querySelector('#ss-modal-resend-wrap')!;
    this.modalResendCheckboxEl = this.root.querySelector('#ss-modal-resend-checkbox')!;
    this.modalConfirmBtn = this.root.querySelector('#ss-modal-confirm-btn')!;
    this.modalCancelBtn = this.root.querySelector('#ss-modal-cancel-btn')!;
    this.modalPauseBtn = this.root.querySelector('#ss-modal-pause-btn')!;
    this.modalStopQueueBtn = this.root.querySelector('#ss-modal-stop-btn')!;

    this.openOrgImportBtn = this.root.querySelector('#open-org-import-btn')!;
    this.orgModalBackdropEl = this.root.querySelector('#ss-org-modal-backdrop')!;
    this.orgImportSymbolInput = this.root.querySelector('#org-import-symbol-input')!;
    this.orgImportTagSelect = this.root.querySelector('#org-import-tag-select')!;
    this.orgImportAlertCheckbox = this.root.querySelector('#org-import-alert-checkbox')!;
    this.orgImportStatusEl = this.root.querySelector('#org-import-status-text')!;
    this.orgImportSubmitBtn = this.root.querySelector('#ss-org-import-submit-btn')!;
    this.orgImportCancelBtn = this.root.querySelector('#ss-org-import-cancel-btn')!;

    this.marketSearchInputEl = this.root.querySelector('#market-search-input')!;
    this.marketItemSelectEl = this.root.querySelector('#market-item-select')!;
    this.marketQualityInputEl = this.root.querySelector('#market-quality-input')!;
    this.marketPriceInputEl = this.root.querySelector('#market-price-input')!;
    this.marketUnitInputEl = this.root.querySelector('#market-unit-input')!;
    this.marketWatchesTbodyEl = this.root.querySelector('#market-watches-tbody')!;
    this.marketNoticesTbodyEl = this.root.querySelector('#market-notices-tbody')!;
    this.marketNoticesHeadingEl = this.root.querySelector('#market-notices-heading')!;
    this.marketShowMatchesBtn = this.root.querySelector('#market-show-matches-btn')!;

    this.bindEvents();

    const sidebarEl = this.root.querySelector<HTMLElement>('#ss-app-sidebar');
    const mainEl = this.root.querySelector<HTMLElement>('#ss-app-main .ss-shell');
    if (sidebarEl && mainEl) {
      this.desktopViews = new DesktopViewsManager(
        this.bridge,
        sidebarEl,
        mainEl,
        (page) => this.setMode(page as PeopleSnapshot['mode']),
      );
    }
  }

  private bindEvents(): void {
    // Mode switcher tabs
    this.root.querySelectorAll<HTMLButtonElement>('.ss-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        const nextMode = (btn.dataset.mode as typeof this.activeMode) ?? 'people';
        this.setMode(nextMode);
      });
    });

    // Settings tiles navigation
    this.root.querySelectorAll<HTMLButtonElement>('[data-nav]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.nav;
        if (target) {
          void this.bridge.sendCommand({ action: 'navigate', target });
        }
      });
    });

    // Search & filter controls
    this.searchInputEl.addEventListener('input', () => {
      this.searchQuery = this.searchInputEl.value;
      if (this.searchQuery.trim() === '' && this.sourceIndex === 1) {
        this.sourceIndex = 0;
        this.sourceSelectEl.value = '0';
      }
      this.renderPeople();
    });

    this.root.querySelector('#people-clear-btn')!.addEventListener('click', () => {
      this.searchQuery = '';
      this.searchInputEl.value = '';
      this.sourceIndex = 0;
      this.sourceSelectEl.value = '0';
      this.renderPeople();
    });

    this.root.querySelector('#people-find-btn')!.addEventListener('click', () => {
      this.sourceIndex = 1;
      this.sourceSelectEl.value = '1';
      void this.bridge.sendCommand({
        action: 'search',
        query: this.searchInputEl.value.trim(),
      });
      this.renderPeople();
    });

    this.root.querySelector('#people-refresh-btn')!.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'refresh_people' });
    });

    this.sourceSelectEl.addEventListener('change', () => {
      this.sourceIndex = Number(this.sourceSelectEl.value) || 0;
      this.renderPeople();
    });

    this.taggedOnlyEl.addEventListener('change', () => {
      this.taggedOnly = this.taggedOnlyEl.checked;
      this.renderPeople();
    });

    // Ordinary click toggles in Roster table
    this.rosterScrollEl.addEventListener('scroll', () => {
      this.virtualScrollTop = Math.round(this.rosterScrollEl.scrollTop);
      this.virtualScrollLeft = Math.round(this.rosterScrollEl.scrollLeft);
    });
    this.rosterTbodyEl.addEventListener('click', (ev) => {
      const tr = (ev.target as HTMLElement).closest<HTMLTableRowElement>('tr[data-player-id]');
      if (!tr) return;
      const id = tr.dataset.playerId!;
      this.toggleSelection(id, ev.shiftKey, false);
    });

    // Ordinary click toggles in Action table
    this.actionTbodyEl.addEventListener('click', (ev) => {
      const tr = (ev.target as HTMLElement).closest<HTMLTableRowElement>('tr[data-player-id]');
      if (!tr) return;
      const id = tr.dataset.playerId!;
      this.toggleSelection(id, ev.shiftKey, true);
    });

    // Action list staging buttons
    this.stageSelectedBtn.addEventListener('click', () => {
      const eligible = this.getStageTargets().map((p) => p.id);
      if (eligible.length > 0) {
        void this.bridge.stagePlayers(eligible);
      }
    });

    this.removeActionBtn.addEventListener('click', () => {
      const ids = Array.from(this.actionSelectedIds);
      if (ids.length > 0) {
        void this.bridge.sendCommand({ action: 'unstage_people', player_ids: ids });
      }
    });

    this.clearActionsBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'clear_actions' });
    });

    this.stageByTagBtn.addEventListener('click', () => {
      const tag = this.stageTagSelectEl.value;
      if (tag) {
        void this.bridge.sendCommand({
          action: 'stage_tag',
          label: tag,
          scope: 'shard',
          include_org_affiliate: false,
        });
      }
    });

    this.stageFriendsBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({
        action: 'stage_tag',
        label: 'Friend',
        scope: 'shard',
        include_org_affiliate: false,
      });
    });

    this.stageOrgBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({
        action: 'stage_tag',
        label: 'Org',
        scope: 'shard',
        include_org_affiliate: true,
      });
    });

    // Tagging controls
    this.addPresetTagBtn.addEventListener('click', () => {
      const targets = this.getActionTargets();
      const tag = this.applyTagSelectEl.value;
      if (targets.length > 0 && tag) {
        void this.bridge.sendCommand({
          action: 'tag_many',
          player_ids: targets.map((p) => p.id),
          label: tag,
        });
      }
    });

    this.applyTagsBtn.addEventListener('click', () => {
      const targets = this.getActionTargets();
      if (targets.length === 0) return;
      const draft = this.tagDraftInputEl.value.trim();
      if (targets.length === 1) {
        void this.bridge.sendCommand({
          action: 'tag',
          player_id: targets[0].id,
          label: draft,
          alert: this.joinAlertsCheckboxEl.checked,
        });
      } else {
        void this.bridge.sendCommand({
          action: 'tag_many',
          player_ids: targets.map((p) => p.id),
          label: draft,
        });
      }
    });

    this.clearTagsBtn.addEventListener('click', () => {
      const targets = this.getActionTargets();
      if (targets.length === 0) return;
      if (targets.length === 1) {
        void this.bridge.sendCommand({
          action: 'tag',
          player_id: targets[0].id,
          label: '',
          clear_tags: true,
          alert: this.joinAlertsCheckboxEl.checked,
        });
      } else {
        void this.bridge.sendCommand({
          action: 'tag_many',
          player_ids: targets.map((p) => p.id),
          label: '',
          clear_tags: true,
        });
      }
    });

    // Social actions -> open explicit confirmation modal
    this.sendFriendsBtn.addEventListener('click', () => {
      const targets = this.getActionTargets().filter((p) => !p.is_friend);
      if (targets.length === 0) {
        this.footerStatusEl.textContent = 'Add eligible players to the Action list first.';
        return;
      }
      this.openConfirmationModal('confirm_friend', targets);
    });

    this.invitePartyBtn.addEventListener('click', () => {
      const targets = this.getActionTargets().filter((p) => !p.in_party);
      if (targets.length === 0) {
        this.footerStatusEl.textContent = 'Add eligible players to the Action list first.';
        return;
      }
      this.openConfirmationModal('confirm_party', targets);
    });

    this.viewQueueBtn.addEventListener('click', () => {
      this.openQueueReportModal();
    });

    this.pauseQueueBtn.addEventListener('click', () => {
      const q = this.snapshot?.invite_queue;
      if (!q?.id) return;
      void this.bridge.sendCommand({
        action: q.paused ? 'resume_invites' : 'pause_invites',
        queue_id: q.id,
      });
    });

    this.cancelQueueBtn.addEventListener('click', () => {
      const q = this.snapshot?.invite_queue;
      if (!q?.id) return;
      void this.bridge.sendCommand({
        action: 'cancel_invites',
        queue_id: q.id,
      });
    });

    // Modal controls
    this.modalCancelBtn.addEventListener('click', () => {
      this.closeModal();
    });

    this.modalConfirmBtn.addEventListener('click', () => {
      if (this.modalMode === 'queue_report') {
        this.closeModal();
        return;
      }
      const ids = this.modalRecipients.map((p) => p.id).slice(0, ACTION_LIMIT);
      const resend = this.modalResendCheckboxEl.checked;
      const action = this.modalMode === 'confirm_friend' ? 'friend_many' : 'party_many';
      this.closeModal();
      if (ids.length > 0) {
        void this.bridge.sendCommand({
          action,
          player_ids: ids,
          from_actions: true,
          confirmed: true,
          resend,
        });
      }
    });

    this.modalPauseBtn.addEventListener('click', () => {
      const q = this.snapshot?.invite_queue;
      if (!q?.id) return;
      void this.bridge.sendCommand({
        action: q.paused ? 'resume_invites' : 'pause_invites',
        queue_id: q.id,
      });
    });

    this.modalStopQueueBtn.addEventListener('click', () => {
      const q = this.snapshot?.invite_queue;
      if (!q?.id) return;
      void this.bridge.sendCommand({
        action: 'cancel_invites',
        queue_id: q.id,
      });
    });

    // Org Importer modal events
    this.openOrgImportBtn.addEventListener('click', () => {
      this.openOrgImportModal();
    });
    this.orgImportCancelBtn.addEventListener('click', () => {
      this.closeOrgImportModal();
    });
    this.orgModalBackdropEl.addEventListener('click', (e) => {
      if (e.target === this.orgModalBackdropEl) {
        this.closeOrgImportModal();
      }
    });
    this.orgImportSubmitBtn.addEventListener('click', () => {
      const symbol = this.orgImportSymbolInput.value.trim().toUpperCase();
      if (!symbol) {
        this.orgImportStatusEl.textContent = 'Please enter an Org Symbol / SID (e.g. TEST).';
        this.orgImportStatusEl.style.color = '#ff6666';
        return;
      }
      const tagLabel = this.orgImportTagSelect.value;
      const alert = this.orgImportAlertCheckbox.checked;
      this.orgImportStatusEl.textContent = 'Contacting RSI API for ' + symbol + ' members…';
      this.orgImportStatusEl.style.color = '#62ccff';
      this.orgImportSubmitBtn.disabled = true;

      void this.bridge.sendCommand({
        action: 'import_org',
        symbol,
        tag_label: tagLabel,
        alert,
        confirmed: true,
      });

      setTimeout(() => {
        this.closeOrgImportModal();
        this.footerStatusEl.textContent = 'Importing ' + symbol + ' from RSI…';
      }, 500);
    });

    // Buyer alerts events
    this.marketSearchInputEl.addEventListener('input', () => {
      this.marketSearch = this.marketSearchInputEl.value;
      this.renderMarketCatalog();
    });
    this.root.querySelector('#market-find-btn')!.addEventListener('click', () => {
      this.marketSearch = this.marketSearchInputEl.value;
      this.renderMarketCatalog();
    });
    this.root.querySelector('#market-refresh-btn')!.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'refresh_market' });
    });
    this.root.querySelector('#market-refresh-now-btn')!.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'refresh_market' });
    });
    this.root.querySelector('#market-watch-btn')!.addEventListener('click', () => {
      const itemId = Number(this.marketItemSelectEl.value);
      const quality = Number(this.marketQualityInputEl.value);
      const priceStr = this.marketPriceInputEl.value.trim();
      const price = priceStr ? Number(priceStr) : 0;
      if (!itemId || Number.isNaN(quality) || quality < 0 || quality > 9999 || Number.isNaN(price)) {
        this.footerStatusEl.textContent =
          'Choose an item and enter a whole-number quality and valid minimum price.';
        return;
      }
      void this.bridge.sendCommand({
        action: 'add_watch',
        item_id: itemId,
        quality: Math.trunc(quality),
        price,
        unit: this.marketUnitInputEl.value.trim() || 'unit',
      });
    });
    this.root.querySelector('#market-toggle-watch-btn')!.addEventListener('click', () => {
      if (this.selectedWatchId) {
        void this.bridge.sendCommand({ action: 'toggle_watch', watch_id: this.selectedWatchId });
      }
    });
    this.root.querySelector('#market-remove-watch-btn')!.addEventListener('click', () => {
      if (this.selectedWatchId) {
        void this.bridge.sendCommand({ action: 'remove_watch', watch_id: this.selectedWatchId });
      }
    });
    this.marketShowMatchesBtn.addEventListener('click', () => {
      this.showMatches = !this.showMatches;
      this.renderMarket();
    });
    this.root.querySelector('#market-dismiss-notices-btn')!.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'dismiss_notices' });
    });

    // Home session toggle
    this.root.querySelector('#home-session-current')!.addEventListener('click', () => {
      this.homeShowPrevious = false;
      this.renderHome();
    });
    this.root.querySelector('#home-session-prev')!.addEventListener('click', () => {
      this.homeShowPrevious = true;
      this.renderHome();
    });
  }

  public setMode(mode: PeopleSnapshot['mode']): void {
    if (!mode) mode = 'people';
    this.activeMode = mode;
    this.peopleSectionEl.hidden = mode !== 'people';
    this.marketSectionEl.hidden = mode !== 'buyer_alerts';
    this.homeSectionEl.hidden = mode !== 'home';
    this.settingsSectionEl.hidden = mode !== 'settings';

    this.root.querySelectorAll<HTMLButtonElement>('.ss-tab').forEach((btn) => {
      const active = btn.dataset.mode === mode;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    const modeTabsEl = this.root.querySelector<HTMLElement>('.ss-mode-tabs');
    if (modeTabsEl) {
      modeTabsEl.hidden = mode !== 'people' && mode !== 'buyer_alerts';
    }

    if (this.desktopViews) {
      this.desktopViews.setActivePage(mode === 'buyer_alerts' ? 'people' : mode);
    }

    const titleEl = this.root.querySelector('#ss-page-title')!;
    const subEl = this.root.querySelector('#ss-page-subtitle')!;
    const titles: Record<string, [string, string]> = {
      home: ['Home', "Find your next upgrade. See what you've accomplished."],
      directory: ['Item & Ship Finder', 'Search Star Citizen commodities, ships, weapons, components, and armor.'],
      people: ['People', 'A familiar face in a very large universe.'],
      buyer_alerts: ['Buyer Alerts', 'Watch UEX buy orders for your best mining and crafting hauls.'],
      mission_log: ['Mission & Wallet Log', 'Track mission objectives, payouts, reputations, and balance changes.'],
      servers: ['Server History', 'Track shard visits, cooldowns, regional latencies, and player sessions.'],
      blueprints: ['Blueprint Library', 'Crafting blueprints, material costs, and collection progress.'],
      planner: ['Mining Planner', 'Ore compositions, optimal locations, rock density, and refinery yields.'],
      diary: ['Mining Diary', 'Log your mining runs, rock signatures, locations, and ore hauls.'],
      refinery: ['Refinery', 'Track active jobs, yields, completion timers, and order collections.'],
      executive_hangar: ['Executive Hangar', 'Automated ship recall, docking bay status, and departure sequencing.'],
      hud_piracy: ['Piracy', 'Interdiction traps, quantum snare timers, and ship cargo surveillance.'],
      daylight: ['Day/Night Forecast', 'Plan surface approaches with real-time solar illumination and terminator lines.'],
      acceptance: ['Automatic Acceptance', 'Hands-free party invitations, trade requests, and mission sharing.'],
      settings: ['Settings & Modules', 'Customize HUD behavior, shortcuts, privacy, and installed modules.'],
    };
    const pair = titles[mode] ?? ['SynthScan', 'YOUR VERSE, CONNECTED'];
    titleEl.textContent = pair[0];
    subEl.textContent = pair[1];
  }

  private onSnapshot(snap: PeopleSnapshot): void {
    const modeChanged = snap.mode && snap.mode !== this.activeMode;
    this.snapshot = snap;
    if (this.desktopViews) {
      this.desktopViews.updateState(snap);
    }
    if (modeChanged && snap.mode) {
      this.setMode(snap.mode);
    }
    this.renderPeople();
    this.renderMarketCatalog();
    this.renderMarket();
    this.renderHome();
    if (this.modalOpen && this.modalMode === 'queue_report') {
      this.renderQueueReportRows();
    }
  }

  private getCandidates(snap: PeopleSnapshot): Player[] {
    if (this.sourceIndex === 2) {
      const tagsMap = snap.tags ?? {};
      return Object.entries(tagsMap).map(([id, entry]) =>
        normalizePlayer({
          id,
          handle: entry.handle ?? id,
          tag: entry.label ?? '',
          alert: entry.alert,
          is_org: entry.is_org,
        }),
      );
    }
    if (this.sourceIndex === 3) {
      return snap.friend_people ?? [];
    }
    if (this.sourceIndex === 1) {
      const q = this.searchQuery.trim().toLowerCase();
      const snapQuery = (snap.search_query ?? '').trim().toLowerCase();
      if (q.length > 0 && q === snapQuery) {
        return snap.search ?? [];
      }
      return [];
    }
    return snap.players;
  }

  private renderPeople(): void {
    const snap = this.snapshot;
    if (!snap) return;

    this.searchInputEl.placeholder =
      this.sourceIndex === 1
        ? 'Enter an RSI handle, then click Find player'
        : 'Filter this list by handle or tag';

    const normalizedQuery = this.searchQuery.trim().toLowerCase();
    const viewSignature = `${snap.session}|${this.sourceIndex}|${normalizedQuery}|${this.taggedOnly ? '1' : '0'}`;
    const resetView = viewSignature !== this.previousViewSignature;
    this.previousViewSignature = viewSignature;

    const candidates = this.getCandidates(snap);
    const nextFiltered: Player[] = [];
    for (const p of candidates) {
      const hay = `${p.handle} ${p.tag ?? p.tags.join(' ')}`.toLowerCase();
      if (normalizedQuery && !hay.includes(normalizedQuery)) continue;
      if (this.taggedOnly && (!p.tags || p.tags.length === 0) && !p.tag) continue;
      nextFiltered.push(p);
    }

    // Capture scroll anchor BEFORE mutating the roster DOM
    const scrollTopBefore = Math.round(this.virtualScrollTop);
    const scrollLeftBefore = Math.round(this.virtualScrollLeft);
    const topIndexBefore = Math.max(
      0,
      Math.min(
        this.filteredPeople.length - 1,
        Math.floor(scrollTopBefore / ROW_HEIGHT_PX),
      ),
    );
    const offsetWithinRow =
      this.filteredPeople.length > 0
        ? scrollTopBefore - topIndexBefore * ROW_HEIGHT_PX
        : 0;

    let survivingAnchorId = '';
    if (!resetView && this.filteredPeople.length > 0) {
      const nextIdSet = new Set(nextFiltered.map((p) => p.id));
      for (let i = topIndexBefore; i < this.filteredPeople.length; i++) {
        if (nextIdSet.has(this.filteredPeople[i].id)) {
          survivingAnchorId = this.filteredPeople[i].id;
          break;
        }
      }
      if (!survivingAnchorId) {
        for (let i = topIndexBefore - 1; i >= 0; i--) {
          if (nextIdSet.has(this.filteredPeople[i].id)) {
            survivingAnchorId = this.filteredPeople[i].id;
            break;
          }
        }
      }
    }

    if (resetView) {
      // Reconcile removed selections when intentionally resetting view
      const nextIdSet = new Set(nextFiltered.map((p) => p.id));
      for (const id of Array.from(this.selectedIds)) {
        if (!nextIdSet.has(id)) {
          this.selectedIds.delete(id);
        }
      }
    } else {
      // Explicitly reconcile selections if a player completely left all known lists
      const allKnownIds = new Set<string>();
      for (const p of nextFiltered) allKnownIds.add(p.id);
      for (const p of snap.players) allKnownIds.add(p.id);
      for (const p of snap.friend_people ?? []) allKnownIds.add(p.id);
      for (const id of Array.from(this.selectedIds)) {
        if (!allKnownIds.has(id)) {
          this.selectedIds.delete(id);
        }
      }
    }

    this.filteredPeople = nextFiltered;
    this.reconcileTableRows(
      this.rosterTbodyEl,
      this.rosterRowMap,
      this.rosterRowSignature,
      this.filteredPeople,
      this.selectedIds,
    );

    // Restore scroll anchor
    if (resetView) {
      this.virtualScrollTop = 0;
      this.rosterScrollEl.scrollTop = 0;
    } else if (survivingAnchorId) {
      const newAnchorIndex = this.filteredPeople.findIndex((p) => p.id === survivingAnchorId);
      if (newAnchorIndex >= 0) {
        this.virtualScrollTop = Math.max(
          0,
          newAnchorIndex * ROW_HEIGHT_PX + offsetWithinRow,
        );
        this.rosterScrollEl.scrollTop = this.virtualScrollTop;
      }
      this.virtualScrollLeft = scrollLeftBefore;
      this.rosterScrollEl.scrollLeft = scrollLeftBefore;
    }

    // Reconcile independent Action list (capped at ACTION_LIMIT = 50)
    const rawActions = (snap.action_people ?? []).slice(0, ACTION_LIMIT);
    const nextActionIdSet = new Set(rawActions.map((p) => p.id));
    for (const id of Array.from(this.actionSelectedIds)) {
      if (!nextActionIdSet.has(id)) {
        this.actionSelectedIds.delete(id);
      }
    }
    this.actionPeople = rawActions;
    this.reconcileTableRows(
      this.actionTbodyEl,
      this.actionRowMap,
      this.actionRowSignature,
      this.actionPeople,
      this.actionSelectedIds,
      false,
    );

    this.updateTagSelectOptions(snap.tag_options ?? ['Org', 'Friendly', 'Aggressive', 'Trader', 'Friend']);
    this.updateStatusAndControls();
  }

  private computeRowSignature(p: Player, isSelected: boolean): string {
    const color = personColor(p).css;
    const reqFriend = p.requests?.friend
      ? `${p.requests.friend.outcome}:${p.requests.friend.detail ?? ''}`
      : '';
    const reqParty = p.requests?.party
      ? `${p.requests.party.outcome}:${p.requests.party.detail ?? ''}`
      : '';
    return `${p.handle}|${p.tag ?? p.tags.join(',')}|${p.relationship ?? ''}|${color}|${isSelected ? '1' : '0'}|${p.alert ? '1' : '0'}|${reqFriend}|${reqParty}`;
  }

  private reconcileTableRows(
    tbody: HTMLTableSectionElement,
    rowMap: Map<string, HTMLTableRowElement>,
    sigMap: Map<string, string>,
    rows: Player[],
    selectedSet: Set<string>,
    trackMetrics = true,
  ): void {
    if (trackMetrics) {
      this.lastUpdatedRowIds = [];
    }
    const nextIds = new Set(rows.map((p) => p.id));

    // Remove rows no longer present
    for (const [id, tr] of Array.from(rowMap.entries())) {
      if (!nextIds.has(id)) {
        tr.remove();
        rowMap.delete(id);
        sigMap.delete(id);
        if (trackMetrics) {
          this.domRowRemovedCount += 1;
        }
      }
    }

    // Update or create rows in order without recreating unchanged DOM nodes
    let cursor: ChildNode | null = tbody.firstChild;
    for (let i = 0; i < rows.length; i++) {
      const p = rows[i];
      const isSelected = selectedSet.has(p.id);
      const nextSig = this.computeRowSignature(p, isSelected);
      let tr = rowMap.get(p.id);

      if (!tr) {
        tr = tbody.ownerDocument.createElement('tr');
        tr.className = 'ss-person-row';
        tr.dataset.playerId = p.id;
        this.populateRowElement(tr, p, isSelected);
        rowMap.set(p.id, tr);
        sigMap.set(p.id, nextSig);
        if (trackMetrics) {
          this.domRowCreatedCount += 1;
          this.lastUpdatedRowIds.push(p.id);
        }
      } else if (sigMap.get(p.id) !== nextSig) {
        this.populateRowElement(tr, p, isSelected);
        sigMap.set(p.id, nextSig);
        if (trackMetrics) {
          this.domRowUpdatedCount += 1;
          this.lastUpdatedRowIds.push(p.id);
        }
      }

      if (tr !== cursor) {
        tbody.insertBefore(tr, cursor);
      } else {
        cursor = cursor.nextSibling;
      }
    }
  }

  private populateRowElement(tr: HTMLTableRowElement, p: Player, isSelected: boolean): void {
    const relColor = personColor(p);
    tr.classList.toggle('is-selected', isSelected);
    tr.setAttribute('aria-selected', isSelected ? 'true' : 'false');
    tr.style.height = `${ROW_HEIGHT_PX}px`;

    const tags = p.tags && p.tags.length > 0 ? p.tags : splitTags(p.tag);
    const chipsHtml = tags
      .map((t) => {
        const c = tagColor(t);
        const bgR = Math.trunc((14 * 4 + c.r) / 5);
        const bgG = Math.trunc((18 * 4 + c.g) / 5);
        const bgB = Math.trunc((25 * 4 + c.b) / 5);
        return `<span class="ss-tag-chip" data-tag="${this.escapeHtml(t)}" style="color:${c.css};background:rgb(${bgR},${bgG},${bgB});border-color:rgba(${c.r},${c.g},${c.b},0.49)">${this.escapeHtml(t)}</span>`;
      })
      .join('');

    const receipts: string[] = [];
    if (p.requests) {
      for (const [kind, entry] of Object.entries(p.requests)) {
        if (!entry) continue;
        const label = kind === 'friend' ? 'Friend' : 'Party';
        const outcome = entry.outcome ?? '';
        const detail = entry.detail ?? '';
        let text = '';
        let cls = 'ss-receipt-muted';
        if (outcome === 'Sent') {
          text = `✓ ${label} sent`;
          cls = 'ss-receipt-ok';
        } else if (detail === 'Already a friend' || detail === 'Already in party') {
          text = `${label}: already ${kind === 'friend' ? 'friends' : 'in party'}`;
        } else if (outcome === 'Queued' || outcome === 'Sending') {
          text = `… ${label} ${outcome}`;
        } else {
          text = `⚠ ${label}: ${detail || outcome}`;
          cls = 'ss-receipt-warn';
        }
        receipts.push(`<span class="ss-receipt ${cls}">${this.escapeHtml(text)}</span>`);
      }
    }

    const relLabel =
      p.relationship ??
      (p.is_self
        ? 'You'
        : p.in_party && p.is_friend
          ? 'Party + Friend'
          : p.in_party
            ? 'Party'
            : p.is_friend
              ? 'Friend'
              : '—');

    tr.innerHTML = `
      <td class="col-player">
        <div class="ss-player-cell">
          <span class="ss-row-check ${isSelected ? 'is-checked' : ''}" aria-hidden="true">${isSelected ? '✓' : ''}</span>
          <span class="ss-person-badge" style="color:${relColor.css}" aria-hidden="true">●</span>
          <div class="ss-player-stack">
            <span class="ss-player-handle">${this.escapeHtml(p.handle)}</span>
            ${receipts.length > 0 ? `<div class="ss-receipts-row">${receipts.join('')}</div>` : ''}
          </div>
        </div>
      </td>
      <td class="col-tags"><div class="ss-tags-run">${chipsHtml}</div></td>
      <td class="col-rel" style="color:${relColor.css}">${this.escapeHtml(relLabel)}</td>
    `;
  }

  private toggleSelection(playerId: string, shiftKey: boolean, isActionTable: boolean): void {
    const rows = isActionTable ? this.actionPeople : this.filteredPeople;
    const set = isActionTable ? this.actionSelectedIds : this.selectedIds;
    const anchor = isActionTable ? this.actionSelectionAnchorId : this.selectionAnchorId;

    if (shiftKey && anchor) {
      const aIdx = rows.findIndex((p) => p.id === anchor);
      const bIdx = rows.findIndex((p) => p.id === playerId);
      if (aIdx >= 0 && bIdx >= 0) {
        const start = Math.min(aIdx, bIdx);
        const end = Math.max(aIdx, bIdx);
        for (let i = start; i <= end; i++) {
          set.add(rows[i].id);
        }
      } else if (set.has(playerId)) {
        set.delete(playerId);
      } else {
        set.add(playerId);
      }
    } else {
      if (set.has(playerId)) {
        set.delete(playerId);
      } else {
        set.add(playerId);
      }
      if (isActionTable) {
        this.actionSelectionAnchorId = playerId;
      } else {
        this.selectionAnchorId = playerId;
      }
    }

    if (isActionTable) {
      this.reconcileTableRows(
        this.actionTbodyEl,
        this.actionRowMap,
        this.actionRowSignature,
        this.actionPeople,
        this.actionSelectedIds,
        false,
      );
    } else {
      this.reconcileTableRows(
        this.rosterTbodyEl,
        this.rosterRowMap,
        this.rosterRowSignature,
        this.filteredPeople,
        this.selectedIds,
      );
    }
    this.updateStatusAndControls();
  }

  private getChosenRosterPlayers(): Player[] {
    return this.filteredPeople.filter((p) => this.selectedIds.has(p.id) && !p.is_self);
  }

  private getStageTargets(): Player[] {
    return this.getChosenRosterPlayers();
  }

  private getActionTargets(): Player[] {
    return this.actionPeople.filter((p) => !p.is_self);
  }

  private updateTagSelectOptions(options: string[]): void {
    const currentStage = this.stageTagSelectEl.value;
    const currentApply = this.applyTagSelectEl.value;

    const stageHtml = options
      .map((opt) => `<option value="${this.escapeHtml(opt)}">${this.escapeHtml(opt)}</option>`)
      .join('');
    if (this.stageTagSelectEl.innerHTML !== stageHtml) {
      this.stageTagSelectEl.innerHTML = stageHtml;
      if (options.includes(currentStage)) {
        this.stageTagSelectEl.value = currentStage;
      }
    }

    const applyOptions = options.filter((opt) => opt !== 'Friend');
    const applyHtml = applyOptions
      .map((opt) => `<option value="${this.escapeHtml(opt)}">${this.escapeHtml(opt)}</option>`)
      .join('');
    if (this.applyTagSelectEl.innerHTML !== applyHtml) {
      this.applyTagSelectEl.innerHTML = applyHtml;
      if (applyOptions.includes(currentApply)) {
        this.applyTagSelectEl.value = currentApply;
      }
    }
  }

  private updateStatusAndControls(): void {
    const snap = this.snapshot;
    if (!snap) return;

    const actionTargets = this.getActionTargets();
    const editorSig = actionTargets.map((p) => p.id).join(',');
    const doc = this.root.ownerDocument;
    const draftFocused = doc.activeElement === this.tagDraftInputEl;

    // Preserve unsaved tag draft unless the target set changed and input is not focused
    if (editorSig !== this.actionEditorSignature && !draftFocused) {
      this.actionEditorSignature = editorSig;
      if (actionTargets.length === 1) {
        const only = actionTargets[0];
        this.tagDraftInputEl.value = only.manual_tag ?? only.tag ?? only.tags.join(', ');
        this.joinAlertsCheckboxEl.checked = Boolean(only.alert);
      } else {
        this.tagDraftInputEl.value = '';
        this.joinAlertsCheckboxEl.checked = false;
      }
    }

    const hasSession = Boolean(snap.session && snap.session.length > 0);
    const socialBusy = Boolean(snap.social_busy);
    const limit = Math.min(ACTION_LIMIT, snap.action_limit ?? ACTION_LIMIT);
    const room = this.actionPeople.length < limit;
    const stageTargets = this.getStageTargets();

    this.stageSelectedBtn.disabled = !hasSession || socialBusy || !room || stageTargets.length === 0;
    this.removeActionBtn.disabled = !hasSession || socialBusy || this.actionSelectedIds.size === 0;
    this.clearActionsBtn.disabled = !hasSession || socialBusy || this.actionPeople.length === 0;
    this.stageByTagBtn.disabled = !hasSession || socialBusy || !room;
    this.stageOrgBtn.disabled = !hasSession || socialBusy || !room;
    this.stageFriendsBtn.disabled = !hasSession || socialBusy || !room || !snap.friends_known;

    const canEditActions = hasSession && !socialBusy && actionTargets.length > 0;
    this.applyTagsBtn.disabled = !canEditActions;
    this.clearTagsBtn.disabled = !canEditActions;
    this.addPresetTagBtn.disabled = !canEditActions;
    this.joinAlertsCheckboxEl.disabled = !canEditActions || actionTargets.length !== 1;
    this.sendFriendsBtn.disabled = !canEditActions;
    this.invitePartyBtn.disabled = !canEditActions;

    this.actionHeaderEl.textContent = `Action list · ${this.actionPeople.length} / ${limit}${socialBusy ? ' · queue running' : ''}`;
    this.selectionSummaryEl.textContent = `${this.selectedIds.size} selected · ${stageTargets.length} eligible`;

    // Roster status text
    let rosterStatus = !hasSession
      ? 'Waiting for current shard'
      : `${snap.players.length} reported shard members`;
    if (this.sourceIndex === 1) {
      const q = this.searchQuery.trim();
      rosterStatus = q
        ? snap.search_busy
          ? 'Searching handles…'
          : `${this.filteredPeople.length} result(s) for “${snap.search_query ?? q}”`
        : 'Enter a handle, then click Find player.';
    } else if (this.sourceIndex === 3) {
      rosterStatus = snap.friends_known
        ? `${(snap.friend_people ?? []).length} friends`
        : 'Friends list is loading or unavailable · Refresh shard to retry';
    }
    if (snap.roster_loading && this.sourceIndex === 0) {
      rosterStatus += ' · refreshing';
    }
    if (snap.roster_error && this.sourceIndex !== 1) {
      rosterStatus += ` · ${snap.roster_error}`;
    }
    this.rosterStatusEl.textContent = rosterStatus;

    // Queue controls & summary
    const q = snap.invite_queue;
    const queueActive = Boolean(q && q.active && !q.cancelling);
    this.viewQueueBtn.disabled = !(snap.batch_results && snap.batch_results.length > 0) && !q?.id;
    this.pauseQueueBtn.disabled = !queueActive;
    this.cancelQueueBtn.disabled = !queueActive;
    this.pauseQueueBtn.textContent = q?.paused ? 'Resume' : 'Pause';
    this.queueStatusEl.textContent = this.formatQueueSummary(q);

    // Footer status
    let footer = snap.status ?? 'Ready';
    footer += ' · Tagged-player alerts report list appearances; the first snapshot stays quiet.';
    if (snap.friends_known === false || snap.party_known === false) {
      footer += ' · Friend / party status is checking or unavailable; unconfirmed rows stay neutral.';
    }
    this.footerStatusEl.textContent = footer;
  }

  private formatQueueSummary(q?: InviteQueueState): string {
    if (!q || !q.id) {
      return 'Party invitations: idle · 0.09–0.99s paced gap';
    }
    const prefix = q.operation === 'friend' ? 'Friends: ' : 'Party: ';
    let summary = `${prefix}${q.state} · ${q.sent} sent · ${q.skipped} skipped · ${q.remaining} remaining`;
    if (q.active && !q.paused && typeof q.next_in_seconds === 'number' && q.next_in_seconds > 0) {
      summary += ` · next in ${Math.trunc(q.next_in_seconds)}s`;
    }
    if (q.current_handle) {
      summary += ` · ${q.current_handle}`;
    }
    return summary;
  }

  public openConfirmationModal(
    mode: 'confirm_friend' | 'confirm_party',
    recipients: Player[],
  ): void {
    this.modalOpen = true;
    this.modalMode = mode;
    this.modalRecipients = recipients.slice(0, ACTION_LIMIT);
    this.modalResend = false;
    this.modalResendCheckboxEl.checked = false;
    this.modalResendWrapEl.hidden = false;
    this.modalConfirmBtn.hidden = false;
    this.modalPauseBtn.hidden = true;
    this.modalStopQueueBtn.hidden = true;
    this.modalCancelBtn.textContent = 'Cancel';

    const isFriend = mode === 'confirm_friend';
    this.modalTitleEl.textContent = isFriend
      ? 'Confirm friend requests'
      : 'Confirm party invitations';
    this.modalSummaryEl.textContent = `${isFriend ? 'Send friend requests to' : 'Invite'} ${this.modalRecipients.length} player(s)? Random 0.09–0.99s gap; current-shard membership is rechecked.`;

    this.modalTbodyEl.innerHTML = this.modalRecipients
      .map((p) => {
        const previous = isFriend ? p.friend_requested_before : p.invited_before;
        const outcome = previous ? 'Previous attempt' : isFriend ? 'Add friend' : 'Invite';
        const detail = previous
          ? 'Skipped unless repeat requests are explicitly enabled below; the previous attempt may be unconfirmed.'
          : (p.relationship ?? 'Ready');
        return `
          <tr data-recipient-id="${this.escapeHtml(p.id)}">
            <td>${this.escapeHtml(p.handle)}</td>
            <td>${this.escapeHtml(outcome)}</td>
            <td>${this.escapeHtml(detail)}</td>
          </tr>
        `;
      })
      .join('');

    this.modalBackdropEl.hidden = false;
    // Cancel is the default focused button per safety rules
    this.modalCancelBtn.focus();
  }

  public openQueueReportModal(): void {
    this.modalOpen = true;
    this.modalMode = 'queue_report';
    this.modalResendWrapEl.hidden = true;
    this.modalConfirmBtn.hidden = true;
    this.modalPauseBtn.hidden = false;
    this.modalStopQueueBtn.hidden = false;
    this.modalCancelBtn.textContent = 'Close';
    this.modalTitleEl.textContent = 'Social action queue';
    this.renderQueueReportRows();
    this.modalBackdropEl.hidden = false;
    this.modalCancelBtn.focus();
  }

  private renderQueueReportRows(): void {
    const snap = this.snapshot;
    const q = snap?.invite_queue;
    this.modalSummaryEl.textContent = this.formatQueueSummary(q);
    const active = Boolean(q && q.active && !q.cancelling);
    this.modalPauseBtn.disabled = !active;
    this.modalStopQueueBtn.disabled = !active;
    this.modalPauseBtn.textContent = q?.paused ? 'Resume' : 'Pause';

    const results = q?.results ?? snap?.batch_results ?? [];
    this.modalTbodyEl.innerHTML = results
      .map(
        (r) => `
        <tr data-recipient-id="${this.escapeHtml(r.id)}">
          <td>${this.escapeHtml(r.handle)}</td>
          <td>${this.escapeHtml(r.outcome)}</td>
          <td>${this.escapeHtml(r.detail ?? '')}</td>
        </tr>
      `,
      )
      .join('');
  }

  public closeModal(): void {
    this.modalOpen = false;
    this.modalBackdropEl.hidden = true;
  }

  public openOrgImportModal(): void {
    this.orgImportSymbolInput.value = '';
    this.orgImportStatusEl.textContent = '';
    this.orgImportSubmitBtn.disabled = false;
    this.orgModalBackdropEl.hidden = false;
    this.orgImportSymbolInput.focus();
  }

  public closeOrgImportModal(): void {
    this.orgModalBackdropEl.hidden = true;
  }

  private renderMarketCatalog(): void {
    const items: MarketCatalogItem[] = this.snapshot?.market_items ?? [];
    const filter = this.marketSearch.trim().toLowerCase();
    const filtered = items
      .filter((item) => !filter || item.name.toLowerCase().includes(filter))
      .sort((a, b) => a.name.localeCompare(b.name))
      .slice(0, 500);

    const html = filtered
      .map((item) => `<option value="${item.id}">${this.escapeHtml(item.name)}</option>`)
      .join('');
    if (this.marketItemSelectEl.innerHTML !== html) {
      this.marketItemSelectEl.innerHTML = html;
      if (this.selectedMarketItemId && filtered.some((i) => i.id === this.selectedMarketItemId)) {
        this.marketItemSelectEl.value = String(this.selectedMarketItemId);
      }
    }
  }

  private renderMarket(): void {
    const snap = this.snapshot;
    if (!snap) return;
    const watches: BuyerWatch[] = snap.watches ?? [];
    if (!this.selectedWatchId && watches.length > 0) {
      this.selectedWatchId = watches[0].id;
    }

    const nextIds = new Set(watches.map((w) => w.id));
    for (const [id, tr] of Array.from(this.watchRowMap.entries())) {
      if (!nextIds.has(id)) {
        tr.remove();
        this.watchRowMap.delete(id);
      }
    }

    for (const w of watches) {
      let tr = this.watchRowMap.get(w.id);
      if (!tr) {
        tr = this.marketWatchesTbodyEl.ownerDocument.createElement('tr');
        tr.dataset.watchId = w.id;
        tr.addEventListener('click', () => {
          this.selectedWatchId = w.id;
          this.renderMarket();
        });
        this.watchRowMap.set(w.id, tr);
        this.marketWatchesTbodyEl.appendChild(tr);
      }
      tr.classList.toggle('is-selected', w.id === this.selectedWatchId);
      const qualText = w.quality ? `Q${w.quality}` : 'Any';
      const minText = w.minimum_price ? `${w.minimum_price} / ${w.unit ?? 'unit'}` : 'Any price';
      const matchesCount = (w.matches ?? []).length;
      const statusText = !w.enabled ? 'Paused' : w.error ? 'Refresh unavailable' : 'Checked';
      tr.innerHTML = `
        <td>${this.escapeHtml(w.name)}</td>
        <td>${this.escapeHtml(qualText)}</td>
        <td>${this.escapeHtml(minText)}</td>
        <td>${matchesCount}</td>
        <td>${this.escapeHtml(statusText)}</td>
      `;
    }

    this.marketNoticesHeadingEl.textContent = this.showMatches
      ? 'Current matching buy requests — select one to open its UEX advertisement'
      : 'Recent HUD notices — buyer matches and tagged-player appearances';
    this.marketShowMatchesBtn.textContent = this.showMatches ? 'Show notices' : 'Show matches';

    let notices: CompanionNotice[] = snap.notifications ?? [];
    if (this.showMatches) {
      const activeWatch = watches.find((w) => w.id === this.selectedWatchId);
      notices = (activeWatch?.matches ?? []).map((m) => ({
        title: 'BUY REQUEST',
        detail: `${m.price} UEC / ${m.unit} · ${m.location}`,
        at: m.renewed ?? 0,
        url: m.url,
      }));
    }

    this.marketNoticesTbodyEl.innerHTML = notices
      .map(
        (n) => `
        <tr>
          <td>${this.escapeHtml(`${n.title} · ${n.detail}`)}</td>
          <td>${n.at ? 'Recent' : '—'}</td>
        </tr>
      `,
      )
      .join('');
  }

  private renderHome(): void {
    const home = this.snapshot?.home;
    const session = this.homeShowPrevious ? home?.previous : home?.current;
    const blueprints = session?.blueprints ?? [];
    const rep = session?.reputation ?? [];
    const contracts = session?.contracts_completed ?? 0;

    this.root
      .querySelector('#home-session-current')!
      .classList.toggle('is-active', !this.homeShowPrevious);
    this.root
      .querySelector('#home-session-prev')!
      .classList.toggle('is-active', this.homeShowPrevious);

    const metricsEl = this.root.querySelector('#home-metrics-row')!;
    metricsEl.innerHTML = `
      <div class="ss-metric-card">
        <span class="ss-metric-value">${blueprints.length}</span>
        <span class="ss-metric-label">Blueprints received</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${contracts}</span>
        <span class="ss-metric-label">Contracts completed</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${rep.length}</span>
        <span class="ss-metric-label">Reputation changes</span>
      </div>
    `;

    const bpListEl = this.root.querySelector('#home-blueprints-list')!;
    bpListEl.innerHTML =
      blueprints.length === 0
        ? '<li class="ss-muted-text">No blueprint grants recorded in this session.</li>'
        : blueprints.map((b) => `<li>${this.escapeHtml(b.name)}</li>`).join('');

    const repListEl = this.root.querySelector('#home-rep-list')!;
    repListEl.innerHTML =
      rep.length === 0
        ? '<li class="ss-muted-text">No balance changes between the saved reads.</li>'
        : rep
            .map(
              (r) =>
                `<li><strong>${this.escapeHtml(r.faction)}</strong> <span class="ss-accent-text">${r.delta > 0 ? `+${r.delta}` : r.delta}</span></li>`,
            )
            .join('');

    const strings = home?.synthstrings;
    const patchEl = this.root.querySelector('#home-patch-banner')!;
    if (strings?.title) {
      patchEl.innerHTML = `
        <strong>${this.escapeHtml(strings.patch_label ?? 'Star Citizen')}</strong>
        <span>${this.escapeHtml(strings.status_label ?? 'Game text unchanged — No action needed')} · ${this.escapeHtml(strings.summary ?? '')}</span>
      `;
    } else {
      patchEl.innerHTML = `
        <strong>${this.escapeHtml(home?.identity || 'No live shard observation')}</strong>
        <span>Game text unchanged — No action needed</span>
      `;
    }
  }

  private escapeHtml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}
