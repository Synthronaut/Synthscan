import {
  ACTION_LIMIT,
  ActionLogEntry,
  BuyerWatch,
  ChatChannel,
  ChatMessage,
  CompanionNotice,
  DesktopBridge,
  InviteQueueState,
  MarketCatalogItem,
  PeopleSnapshot,
  Player,
  normalizePlayer,
} from './bridge';
import { personColor, splitTags, tagColor } from './colors';
import { DaylightViewController } from './daylight_view';
import { PiracyViewController } from './piracy_view';
import { MissionViewController } from './mission_view';

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

  private snapshot: PeopleSnapshot | null = null;
  private activeMode: 'people' | 'buyer_alerts' | 'home' | 'settings' | 'daylight' | 'hud_piracy' | 'mission_log' = 'people';
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
  private partyPeople: Player[] = [];

  // Citizens sub-mode ('roster' vs 'chat') and Live Chat state
  private peopleSubMode: 'roster' | 'party' | 'chat' | 'log' = 'roster';
  private selectedChatChannelId = 'all';
  private selectedSendChannelId = '';
  private chatShowRawCodes = false;
  private chatLiveTranslate = true;
  private lastChatSignature = '';
  private lastPartySignature = '';

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
  private footerEl!: HTMLElement;
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
  private daylightSectionEl!: HTMLElement;
  private daylightController: DaylightViewController | null = null;
  private piracySectionEl!: HTMLElement;
  private piracyController: PiracyViewController | null = null;
  private missionSectionEl!: HTMLElement;
  private missionController: MissionViewController | null = null;
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
  private contextMenuEl: HTMLElement | null = null;
  private pendingQueueFeedback: { text: string; at: number } | null = null;

  // Actions Log DOM elements
  private actionLogTbodyEl!: HTMLTableSectionElement;
  private actionLogCountEl!: HTMLElement;
  private actionLogFilterEl!: HTMLSelectElement;
  private actionLogClearBtn!: HTMLButtonElement;
  private actionLogFilter = 'all';

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

  // Citizens sub-mode, Party box & Live Chat DOM elements
  private peopleModeRosterBtn!: HTMLButtonElement;
  private peopleModePartyBtn!: HTMLButtonElement;
  private peopleModeChatBtn!: HTMLButtonElement;
  private peopleModeLogBtn!: HTMLButtonElement;
  private peopleRosterWorkspaceEl!: HTMLElement;
  private peoplePartyWorkspaceEl!: HTMLElement;
  private peopleChatWorkspaceEl!: HTMLElement;
  private peopleLogWorkspaceEl!: HTMLElement;
  private partyHeaderEl!: HTMLElement;
  private partyListEl!: HTMLElement;
  private leavePartyBtn!: HTMLButtonElement;
  private chatChannelTabsEl!: HTMLElement;
  private chatAutoTranslateCheckboxEl!: HTMLInputElement;
  private chatShowRawCheckboxEl!: HTMLInputElement;
  private chatRefreshBtn!: HTMLButtonElement;
  private chatStatusLineEl!: HTMLElement;
  private chatMessagesScrollEl!: HTMLElement;
  private chatSendChannelSelectEl!: HTMLSelectElement;
  private chatSendInputEl!: HTMLInputElement;
  private chatEncodeZhCheckboxEl!: HTMLInputElement;
  private chatSendBtn!: HTMLButtonElement;
  private chatVoiceBtn!: HTMLButtonElement;
  private isVoiceRecording = false;
  private voicePressStartTime = 0;

  constructor(root: HTMLElement, bridge: DesktopBridge) {
    this.root = root;
    this.bridge = bridge;
    this.buildShell();
    this.unsubscribe = this.bridge.subscribePeople((snap) => {
      this.onSnapshot(snap);
    });
  }

  public destroy(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
    if (this.daylightController) {
      this.daylightController.destroy();
      this.daylightController = null;
    }
    if (this.piracyController) {
      this.piracyController.destroy();
      this.piracyController = null;
    }
    if (this.missionController) {
      this.missionController.destroy();
      this.missionController = null;
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
      <div class="ss-shell">
        <section id="ss-view-people" class="ss-view">
          <div class="ss-toolbar-row ss-people-subnav">
            <div class="ss-mode-tabs" role="tablist" aria-label="Citizens workspace view">
              <button id="people-mode-roster-btn" type="button" class="ss-tab is-active" role="tab" aria-selected="true">Citizens</button>
              <button id="people-mode-party-btn" type="button" class="ss-tab" role="tab" aria-selected="false">Party</button>
              <button id="people-mode-chat-btn" type="button" class="ss-tab" role="tab" aria-selected="false">Live Chat &amp; Translator</button>
              <button id="people-mode-log-btn" type="button" class="ss-tab" role="tab" aria-selected="false">Actions Log</button>
            </div>
            <span class="ss-hint-line">Native gRPC social &amp; chat feed · Zero screen capture or OCR</span>
          </div>

          <div id="people-roster-workspace" class="ss-people-grid">
            <!-- Left Column: Roster -->
            <div class="ss-card ss-roster-pane">
              <div class="ss-toolbar-row">
                <input id="people-search-input" class="ss-input ss-grow" type="text" placeholder="Filter this list by handle or tag" autocomplete="off" />
                <button id="people-clear-btn" type="button" class="ss-btn">Clear</button>
              </div>
              <div class="ss-toolbar-row ss-toolbar-sub">
                <select id="people-source-select" class="ss-select" aria-label="Citizen list source">
                  <option value="0">Shard members</option>
                  <option value="1">Handle search results</option>
                  <option value="2">Saved citizen tags</option>
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
                <span id="people-roster-status" class="ss-status-line">Loading citizen list…</span>
                <span class="ss-hint-line">Citizens · click to select / right-click for actions</span>
              </div>
              <div id="people-roster-scroll" class="ss-table-scroll" tabindex="0" role="region" aria-label="Citizen roster">
                <table class="ss-table" id="people-roster-table">
                  <thead>
                    <tr>
                      <th class="col-player">CITIZEN</th>
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
                  <select id="stage-tag-select" class="ss-select ss-grow" aria-label="Stage citizens by tag"></select>
                  <button id="stage-by-tag-btn" type="button" class="ss-btn">Add by tag</button>
                  <button id="stage-friends-btn" type="button" class="ss-btn">Add friends →</button>
                  <button id="stage-org-btn" type="button" class="ss-btn">Add org →</button>
                </div>
                <div class="ss-pane-meta">
                  <span id="people-action-header" class="ss-status-line">Action list · 0 / 50</span>
                  <span class="ss-hint-line">Tags: shard citizens · Friend: your friends list</span>
                </div>
                <div id="people-action-scroll" class="ss-table-scroll ss-action-scroll" tabindex="0" role="region" aria-label="Staged action list">
                  <table class="ss-table" id="people-action-table">
                    <thead>
                      <tr>
                        <th class="col-player">CITIZEN</th>
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

          <!-- Party Workspace (Tab 2) -->
          <div id="people-party-workspace" class="ss-card ss-party-workspace" hidden style="display: none !important;">
            <div class="ss-pane-meta">
              <span id="people-party-header" class="ss-status-line">Party · Solo</span>
              <div class="ss-toolbar-row">
                <span class="ss-hint-line">Right-click member or click Actions to make leader or remove</span>
                <button id="leave-party-btn" type="button" class="ss-btn ss-btn-xs" hidden>Leave</button>
              </div>
            </div>
            <div id="people-party-list" class="ss-party-list ss-party-list-full" role="region" aria-label="Current party members"></div>
          </div>

          <!-- Live Chat & Translator Workspace -->
          <div id="people-chat-workspace" class="ss-card ss-chat-workspace" hidden style="display: none !important;">
            <div class="ss-toolbar-row ss-toolbar-sub">
              <div id="chat-channel-tabs" class="ss-mode-tabs ss-chat-channel-tabs" role="tablist" aria-label="Chat channels">
                <button type="button" class="ss-tab is-active" data-channel-id="all">All Channels</button>
              </div>
              <div class="ss-toolbar-row">
                <label class="ss-checkbox-label" title="Automatically translate decoded [zh] and foreign messages into English">
                  <input id="chat-auto-translate-checkbox" type="checkbox" checked />
                  <span>Live translate</span>
                </label>
                <label class="ss-checkbox-label" title="Also display the raw [zh] @CODE string underneath decoded messages">
                  <input id="chat-show-raw-checkbox" type="checkbox" />
                  <span>Show raw [zh]</span>
                </label>
                <button id="chat-refresh-btn" type="button" class="ss-btn">Refresh chat</button>
              </div>
            </div>
            <div class="ss-pane-meta">
              <span id="chat-status-line" class="ss-status-line">Waiting for active shard channels…</span>
              <span class="ss-hint-line">Decodes [zh] @CODE chat automatically · Right-click any sender for social &amp; party actions</span>
            </div>
            <div id="chat-messages-scroll" class="ss-table-scroll ss-chat-feed" tabindex="0" role="log" aria-label="Live game chat feed"></div>
            <div class="ss-toolbar-row ss-chat-compose">
              <select id="chat-send-channel-select" class="ss-select ss-chat-channel-select" aria-label="Target chat channel">
                <option value="">Select channel…</option>
              </select>
              <input id="chat-send-input" class="ss-input ss-grow" type="text" maxlength="480" placeholder="Type message or click 🎙️ Talk to speak… (Enter to send)" autocomplete="off" />
              <button id="chat-voice-btn" type="button" class="ss-btn ss-btn-voice" title="Click &amp; hold to talk, release to send (or click to toggle)">🎙️ Talk</button>
              <label class="ss-checkbox-label" title="Translate outgoing text to Simplified Chinese and encode as [zh] @CODE so Chinese players can read it in-game">
                <input id="chat-encode-zh-checkbox" type="checkbox" />
                <span>Send as [zh]</span>
              </label>
              <button id="chat-send-btn" type="button" class="ss-btn ss-btn-accent">Send</button>
            </div>
          </div>

          <!-- Actions Log Workspace (Tab 4) -->
          <div id="people-log-workspace" class="ss-card ss-log-workspace" hidden style="display: none !important;">
            <div class="ss-pane-meta ss-activity-log-header">
              <div class="ss-toolbar-row">
                <span class="ss-status-line" id="action-log-title">Actions Log</span>
                <span class="ss-activity-log-count" id="action-log-count">0</span>
                <span class="ss-hint-line">Tags, friend &amp; party invites, and accepted / declined responses</span>
              </div>
              <div class="ss-toolbar-row">
                <select id="action-log-filter" class="ss-select ss-select-xs" aria-label="Filter actions log">
                  <option value="all">All events</option>
                  <option value="tags">Tags</option>
                  <option value="friend">Friend invites</option>
                  <option value="party">Party invites</option>
                  <option value="responses">Accepted / Declined</option>
                </select>
                <button id="action-log-clear-btn" type="button" class="ss-btn ss-btn-xs">Clear log</button>
              </div>
            </div>
            <div id="action-log-body" class="ss-table-scroll ss-activity-log-scroll" tabindex="0" role="region" aria-label="Citizen actions log">
              <table class="ss-table ss-activity-log-table">
                <thead>
                  <tr>
                    <th class="col-log-time">TIME</th>
                    <th class="col-log-type">ACTION</th>
                    <th class="col-log-player">CITIZEN</th>
                    <th class="col-log-detail">DETAILS</th>
                  </tr>
                </thead>
                <tbody id="action-log-tbody"></tbody>
              </table>
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

        <!-- Home Command Dashboard View -->
        <section id="ss-view-home" class="ss-view" hidden>
          <div class="ss-home-grid">
            <!-- Top Verse Status & In-Game HUD Quick-Launch Strip -->
            <div class="ss-card ss-home-topbar">
              <div class="ss-home-status-row">
                <div class="ss-home-status-left">
                  <span id="home-conn-pill" class="ss-status-pill is-idle">OFFLINE</span>
                  <span id="home-shard-text" class="ss-muted-text">Star Citizen not running</span>
                </div>
                <span id="home-strings-pill" class="ss-home-strings-pill">Game text OK</span>
              </div>
              <div class="ss-home-hud-strip" aria-label="In-game HUD overlays">
                <span class="ss-home-hud-label">IN-GAME HUDS</span>
                <button type="button" class="ss-btn ss-btn-sm" data-home-nav="hud_mining">Mining HUD</button>
                <button type="button" class="ss-btn ss-btn-sm" data-home-nav="hud_finder">Finder HUD</button>
                <button type="button" class="ss-btn ss-btn-sm" data-home-nav="hud_missions">Missions HUD</button>
                <button type="button" class="ss-btn ss-btn-sm" data-home-nav="hud_hangars">Hangars HUD</button>
              </div>
            </div>

            <!-- Refinery Order Completion Notification -->
            <div id="home-refinery-banner" class="ss-refinery-banner" style="display:none;"></div>

            <!-- Session Recap Card -->
            <div class="ss-card ss-home-recap-card">
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

        <section id="ss-view-daylight" class="ss-view" hidden></section>
        <section id="ss-view-piracy" class="ss-view" hidden></section>
        <section id="ss-view-mission" class="ss-view" hidden></section>

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
                    <th>Citizen</th>
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
    this.footerEl = this.root.querySelector('.ss-footer')!;
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

    this.actionLogTbodyEl = this.root.querySelector('#action-log-tbody')!;
    this.actionLogCountEl = this.root.querySelector('#action-log-count')!;
    this.actionLogFilterEl = this.root.querySelector('#action-log-filter')!;
    this.actionLogClearBtn = this.root.querySelector('#action-log-clear-btn')!;

    this.peopleSectionEl = this.root.querySelector('#ss-view-people')!;
    this.marketSectionEl = this.root.querySelector('#ss-view-market')!;
    this.homeSectionEl = this.root.querySelector('#ss-view-home')!;
    this.settingsSectionEl = this.root.querySelector('#ss-view-settings')!;
    this.daylightSectionEl = this.root.querySelector('#ss-view-daylight')!;
    this.daylightController = new DaylightViewController(this.daylightSectionEl, this.bridge, {
      onCopyNotice: (msg) => {
        if (this.footerStatusEl) this.footerStatusEl.textContent = msg;
      },
    });
    this.piracySectionEl = this.root.querySelector('#ss-view-piracy')!;
    this.missionSectionEl = this.root.querySelector('#ss-view-mission')!;
    this.missionController = new MissionViewController(this.missionSectionEl, this.bridge, {
      onNotice: (msg) => {
        if (this.footerStatusEl) this.footerStatusEl.textContent = msg;
      },
    });
    this.piracyController = new PiracyViewController(this.piracySectionEl, this.bridge, {
      onNotice: (msg) => {
        if (this.footerStatusEl) this.footerStatusEl.textContent = msg;
      },
    });

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

    this.marketSearchInputEl = this.root.querySelector('#market-search-input')!;
    this.marketItemSelectEl = this.root.querySelector('#market-item-select')!;
    this.marketQualityInputEl = this.root.querySelector('#market-quality-input')!;
    this.marketPriceInputEl = this.root.querySelector('#market-price-input')!;
    this.marketUnitInputEl = this.root.querySelector('#market-unit-input')!;
    this.marketWatchesTbodyEl = this.root.querySelector('#market-watches-tbody')!;
    this.marketNoticesTbodyEl = this.root.querySelector('#market-notices-tbody')!;
    this.marketNoticesHeadingEl = this.root.querySelector('#market-notices-heading')!;
    this.marketShowMatchesBtn = this.root.querySelector('#market-show-matches-btn')!;

    this.peopleModeRosterBtn = this.root.querySelector('#people-mode-roster-btn')!;
    this.peopleModePartyBtn = this.root.querySelector('#people-mode-party-btn')!;
    this.peopleModeChatBtn = this.root.querySelector('#people-mode-chat-btn')!;
    this.peopleModeLogBtn = this.root.querySelector('#people-mode-log-btn')!;
    this.peopleRosterWorkspaceEl = this.root.querySelector('#people-roster-workspace')!;
    this.peoplePartyWorkspaceEl = this.root.querySelector('#people-party-workspace')!;
    this.peopleChatWorkspaceEl = this.root.querySelector('#people-chat-workspace')!;
    this.peopleLogWorkspaceEl = this.root.querySelector('#people-log-workspace')!;
    this.partyHeaderEl = this.root.querySelector('#people-party-header')!;
    this.partyListEl = this.root.querySelector('#people-party-list')!;
    this.leavePartyBtn = this.root.querySelector('#leave-party-btn')!;
    this.chatChannelTabsEl = this.root.querySelector('#chat-channel-tabs')!;
    this.chatAutoTranslateCheckboxEl = this.root.querySelector('#chat-auto-translate-checkbox')!;
    this.chatShowRawCheckboxEl = this.root.querySelector('#chat-show-raw-checkbox')!;
    this.chatRefreshBtn = this.root.querySelector('#chat-refresh-btn')!;
    this.chatStatusLineEl = this.root.querySelector('#chat-status-line')!;
    this.chatMessagesScrollEl = this.root.querySelector('#chat-messages-scroll')!;
    this.chatSendChannelSelectEl = this.root.querySelector('#chat-send-channel-select')!;
    this.chatSendInputEl = this.root.querySelector('#chat-send-input')!;
    this.chatEncodeZhCheckboxEl = this.root.querySelector('#chat-encode-zh-checkbox')!;
    this.chatSendBtn = this.root.querySelector('#chat-send-btn')!;
    this.chatVoiceBtn = this.root.querySelector('#chat-voice-btn')!;

    this.bindEvents();
  }

  private bindEvents(): void {
    // Settings tiles navigation
    this.root.querySelectorAll<HTMLButtonElement>('[data-nav]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.nav;
        if (target) {
          void this.bridge.sendCommand({ action: 'navigate', page: target, target });
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
      this.closeContextMenu();
    });
    this.rosterTbodyEl.addEventListener('click', (ev) => {
      this.closeContextMenu();
      const tr = (ev.target as HTMLElement).closest<HTMLTableRowElement>('tr[data-player-id]');
      if (!tr) return;
      const id = tr.dataset.playerId!;
      this.toggleSelection(id, ev.shiftKey, false);
    });

    // Right-click context menu in Roster table and Action table
    const handleTableContextMenu = (ev: MouseEvent, list: Player[]) => {
      const rawTarget = ev.target as { closest?: unknown; parentElement?: Element | null } | null;
      const targetEl =
        rawTarget && typeof rawTarget.closest === 'function'
          ? (rawTarget as Element)
          : rawTarget?.parentElement ?? null;
      const tr = targetEl?.closest<HTMLTableRowElement>('tr[data-player-id]');
      if (!tr) return;
      const id = tr.dataset.playerId!;
      const player = list.find((p) => p.id === id);
      if (!player) return;

      ev.preventDefault();
      ev.stopPropagation();
      const rect = typeof tr.getBoundingClientRect === 'function' ? tr.getBoundingClientRect() : null;
      const x = ev.clientX || (rect ? rect.left + 80 : 240);
      const y = ev.clientY || (rect ? rect.bottom : 180);
      this.openContextMenu(player, x, y);
    };

    this.rosterTbodyEl.addEventListener('contextmenu', (ev) => {
      handleTableContextMenu(ev, this.filteredPeople);
    });
    this.actionTbodyEl.addEventListener('contextmenu', (ev) => {
      handleTableContextMenu(ev, this.actionPeople);
    });

    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
      document.addEventListener('click', (ev) => {
        if (this.contextMenuEl && !this.contextMenuEl.contains(ev.target as Node)) {
          this.closeContextMenu();
        }
      });

      document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') {
          this.closeContextMenu();
        }
      });
    }

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
        this.footerStatusEl.textContent = 'Add eligible citizens to the Action list first.';
        return;
      }
      this.openConfirmationModal('confirm_friend', targets);
    });

    this.invitePartyBtn.addEventListener('click', () => {
      const targets = this.getActionTargets().filter((p) => !p.in_party);
      if (targets.length === 0) {
        this.footerStatusEl.textContent = 'Add eligible citizens to the Action list first.';
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

    // Actions Log controls
    this.actionLogFilterEl.addEventListener('change', () => {
      this.actionLogFilter = this.actionLogFilterEl.value;
      this.renderActionLog();
    });
    this.actionLogClearBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'clear_action_log' });
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
        this.pendingQueueFeedback = {
          text: `Queuing ${ids.length} ${action === 'friend_many' ? 'friend request(s)' : 'party invite(s)'}…`,
          at: Date.now(),
        };
        this.updateStatusAndControls();
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
    this.root.querySelectorAll<HTMLButtonElement>('button[data-home-nav]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const page = btn.dataset.homeNav;
        if (page) {
          void this.bridge.sendCommand({ action: 'navigate', page });
        }
      });
    });

    // Citizens top mode switch (Citizens vs Party vs Live Chat & Translator vs Actions Log)
    this.peopleModeRosterBtn.addEventListener('click', () => {
      this.setPeopleSubMode('roster');
    });
    this.peopleModePartyBtn.addEventListener('click', () => {
      this.setPeopleSubMode('party');
    });
    this.peopleModeChatBtn.addEventListener('click', () => {
      this.setPeopleSubMode('chat');
    });
    this.peopleModeLogBtn.addEventListener('click', () => {
      this.setPeopleSubMode('log');
    });

    // Party list interactions (right-click or Actions button)
    this.partyListEl.addEventListener('contextmenu', (ev) => {
      const row = (ev.target as HTMLElement).closest<HTMLElement>('[data-party-player-id]');
      if (!row) return;
      const pid = row.dataset.partyPlayerId!;
      const player = this.partyPeople.find((p) => p.id === pid);
      if (!player) return;
      ev.preventDefault();
      this.openContextMenu(player, ev.clientX || 240, ev.clientY || 180);
    });

    this.partyListEl.addEventListener('click', (ev) => {
      const btn = (ev.target as HTMLElement).closest<HTMLElement>('[data-party-menu-id]');
      if (!btn) return;
      const pid = btn.dataset.partyMenuId!;
      const player = this.partyPeople.find((p) => p.id === pid);
      if (!player) return;
      ev.stopPropagation();
      const rect = typeof btn.getBoundingClientRect === 'function' ? btn.getBoundingClientRect() : { left: 240, bottom: 180 };
      this.openContextMenu(player, rect.left, rect.bottom + 4);
    });

    this.leavePartyBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({
        action: 'leave_party',
        confirmed: true,
      });
    });

    // Live Chat controls
    this.chatChannelTabsEl.addEventListener('click', (ev) => {
      const tab = (ev.target as HTMLElement).closest<HTMLElement>('[data-channel-id]');
      if (!tab) return;
      const channelId = tab.dataset.channelId ?? 'all';
      this.selectedChatChannelId = channelId;
      if (channelId !== 'all') {
        this.selectedSendChannelId = channelId;
        this.chatSendChannelSelectEl.value = channelId;
      }
      this.lastChatSignature = '';
      this.renderChat();
    });

    this.chatAutoTranslateCheckboxEl.addEventListener('change', () => {
      this.chatLiveTranslate = this.chatAutoTranslateCheckboxEl.checked;
      this.lastChatSignature = '';
      this.renderChat();
      void this.bridge.sendCommand({
        action: 'set_chat_translate',
        enabled: this.chatLiveTranslate,
      });
    });

    this.chatShowRawCheckboxEl.addEventListener('change', () => {
      this.chatShowRawCodes = this.chatShowRawCheckboxEl.checked;
      this.lastChatSignature = '';
      this.renderChat();
    });

    this.chatRefreshBtn.addEventListener('click', () => {
      void this.bridge.sendCommand({ action: 'refresh_chat' });
    });

    this.chatSendChannelSelectEl.addEventListener('change', () => {
      this.selectedSendChannelId = this.chatSendChannelSelectEl.value;
    });

    const submitChatMessage = () => {
      const text = this.chatSendInputEl.value.trim();
      const groupId = this.chatSendChannelSelectEl.value || this.selectedSendChannelId;
      if (!groupId) {
        this.footerStatusEl.textContent = 'Select an active chat channel before sending.';
        return;
      }
      if (!text) return;
      const encodeZh = this.chatEncodeZhCheckboxEl.checked;
      this.chatSendInputEl.value = '';
      void this.bridge.sendCommand({
        action: 'send_chat_message',
        group_id: groupId,
        text,
        encode_zh: encodeZh,
        confirmed: true,
      });
    };

    this.chatSendBtn.addEventListener('click', submitChatMessage);
    this.chatSendInputEl.addEventListener('keydown', (ev) => {
      if ((ev as KeyboardEvent).key === 'Enter') {
        ev.preventDefault();
        submitChatMessage();
      }
    });

    const playCommsTone = (type: 'start' | 'end'): void => {
      try {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        const now = ctx.currentTime;
        if (type === 'start') {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(880, now);
          osc.frequency.exponentialRampToValueAtTime(1760, now + 0.04);
          gain.gain.setValueAtTime(0.06, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
          osc.start(now);
          osc.stop(now + 0.05);
        } else {
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(1400, now);
          osc.frequency.exponentialRampToValueAtTime(700, now + 0.06);
          gain.gain.setValueAtTime(0.06, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
          osc.start(now);
          osc.stop(now + 0.07);
        }
      } catch {}
    };

    const startVoice = (ev?: Event): void => {
      if (ev) ev.preventDefault();
      if (this.isVoiceRecording) return;
      this.voicePressStartTime = Date.now();
      this.isVoiceRecording = true;
      this.chatVoiceBtn.classList.add('is-recording');
      this.chatVoiceBtn.innerHTML = '<span class="ss-voice-pulse"></span>🎙️ Recording…';
      playCommsTone('start');
      void this.bridge.sendCommand({ action: 'start_voice_dictation' });
    };

    const stopVoice = (ev?: Event, send = true): void => {
      if (ev) ev.preventDefault();
      if (!this.isVoiceRecording) return;
      this.isVoiceRecording = false;
      this.chatVoiceBtn.classList.remove('is-recording');
      this.chatVoiceBtn.innerHTML = '🎙️ Talk';
      playCommsTone('end');
      const targetChannelId = this.selectedSendChannelId || this.chatSendChannelSelectEl.value;
      void this.bridge.sendCommand({
        action: 'stop_voice_dictation',
        send,
        group_id: targetChannelId,
        encode_zh: this.chatEncodeZhCheckboxEl.checked,
      });
    };

    this.chatVoiceBtn.addEventListener('pointerdown', (ev) => {
      if ((ev as MouseEvent).button === 0) {
        startVoice(ev);
      }
    });

    this.chatVoiceBtn.addEventListener('pointerup', (ev) => {
      const duration = Date.now() - this.voicePressStartTime;
      if (duration > 350) {
        stopVoice(ev, true);
      }
    });

    this.chatVoiceBtn.addEventListener('click', (ev) => {
      const duration = Date.now() - this.voicePressStartTime;
      if (!this.isVoiceRecording) {
        startVoice(ev);
      } else if (duration <= 350) {
        stopVoice(ev, true);
      }
    });

    this.chatMessagesScrollEl.addEventListener('contextmenu', (ev) => {
      const msgEl = (ev.target as HTMLElement).closest<HTMLElement>('[data-sender-id]');
      if (!msgEl) return;
      const senderId = msgEl.dataset.senderId ?? '';
      const senderHandle = msgEl.dataset.senderHandle ?? senderId;
      if (!senderId) return;
      const existing =
        this.snapshot?.players.find((p) => p.id === senderId) ??
        this.partyPeople.find((p) => p.id === senderId) ??
        (this.snapshot?.friend_people ?? []).find((p) => p.id === senderId) ??
        normalizePlayer({ id: senderId, handle: senderHandle, on_shard: true });
      ev.preventDefault();
      this.openContextMenu(existing, ev.clientX || 240, ev.clientY || 180);
    });
  }

  public setPeopleSubMode(subMode: 'roster' | 'party' | 'chat' | 'log'): void {
    this.peopleSubMode = subMode;
    const isRoster = subMode === 'roster';
    const isParty = subMode === 'party';
    const isChat = subMode === 'chat';
    const isLog = subMode === 'log';

    this.peopleModeRosterBtn.classList.toggle('is-active', isRoster);
    this.peopleModeRosterBtn.setAttribute('aria-selected', isRoster ? 'true' : 'false');
    this.peopleModePartyBtn.classList.toggle('is-active', isParty);
    this.peopleModePartyBtn.setAttribute('aria-selected', isParty ? 'true' : 'false');
    this.peopleModeChatBtn.classList.toggle('is-active', isChat);
    this.peopleModeChatBtn.setAttribute('aria-selected', isChat ? 'true' : 'false');
    this.peopleModeLogBtn.classList.toggle('is-active', isLog);
    this.peopleModeLogBtn.setAttribute('aria-selected', isLog ? 'true' : 'false');

    this.peopleRosterWorkspaceEl.hidden = !isRoster;
    this.peoplePartyWorkspaceEl.hidden = !isParty;
    this.peopleChatWorkspaceEl.hidden = !isChat;
    this.peopleLogWorkspaceEl.hidden = !isLog;

    this.peopleRosterWorkspaceEl.style.setProperty('display', isRoster ? 'grid' : 'none', 'important');
    this.peoplePartyWorkspaceEl.style.setProperty('display', isParty ? 'flex' : 'none', 'important');
    this.peopleChatWorkspaceEl.style.setProperty('display', isChat ? 'flex' : 'none', 'important');
    this.peopleLogWorkspaceEl.style.setProperty('display', isLog ? 'flex' : 'none', 'important');

    void this.bridge.sendCommand({
      action: 'set_chat_active',
      active: isChat,
    });
    if (isChat) {
      this.lastChatSignature = '';
      this.renderChat();
    } else if (isParty) {
      this.renderParty();
    } else if (isLog) {
      this.renderActionLog();
    }
  }

  private closeContextMenu(): void {
    if (this.contextMenuEl) {
      this.contextMenuEl.remove();
      this.contextMenuEl = null;
    }
  }

  private openContextMenu(player: Player, x: number, y: number): void {
    this.closeContextMenu();

    const doc = this.root.ownerDocument;
    const menu = doc.createElement('div');
    menu.className = 'ss-context-menu';
    menu.id = 'ss-roster-context-menu';

    const header = doc.createElement('div');
    header.className = 'ss-context-menu-header';
    header.textContent = player.handle;
    menu.appendChild(header);

    // Party management options when player is in party
    if (player.in_party && !player.is_self) {
      const canManageParty = this.snapshot?.is_party_leader !== false;

      const promoteBtn = doc.createElement('button');
      promoteBtn.type = 'button';
      promoteBtn.className = 'ss-context-menu-item';
      promoteBtn.id = 'ctx-make-party-leader-btn';
      promoteBtn.textContent = player.is_leader
        ? 'Already Party Leader'
        : canManageParty
          ? 'Make Party Leader'
          : 'Make Party Leader (Leader Only)';
      if (player.is_leader || !canManageParty) {
        promoteBtn.disabled = true;
      } else {
        promoteBtn.addEventListener('click', () => {
          this.closeContextMenu();
          void this.bridge.sendCommand({
            action: 'transfer_party_leader',
            player_id: player.id,
            handle: player.handle,
            confirmed: true,
          });
        });
      }
      menu.appendChild(promoteBtn);

      const kickBtn = doc.createElement('button');
      kickBtn.type = 'button';
      kickBtn.className = 'ss-context-menu-item ss-context-menu-danger';
      kickBtn.id = 'ctx-kick-party-member-btn';
      kickBtn.textContent = canManageParty
        ? 'Remove from Party'
        : 'Remove from Party (Leader Only)';
      if (!canManageParty) {
        kickBtn.disabled = true;
      } else {
        kickBtn.addEventListener('click', () => {
          this.closeContextMenu();
          void this.bridge.sendCommand({
            action: 'kick_party_member',
            player_id: player.id,
            handle: player.handle,
            confirmed: true,
          });
        });
      }
      menu.appendChild(kickBtn);

      const partyDiv = doc.createElement('div');
      partyDiv.className = 'ss-context-menu-divider';
      menu.appendChild(partyDiv);
    }

    const hasSession = Boolean(this.snapshot?.session && this.snapshot.session.length > 0);
    const socialBusy = Boolean(this.snapshot?.social_busy);

    // Friend Request item
    const friendBtn = doc.createElement('button');
    friendBtn.type = 'button';
    friendBtn.className = 'ss-context-menu-item';
    friendBtn.textContent = player.friend_requested_before
      ? 'Send Friend Request (Retry)'
      : 'Send Friend Request';
    if (player.is_self || player.is_friend || !hasSession || socialBusy) {
      friendBtn.disabled = true;
      if (player.is_friend) friendBtn.textContent = 'Already Friend';
      else if (!hasSession) friendBtn.textContent = 'Send Friend Request (Wait for shard)';
      else if (socialBusy) friendBtn.textContent = 'Send Friend Request (Queue running)';
    } else {
      friendBtn.addEventListener('click', () => {
        this.closeContextMenu();
        this.pendingQueueFeedback = {
          text: `Queuing friend request for ${player.handle}…`,
          at: Date.now(),
        };
        this.updateStatusAndControls();
        void this.bridge.sendCommand({
          action: 'friend',
          player_id: player.id,
          confirmed: true,
          resend: Boolean(player.friend_requested_before),
        });
      });
    }
    menu.appendChild(friendBtn);

    // Invite Party item
    const partyBtn = doc.createElement('button');
    partyBtn.type = 'button';
    partyBtn.className = 'ss-context-menu-item';
    partyBtn.textContent = player.invited_before ? 'Invite to Party (Retry)' : 'Invite to Party';
    if (player.is_self || player.in_party || !hasSession || socialBusy) {
      partyBtn.disabled = true;
      if (player.in_party) partyBtn.textContent = 'Already in Party';
      else if (!hasSession) partyBtn.textContent = 'Invite to Party (Wait for shard)';
      else if (socialBusy) partyBtn.textContent = 'Invite to Party (Queue running)';
    } else {
      partyBtn.addEventListener('click', () => {
        this.closeContextMenu();
        this.pendingQueueFeedback = {
          text: `Queuing party invite for ${player.handle}…`,
          at: Date.now(),
        };
        this.updateStatusAndControls();
        void this.bridge.sendCommand({
          action: 'party',
          player_id: player.id,
          confirmed: true,
          resend: Boolean(player.invited_before),
          allow_friends: Boolean(player.is_friend),
        });
      });
    }
    menu.appendChild(partyBtn);

    // Divider
    const div1 = doc.createElement('div');
    div1.className = 'ss-context-menu-divider';
    menu.appendChild(div1);

    // Tag Presets Header
    const tagHeader = doc.createElement('div');
    tagHeader.style.padding = '4px 14px 2px';
    tagHeader.style.fontSize = '11px';
    tagHeader.style.color = 'var(--ss-muted, #94a3b8)';
    tagHeader.textContent = 'DESIGNATE TAG:';
    menu.appendChild(tagHeader);

    // Preset buttons grid
    const grid = doc.createElement('div');
    grid.className = 'ss-context-menu-tag-grid';
    const presets = ['Friendly', 'Trader', 'Scout', 'Target', 'Miner', 'Org'];
    for (const preset of presets) {
      const btn = doc.createElement('button');
      btn.type = 'button';
      btn.className = 'ss-context-menu-tag-btn';
      btn.textContent = preset;
      btn.addEventListener('click', () => {
        this.closeContextMenu();
        void this.bridge.sendCommand({
          action: 'tag',
          player_id: player.id,
          label: preset,
          alert: true,
        });
      });
      grid.appendChild(btn);
    }
    menu.appendChild(grid);

    // Custom Tag input row
    const customRow = doc.createElement('div');
    customRow.className = 'ss-context-menu-custom-tag';
    const input = doc.createElement('input');
    input.type = 'text';
    input.placeholder = 'Custom tag…';
    input.maxLength = 32;
    const saveBtn = doc.createElement('button');
    saveBtn.type = 'button';
    saveBtn.textContent = 'Tag';
    const applyCustom = () => {
      const val = input.value.trim();
      if (!val) return;
      this.closeContextMenu();
      void this.bridge.sendCommand({
        action: 'tag',
        player_id: player.id,
        label: val,
        alert: true,
      });
    };
    saveBtn.addEventListener('click', applyCustom);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        applyCustom();
      }
    });
    customRow.appendChild(input);
    customRow.appendChild(saveBtn);
    menu.appendChild(customRow);

    // Clear tag option if player has tags
    if (player.tags && player.tags.length > 0) {
      const clearBtn = doc.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'ss-context-menu-item';
      clearBtn.style.color = '#f87171';
      clearBtn.textContent = '✕ Remove Tag';
      clearBtn.addEventListener('click', () => {
        this.closeContextMenu();
        void this.bridge.sendCommand({
          action: 'tag',
          player_id: player.id,
          label: '',
          clear_tags: true,
        });
      });
      menu.appendChild(clearBtn);
    }

    // Append to document body (or root in headless tests) and position safely
    const host = (doc as Document).body ?? this.root;
    host.appendChild(menu);
    this.contextMenuEl = menu;

    const rect =
      typeof menu.getBoundingClientRect === 'function'
        ? menu.getBoundingClientRect()
        : { width: 220, height: 260 };
    const winW = typeof window !== 'undefined' && window.innerWidth ? window.innerWidth : 1280;
    const winH = typeof window !== 'undefined' && window.innerHeight ? window.innerHeight : 800;
    let posX = x;
    let posY = y;
    if (posX + rect.width > winW - 8) {
      posX = Math.max(8, winW - rect.width - 8);
    }
    if (posY + rect.height > winH - 8) {
      posY = Math.max(8, winH - rect.height - 8);
    }
    menu.style.left = `${posX}px`;
    menu.style.top = `${posY}px`;
  }

  public setMode(mode: 'people' | 'buyer_alerts' | 'home' | 'settings' | 'daylight' | 'hud_piracy' | 'mission_log'): void {
    this.activeMode = mode;
    this.peopleSectionEl.hidden = mode !== 'people';
    this.marketSectionEl.hidden = mode !== 'buyer_alerts';
    this.homeSectionEl.hidden = mode !== 'home';
    this.settingsSectionEl.hidden = mode !== 'settings';
    this.daylightSectionEl.hidden = mode !== 'daylight';
    this.piracySectionEl.hidden = mode !== 'hud_piracy';
    this.missionSectionEl.hidden = mode !== 'mission_log';
    if (mode === 'mission_log') {
      this.missionController?.activate();
    }

    if (this.footerEl) {
      this.footerEl.hidden = mode !== 'people' && mode !== 'hud_piracy' && mode !== 'mission_log';
    }

    const titleEl = this.root.querySelector('#ss-page-title');
    const subEl = this.root.querySelector('#ss-page-subtitle');
    if (titleEl && subEl) {
      if (mode === 'people') {
        titleEl.textContent = 'Citizens';
        subEl.textContent = 'A familiar face in a very large universe.';
      } else if (mode === 'buyer_alerts') {
        titleEl.textContent = 'Buyer Alerts';
        subEl.textContent = 'Watch UEX buy orders for your best mining and crafting hauls.';
      } else if (mode === 'daylight') {
        titleEl.textContent = 'Day/Night Forecast';
        subEl.textContent = 'Destination-first solar geometry. Plan for the light when you arrive.';
      } else if (mode === 'hud_piracy') {
        titleEl.textContent = 'Flight / Piracy';
        subEl.textContent = 'Live Game.log avionics, unmonitored jurisdiction radar, and snare ops.';
      } else if (mode === 'mission_log') {
        titleEl.textContent = 'Mission & Wallet Log';
        subEl.textContent = 'Every contract, reputation shift and aUEC movement, grouped by play session.';
      } else if (mode === 'home') {
        titleEl.textContent = 'Home';
        subEl.textContent = "Find your next upgrade. See what you've accomplished.";
      } else {
        titleEl.textContent = 'Settings & Modules';
        subEl.textContent = 'Customize HUD behavior, shortcuts, privacy, and installed modules.';
      }
    }
  }

  private onSnapshot(snap: PeopleSnapshot): void {
    if (snap.mode && snap.mode !== this.activeMode) {
      this.setMode(snap.mode);
    }
    this.snapshot = snap;
    this.renderPeople();
    this.renderMarketCatalog();
    this.renderMarket();
    this.renderHome();
    if (snap.daylight && this.daylightController) {
      this.daylightController.updateFromDaylightState(snap.daylight);
    }
    if (this.piracyController) {
      this.piracyController.updateFromSnapshot(snap.piracy, snap.session_token ?? snap.session);
    }
    if (this.missionController) {
      this.missionController.updateFromState(snap.mission);
    }
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
    this.renderParty();
    this.renderChat();
    this.renderActionLog();
    if (snap.last_dictated_text && this.chatSendInputEl) {
      this.chatSendInputEl.value = snap.last_dictated_text;
    }
    if (snap.voice_dictating === false && this.isVoiceRecording && this.chatVoiceBtn) {
      this.isVoiceRecording = false;
      this.chatVoiceBtn.classList.remove('is-recording');
      this.chatVoiceBtn.innerHTML = '🎙️ Talk';
    }
    this.updateStatusAndControls();
  }

  private renderTagChips(tags: string[], fontSize?: number, height?: number): string {
    const sizeStyle = fontSize && height ? `font-size:${fontSize}px;height:${height}px;line-height:${height - 2}px;` : '';
    return tags
      .filter((t) => t && t.trim())
      .map((t) => {
        const c = tagColor(t);
        const bgR = Math.trunc((14 * 4 + c.r) / 5);
        const bgG = Math.trunc((18 * 4 + c.g) / 5);
        const bgB = Math.trunc((25 * 4 + c.b) / 5);
        return `<span class="ss-tag-chip" data-tag="${this.escapeHtml(t)}" style="color:${c.css};background:rgb(${bgR},${bgG},${bgB});border-color:rgba(${c.r},${c.g},${c.b},0.49);${sizeStyle}">${this.escapeHtml(t)}</span>`;
      })
      .join('');
  }

  private renderParty(): void {
    const snap = this.snapshot;
    if (!snap) return;

    const rawParty = snap.party_people ?? [];
    this.partyPeople = rawParty;

    const leaderId = snap.party_leader_id ?? '';
    const isLeader = Boolean(snap.is_party_leader);
    const count = rawParty.length;

    if (count <= 1) {
      this.partyHeaderEl.textContent = 'Party · Solo / none';
      this.leavePartyBtn.hidden = true;
    } else {
      this.partyHeaderEl.textContent = `Party · ${count} members${isLeader ? ' (You are Leader)' : ''}`;
      this.leavePartyBtn.hidden = false;
    }

    const partySig = `${snap.session}|${snap.revision ?? 0}|${leaderId}|${isLeader ? '1' : '0'}|${rawParty.map((p) => `${p.id}:${p.handle}:${p.is_leader ? '1' : '0'}:${p.tag ?? ''}`).join(',')}`;
    if (partySig === this.lastPartySignature) {
      return;
    }
    this.lastPartySignature = partySig;

    if (rawParty.length === 0) {
      this.partyListEl.innerHTML = '<div class="ss-party-empty ss-muted-text">Not in a party. Invite shard citizens or friends below.</div>';
      return;
    }

    const doc = this.root.ownerDocument;
    this.partyListEl.innerHTML = '';
    for (const p of rawParty) {
      const card = doc.createElement('div');
      card.className = `ss-party-card${p.is_leader ? ' is-leader' : ''}${p.is_self ? ' is-self' : ''}`;
      card.dataset.partyPlayerId = p.id;

      const pColor = personColor(p);
      const tags = p.tags && p.tags.length > 0 ? p.tags : splitTags(p.tag);
      const chipsHtml = this.renderTagChips(tags, 10, 18);

      card.innerHTML = `
        <div class="ss-party-card-main">
          <span class="ss-person-badge" style="color:${pColor.css}">●</span>
          <div class="ss-player-stack">
            <div class="ss-party-handle-row">
              <strong class="ss-player-handle">${this.escapeHtml(p.handle)}</strong>
              ${p.is_leader ? '<span class="ss-party-leader-badge">★ Leader</span>' : ''}
              ${p.is_self ? '<span class="ss-party-self-badge">You</span>' : ''}
            </div>
            ${chipsHtml ? `<div class="ss-tags-run" style="margin-top:2px;">${chipsHtml}</div>` : ''}
          </div>
        </div>
        <div class="ss-party-card-actions">
          <button type="button" class="ss-btn ss-btn-xs" data-party-menu-id="${this.escapeHtml(p.id)}" title="Manage member">Actions ▾</button>
        </div>
      `;
      this.partyListEl.appendChild(card);
    }
  }

  private renderChat(): void {
    if (this.peopleSubMode !== 'chat') {
      return;
    }
    const snap = this.snapshot;
    if (!snap) return;

    // Filter out ship channels defensively (user requested zero ship channels)
    const channels: ChatChannel[] = (snap.chat_channels ?? []).filter((ch) => ch.kind !== 'ship');
    const allMsgs: ChatMessage[] = (snap.chat_messages ?? []).filter((m) => m.channel_kind !== 'ship');

    // Render / update channel pills
    const tabsDoc = this.root.ownerDocument;
    const currentTabId = this.selectedChatChannelId;

    let tabsHtml = `<button type="button" class="ss-tab${currentTabId === 'all' ? ' is-active' : ''}" data-channel-id="all">All Channels</button>`;
    for (const ch of channels) {
      const active = currentTabId === ch.id ? ' is-active' : '';
      const badgeCls = `ss-chat-badge-${ch.kind}`;
      tabsHtml += `<button type="button" class="ss-tab${active}" data-channel-id="${this.escapeHtml(ch.id)}"><span class="ss-chat-kind-badge ${badgeCls}"></span>${this.escapeHtml(ch.label)}</button>`;
    }
    if (this.chatChannelTabsEl.innerHTML !== tabsHtml) {
      this.chatChannelTabsEl.innerHTML = tabsHtml;
    }

    // Populate compose channel selector options
    const sendOptionsHtml = [
      '<option value="">Select channel…</option>',
      ...channels.map((ch) => `<option value="${this.escapeHtml(ch.id)}">${this.escapeHtml(ch.label)}</option>`),
    ].join('');
    if (this.chatSendChannelSelectEl.innerHTML !== sendOptionsHtml) {
      this.chatSendChannelSelectEl.innerHTML = sendOptionsHtml;
      if (this.selectedSendChannelId && channels.some((c) => c.id === this.selectedSendChannelId)) {
        this.chatSendChannelSelectEl.value = this.selectedSendChannelId;
      } else if (channels.length > 0) {
        // Default to Global (or first channel)
        const def = channels.find((c) => c.kind === 'global') ?? channels[0];
        this.selectedSendChannelId = def.id;
        this.chatSendChannelSelectEl.value = def.id;
      }
    }

    // Status line
    const activeCh = channels.find((c) => c.id === currentTabId);
    let statusText = activeCh ? `${activeCh.label} · ${activeCh.member_count ?? 0} members` : `${channels.length} active channels · ${allMsgs.length} messages`;
    if (snap.chat_loading) statusText += ' · refreshing…';
    if (snap.chat_sending) statusText += ' · sending message…';
    if (snap.chat_error) statusText += ` · ${snap.chat_error}`;
    this.chatStatusLineEl.textContent = statusText;

    // Filter messages by selected channel
    const visibleMsgs = currentTabId === 'all' ? allMsgs : allMsgs.filter((m) => m.group_id === currentTabId);

    // Compute signature to skip DOM rebuild when no new messages
    const sig = `${currentTabId}|${snap.revision ?? 0}|${this.chatShowRawCodes ? '1' : '0'}|${this.chatLiveTranslate ? '1' : '0'}|${visibleMsgs.map((m) => `${m.id}:${m.content}:${m.translated_content ?? ''}:${(m.sender_tags ?? []).join('-')}`).join(',')}`;
    if (sig === this.lastChatSignature) {
      return;
    }
    this.lastChatSignature = sig;

    if (visibleMsgs.length === 0) {
      this.chatMessagesScrollEl.innerHTML = '<div class="ss-chat-empty ss-muted-text">No chat messages recorded in this channel yet. Send a message below or click Refresh.</div>';
      return;
    }

    const wasScrolledToBottom =
      this.chatMessagesScrollEl.scrollHeight - this.chatMessagesScrollEl.scrollTop - 20 <=
      this.chatMessagesScrollEl.clientHeight;

    this.chatMessagesScrollEl.innerHTML = '';
    for (const m of visibleMsgs) {
      const item = tabsDoc.createElement('div');
      item.className = `ss-chat-msg ss-chat-kind-${m.channel_kind}${m.is_self ? ' is-self' : ''}`;
      item.dataset.senderId = m.sender_id;
      item.dataset.senderHandle = m.sender_handle;

      const timeStr = m.at > 0 ? new Date(m.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
      const senderColor = m.is_self ? 'var(--ss-self)' : m.in_party ? 'var(--ss-party)' : m.is_friend ? 'var(--ss-friend)' : 'var(--ss-ink)';
      const channelBadge = currentTabId === 'all' ? `<span class="ss-chat-channel-tag ss-chat-badge-${m.channel_kind}">${this.escapeHtml(m.channel_label)}</span>` : '';

      let tags: string[] = m.sender_tags && m.sender_tags.length > 0 ? [...m.sender_tags] : splitTags(m.sender_tag);
      if (tags.length === 0 && snap.tags) {
        const sid = m.sender_id || '';
        const bareId = sid.startsWith('urn:sc:global:player:geid:') ? sid.slice('urn:sc:global:player:geid:'.length) : sid;
        const prefId = sid.startsWith('urn:sc:global:player:geid:') ? sid : (sid ? `urn:sc:global:player:geid:${sid}` : '');
        const handleLower = (m.sender_handle || '').trim().toLowerCase();

        let foundTag = (sid ? snap.tags[sid] : undefined) || (bareId ? snap.tags[bareId] : undefined) || (prefId ? snap.tags[prefId] : undefined);
        if (!foundTag && handleLower) {
          for (const t of Object.values(snap.tags)) {
            if (t.handle && t.handle.trim().toLowerCase() === handleLower) {
              foundTag = t;
              break;
            }
          }
        }
        if (foundTag) {
          tags = splitTags(foundTag.label);
          if (foundTag.is_friend && !tags.includes('Friend')) tags.push('Friend');
          if (foundTag.in_party && !tags.includes('Party')) tags.push('Party');
        }
      }
      const tagsHtml = this.renderTagChips(tags, 9.5, 16);

      let translationHtml = '';
      if (this.chatLiveTranslate && m.translated_content && m.translated_content.trim()) {
        translationHtml = `
          <div class="ss-chat-translation">
            <span class="ss-chat-trans-icon" title="Translated to English">🌐 EN:</span>
            <span class="ss-chat-trans-text">${this.escapeHtml(m.translated_content)}</span>
          </div>
        `;
      }

      let rawZhHtml = '';
      if (this.chatShowRawCodes && m.was_zh_encoded && m.raw_content && m.raw_content !== m.content) {
        rawZhHtml = `<div class="ss-chat-raw-code">${this.escapeHtml(m.raw_content)}</div>`;
      }

      item.innerHTML = `
        <div class="ss-chat-msg-header">
          ${channelBadge}
          <span class="ss-chat-sender" style="color:${senderColor}">${this.escapeHtml(m.sender_handle)}</span>
          ${m.is_self ? '<span class="ss-party-self-badge">You</span>' : ''}
          ${tagsHtml ? `<div class="ss-tags-run">${tagsHtml}</div>` : ''}
          <span class="ss-chat-time">${timeStr}</span>
        </div>
        <div class="ss-chat-body">
          <div class="ss-chat-text">${this.escapeHtml(m.content)}</div>
          ${translationHtml}
          ${rawZhHtml}
        </div>
      `;
      this.chatMessagesScrollEl.appendChild(item);
    }

    if (wasScrolledToBottom || visibleMsgs.length <= 15) {
      this.chatMessagesScrollEl.scrollTop = this.chatMessagesScrollEl.scrollHeight;
    }
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
    const chipsHtml = this.renderTagChips(tags);

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
    return this.getChosenRosterPlayers().filter((p) => p.on_shard !== false || Boolean(p.is_friend));
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
    if (this.pendingQueueFeedback && (queueActive || socialBusy || Date.now() - this.pendingQueueFeedback.at > 4500)) {
      this.pendingQueueFeedback = null;
    }
    this.viewQueueBtn.disabled = !(snap.batch_results && snap.batch_results.length > 0) && !q?.id;
    this.pauseQueueBtn.disabled = !queueActive;
    this.cancelQueueBtn.disabled = !queueActive;
    this.pauseQueueBtn.textContent = q?.paused ? 'Resume' : 'Pause';
    if (this.pendingQueueFeedback) {
      this.queueStatusEl.textContent = this.pendingQueueFeedback.text;
      this.queueStatusEl.className = 'ss-queue-summary is-queuing';
    } else {
      this.queueStatusEl.textContent = this.formatQueueSummary(q);
      const stateClass = !q?.id
        ? ''
        : q.active && q.paused
          ? 'is-paused'
          : q.active
            ? 'is-active'
            : q.state === 'Completed'
              ? 'is-done'
              : 'is-stopped';
      this.queueStatusEl.className = `ss-queue-summary ${stateClass}`.trim();
    }

    // Footer status
    if (this.footerEl) {
      this.footerEl.hidden =
        this.activeMode !== 'people' &&
        this.activeMode !== 'hud_piracy' &&
        this.activeMode !== 'mission_log';
    }
    if (this.activeMode === 'people') {
      let footer = this.pendingQueueFeedback ? this.pendingQueueFeedback.text : (snap.status ?? 'Ready');
      footer += ' · Tagged-citizen alerts report list appearances; the first snapshot stays quiet.';
      if (snap.friends_known === false || snap.party_known === false) {
        footer += ' · Friend / party status is checking or unavailable; unconfirmed rows stay neutral.';
      }
      this.footerStatusEl.textContent = footer;
    }
  }

  private renderActionLog(): void {
    const entries: ActionLogEntry[] = this.snapshot?.action_log ?? [];
    const filtered = entries.filter((entry) => {
      if (this.actionLogFilter === 'tags') return entry.kind === 'tag';
      if (this.actionLogFilter === 'friend') {
        return entry.kind === 'friend_sent' || entry.kind === 'friend_accepted' || entry.kind === 'friend_rejected';
      }
      if (this.actionLogFilter === 'party') {
        return (
          entry.kind === 'party_sent' ||
          entry.kind === 'party_accepted' ||
          entry.kind === 'party_rejected' ||
          entry.kind === 'party_manage'
        );
      }
      if (this.actionLogFilter === 'responses') {
        return (
          entry.kind === 'friend_accepted' ||
          entry.kind === 'friend_rejected' ||
          entry.kind === 'party_accepted' ||
          entry.kind === 'party_rejected'
        );
      }
      return true;
    });

    this.actionLogCountEl.textContent = String(filtered.length);
    this.actionLogClearBtn.disabled = entries.length === 0;

    if (filtered.length === 0) {
      this.actionLogTbodyEl.innerHTML =
        '<tr><td colspan="4" class="ss-activity-log-empty">No recorded actions yet. Tag citizens or send friend / party invites to log activity here.</td></tr>';
      return;
    }

    const badgeFor = (entry: ActionLogEntry): { label: string; cls: string } => {
      switch (entry.kind) {
        case 'tag':
          return { label: entry.outcome === 'Cleared' ? 'Tags Cleared' : 'Tagged', cls: 'is-tag' };
        case 'friend_sent':
          return {
            label: entry.outcome === 'Sent' ? 'Friend Sent' : `Friend (${entry.outcome || 'Note'})`,
            cls: entry.outcome === 'Sent' ? 'is-sent' : 'is-warn',
          };
        case 'friend_accepted':
          return { label: 'Friend Accepted', cls: 'is-accepted' };
        case 'friend_rejected':
          return { label: 'Friend Declined', cls: 'is-declined' };
        case 'party_sent':
          return {
            label: entry.outcome === 'Sent' ? 'Party Sent' : `Party (${entry.outcome || 'Note'})`,
            cls: entry.outcome === 'Sent' ? 'is-sent' : 'is-warn',
          };
        case 'party_accepted':
          return { label: 'Party Accepted', cls: 'is-accepted' };
        case 'party_rejected':
          return { label: 'Party Declined', cls: 'is-declined' };
        case 'party_manage':
          return { label: `Party · ${entry.outcome || 'Action'}`, cls: 'is-tag' };
        default:
          return { label: entry.outcome || 'Action', cls: 'is-tag' };
      }
    };

    this.actionLogTbodyEl.innerHTML = filtered
      .map((entry) => {
        const d = new Date(entry.at * 1000);
        const timeStr = Number.isFinite(d.getTime())
          ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          : '';
        const badge = badgeFor(entry);
        return `
          <tr>
            <td class="col-log-time">${this.escapeHtml(timeStr)}</td>
            <td class="col-log-type"><span class="ss-log-badge ${badge.cls}">${this.escapeHtml(badge.label)}</span></td>
            <td class="col-log-player">${this.escapeHtml(entry.handle)}</td>
            <td class="col-log-detail">${this.escapeHtml(entry.detail)}</td>
          </tr>
        `;
      })
      .join('');
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

    // Top Verse Status & SynthStrings indicator
    const connPillEl = this.root.querySelector('#home-conn-pill');
    const shardTextEl = this.root.querySelector('#home-shard-text');
    const stringsPillEl = this.root.querySelector('#home-strings-pill');
    const connected = Boolean(home?.connected || this.snapshot?.piracy?.game_running);
    if (connPillEl && shardTextEl) {
      connPillEl.className = `ss-status-pill ${connected ? 'is-flight' : 'is-idle'}`;
      connPillEl.textContent = connected ? 'ONLINE' : 'OFFLINE';
      const shardLabel = home?.identity || this.snapshot?.session || '';
      shardTextEl.textContent = connected
        ? shardLabel
          ? `Connected · ${shardLabel}`
          : 'Star Citizen running'
        : 'Star Citizen not running';
    }

    const strings = home?.synthstrings;
    if (stringsPillEl) {
      const attention = strings?.status_kind === 'attention';
      stringsPillEl.className = `ss-home-strings-pill${attention ? ' is-attention' : ''}`;
      stringsPillEl.textContent = strings?.status_label
        ? strings.status_label
        : attention
          ? 'Game text needs attention'
          : 'Game text OK';
    }

    // Refinery order completion banner
    const refBannerEl = this.root.querySelector('#home-refinery-banner') as HTMLElement | null;
    if (refBannerEl) {
      const orders = (home?.refinery ?? []).filter((r) => !r.dismissed && r.station);
      const fallbackNotice = (home?.refinery_notice ?? '').trim();
      if (orders.length > 0) {
        const lines = orders.map((r) => {
          const count = r.count && r.count > 1 ? `${r.count} refinery orders` : 'Refinery order';
          return `<strong>${this.escapeHtml(count)} at ${this.escapeHtml(r.station)}</strong> finished`;
        });
        refBannerEl.style.display = 'flex';
        refBannerEl.innerHTML = `
          <div class="ss-refinery-banner-text">
            <span class="ss-refinery-badge">REFINERY READY</span>
            <span>${lines.join(' · ')}</span>
          </div>
          <div class="ss-refinery-banner-actions">
            <button type="button" class="ss-btn ss-btn-sm ss-btn-accent" id="home-open-refinery-btn">Open Refinery</button>
            <button type="button" class="ss-btn ss-btn-sm" id="home-dismiss-refinery-btn">Dismiss</button>
          </div>
        `;
        refBannerEl.querySelector('#home-open-refinery-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'navigate', page: 'refinery' });
        });
        refBannerEl.querySelector('#home-dismiss-refinery-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'navigate', page: 'dismiss_refinery' });
        });
      } else if (fallbackNotice) {
        refBannerEl.style.display = 'flex';
        refBannerEl.innerHTML = `
          <div class="ss-refinery-banner-text">
            <span class="ss-refinery-badge">REFINERY READY</span>
            <span>${this.escapeHtml(fallbackNotice)}</span>
          </div>
          <div class="ss-refinery-banner-actions">
            <button type="button" class="ss-btn ss-btn-sm ss-btn-accent" id="home-open-refinery-btn">Open Refinery</button>
            <button type="button" class="ss-btn ss-btn-sm" id="home-dismiss-refinery-btn">Dismiss</button>
          </div>
        `;
        refBannerEl.querySelector('#home-open-refinery-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'navigate', page: 'refinery' });
        });
        refBannerEl.querySelector('#home-dismiss-refinery-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'navigate', page: 'dismiss_refinery' });
        });
      } else {
        refBannerEl.style.display = 'none';
        refBannerEl.innerHTML = '';
      }
    }

    this.root
      .querySelector('#home-session-current')!
      .classList.toggle('is-active', !this.homeShowPrevious);
    this.root
      .querySelector('#home-session-prev')!
      .classList.toggle('is-active', this.homeShowPrevious);

    // Net aUEC from Mission & Wallet Log for the selected session
    const missionSessions = this.snapshot?.mission?.sessions ?? [];
    const targetMissionSession = this.homeShowPrevious
      ? missionSessions[1]
      : (missionSessions.find((s) => s.id === this.snapshot?.mission?.current_session) ?? missionSessions[0]);
    const auecWallet = targetMissionSession?.wallet?.find((w) => w.currency.toLowerCase() === 'auec');
    const netAuec = auecWallet?.delta;
    const netAuecText =
      typeof netAuec === 'number'
        ? `${netAuec > 0 ? '+' : ''}${Math.round(netAuec).toLocaleString('en-US')}`
        : '—';
    const netAuecCls =
      typeof netAuec === 'number' && netAuec !== 0 ? (netAuec > 0 ? ' ss-text-ok' : ' ss-text-bad') : '';

    // Flight sorties & helm time (current session)
    const flight = this.snapshot?.piracy?.flight;
    const sortiesCount = !this.homeShowPrevious ? (flight?.total_sorties ?? 0) : null;
    const helmSec = !this.homeShowPrevious ? (flight?.total_helm_s ?? 0) : 0;
    const helmLabel =
      helmSec >= 3600
        ? `${Math.floor(helmSec / 3600)}h ${Math.floor((helmSec % 3600) / 60)}m`
        : helmSec >= 60
          ? `${Math.floor(helmSec / 60)}m`
          : `${Math.floor(helmSec)}s`;

    const metricsEl = this.root.querySelector('#home-metrics-row')!;
    metricsEl.innerHTML = `
      <div class="ss-metric-card">
        <span class="ss-metric-value${netAuecCls}">${this.escapeHtml(netAuecText)}</span>
        <span class="ss-metric-label">Net aUEC</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${contracts}</span>
        <span class="ss-metric-label">Contracts completed</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${blueprints.length}</span>
        <span class="ss-metric-label">Blueprints received</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${rep.length}</span>
        <span class="ss-metric-label">Reputation changes</span>
      </div>
      ${
        sortiesCount !== null
          ? `<div class="ss-metric-card">
              <span class="ss-metric-value">${sortiesCount} <small class="ss-metric-sub">· ${this.escapeHtml(helmLabel)}</small></span>
              <span class="ss-metric-label">Flights &amp; helm</span>
            </div>`
          : ''
      }
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

    const patchEl = this.root.querySelector('#home-patch-banner') as HTMLElement | null;
    if (patchEl) {
      if (strings?.title && strings.status_kind === 'attention') {
        patchEl.style.display = 'flex';
        const summaryText = strings.summary ? ` · ${strings.summary}` : '';
        patchEl.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;">
            <div>
              <strong>${this.escapeHtml(strings.patch_label ?? 'Star Citizen')}</strong>
              <div style="font-size:11.5px;color:var(--ss-muted);margin-top:2px;">
                ${this.escapeHtml(strings.status_label ?? 'Game text unchanged')} ${this.escapeHtml(summaryText)}
              </div>
            </div>
            <div style="display:flex;gap:8px;flex-shrink:0;">
              <button type="button" class="ss-btn ss-btn-accent" id="home-strings-settings-btn">Text settings</button>
              <button type="button" class="ss-btn" id="home-strings-patch-btn">Patch status</button>
            </div>
          </div>
        `;
        patchEl.querySelector('#home-strings-settings-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'strings_settings' });
        });
        patchEl.querySelector('#home-strings-patch-btn')?.addEventListener('click', () => {
          void this.bridge.sendCommand({ action: 'strings_details' });
        });
      } else {
        patchEl.style.display = 'none';
        patchEl.innerHTML = '';
      }
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
