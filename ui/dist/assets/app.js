var ke=Object.defineProperty;var Ce=(l,e,t)=>e in l?ke(l,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):l[e]=t;var a=(l,e,t)=>Ce(l,typeof e!="symbol"?e+"":e,t);(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const n of document.querySelectorAll('link[rel="modulepreload"]'))o(n);new MutationObserver(n=>{for(const i of n)if(i.type==="childList")for(const s of i.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&o(s)}).observe(document,{childList:!0,subtree:!0});function t(n){const i={};return n.integrity&&(i.integrity=n.integrity),n.referrerPolicy&&(i.referrerPolicy=n.referrerPolicy),n.crossOrigin==="use-credentials"?i.credentials="include":n.crossOrigin==="anonymous"?i.credentials="omit":i.credentials="same-origin",i}function o(n){if(n.ep)return;n.ep=!0;const i=t(n);fetch(n.href,i)}})();const y=50,Re=new Set(["friend","friend_many","party","party_many"]);function X(l){if(Re.has(l.action)){if(l.confirmed!==!0)throw new Error(`Unconfirmed outgoing social action rejected: ${l.action}`);if(l.action==="friend_many"||l.action==="party_many"){if(!Array.isArray(l.player_ids)||l.player_ids.length===0)throw new Error("Batch social action requires at least one recipient");if(l.player_ids.length>y)throw new Error(`Batch social action exceeds cap of ${y}`)}}if(l.action==="stage_people"&&Array.isArray(l.player_ids)&&l.player_ids.length>y)throw new Error(`Cannot stage more than ${y} players at once`);if(l.action==="open_uex_ad"){const e=l.url??"";if(!e.startsWith("https://uexcorp.space/marketplace/item/info/")||/[\r\n\t ]/.test(e))throw new Error("Invalid UEX advertisement URL")}}function k(l){const e=typeof l.tag=="string"?l.tag:Array.isArray(l.tags)?l.tags.join(", "):"",t=Array.isArray(l.tags)?l.tags:e.split(",").map(o=>o.trim()).filter(o=>o.length>0);return{...l,id:String(l.id),handle:String(l.handle??l.id),tags:t,tag:e}}function M(l){const t=(l.players??l.rows??[]).map(r=>k(r)),o=(l.action_people??[]).map(r=>k(r)),n=(l.friend_people??[]).map(r=>k(r)),i=(l.search??[]).map(r=>k(r)),s=l.session??l.session_token??"";return{...l,revision:typeof l.revision=="number"?l.revision:Date.now(),session:s,session_token:s,players:t,rows:t,action_people:o,friend_people:n,search:i,tag_options:l.tag_options??["Org","Friendly","Aggressive","Trader","Friend"],action_limit:typeof l.action_limit=="number"?l.action_limit:y}}class K{constructor(e){a(this,"listeners",new Set);a(this,"snapshot");a(this,"commands",[]);this.snapshot=M(e??{revision:1,session:"synthetic-session",players:[],action_people:[],friends_known:!0,party_known:!0,roster_at:Date.now()/1e3-5,status:"Ready"})}getSnapshot(){return this.snapshot}publish(e){this.snapshot=M({...this.snapshot,...e,revision:(this.snapshot.revision??0)+1});for(const t of this.listeners)t(this.snapshot)}subscribePeople(e){return this.listeners.add(e),e(this.snapshot),()=>{this.listeners.delete(e)}}async stagePlayers(e){await this.sendCommand({action:"stage_people",player_ids:e.slice(0,y)})}async sendCommand(e){X(e),this.commands.push(structuredClone(e));const t=Math.min(y,this.snapshot.action_limit??y),o=new Map;for(const n of[this.snapshot.players,this.snapshot.friend_people??[],this.snapshot.search??[],this.snapshot.action_people??[]])for(const i of n)o.set(i.id,i);if(e.action==="stage_people"&&Array.isArray(e.player_ids)){const n=[...this.snapshot.action_people??[]],i=new Set(n.map(s=>s.id));for(const s of e.player_ids){if(n.length>=t)break;if(i.has(s))continue;const r=o.get(s);r&&!r.is_self&&(r.on_shard!==!1||r.is_friend)&&(n.push(r),i.add(s))}this.publish({action_people:n})}else if(e.action==="unstage_people"&&Array.isArray(e.player_ids)){const n=new Set(e.player_ids),i=(this.snapshot.action_people??[]).filter(s=>!n.has(s.id));this.publish({action_people:i})}else if(e.action==="clear_actions")this.publish({action_people:[]});else if(e.action==="stage_tag"&&e.label){const n=[...this.snapshot.action_people??[]],i=new Set(n.map(r=>r.id)),s=e.label.trim().toLowerCase();for(const r of this.snapshot.players){if(n.length>=t)break;if(r.is_self||i.has(r.id))continue;const g=r.tags.map(h=>h.toLowerCase());(s==="org"&&(r.is_org||g.includes("org")||e.include_org_affiliate&&g.includes("org affiliate"))||s==="friend"&&(r.is_friend||g.includes("friend"))||g.includes(s))&&(n.push(r),i.add(r.id))}this.publish({action_people:n})}else e.action==="tag"&&e.player_id?this.applyTagUpdate([e.player_id],e.label??"",!!e.clear_tags,e.alert):e.action==="tag_many"&&Array.isArray(e.player_ids)&&this.applyTagUpdate(e.player_ids,e.label??"",!!e.clear_tags)}applyTagUpdate(e,t,o,n){const i=new Set(e),s=o?[]:t.split(",").map(g=>g.trim()).filter(g=>g.length>0),r=g=>g.map(c=>{if(!i.has(c.id))return c;const h=o?[]:Array.from(new Set([...s]));return k({...c,tags:h,tag:h.join(", "),manual_tag:h.join(", "),alert:typeof n=="boolean"?n:c.alert})});this.publish({players:r(this.snapshot.players),action_people:r(this.snapshot.action_people??[])})}}class Ie{constructor(){a(this,"listeners",new Set);a(this,"snapshot",null);a(this,"bridgeToken","");a(this,"sequence",0);var t;const e=typeof window<"u"?(t=window.chrome)==null?void 0:t.webview:void 0;e&&(e.addEventListener("message",o=>{const n=typeof o.data=="string"?JSON.parse(o.data):o.data;if(!n||typeof n!="object")return;const i=n;if(typeof i.bridge_token=="string"&&i.bridge_token.length>0&&(this.bridgeToken=i.bridge_token),i.kind==="snapshot"&&i.state&&typeof i.state=="object"){const s=i.state;this.snapshot=M({...s,mode:i.mode??s.mode??"people",market_items:i.market_items??s.market_items,home:i.home??s.home});for(const r of this.listeners)r(this.snapshot)}}),e.postMessage({kind:"ui_ready",at:Date.now()/1e3}))}subscribePeople(e){return this.listeners.add(e),this.snapshot&&e(this.snapshot),()=>{this.listeners.delete(e)}}async stagePlayers(e){await this.sendCommand({action:"stage_people",player_ids:e.slice(0,y)})}async sendCommand(e){var o;X(e);const t=typeof window<"u"?(o=window.chrome)==null?void 0:o.webview:void 0;if(!t)throw new Error("WebView2 host channel is not available");this.sequence+=1,t.postMessage({kind:"command",bridge_token:this.bridgeToken,client_seq:this.sequence,at:Date.now()/1e3,command:e})}}function C(l,e,t){return{r:l,g:e,b:t,css:`rgb(${l}, ${e}, ${t})`}}const J=C(193,157,255),Z=C(116,183,255),ee=C(121,225,158),Te=C(234,240,247);function I(l){return l.is_self?J:l.in_party?Z:l.is_friend?ee:Te}const qe={org:[255,145,40],friend:[45,225,122],friendly:[166,231,190],aggressive:[255,105,112],trader:[75,207,232],"org affiliate":[231,204,80],crew:[184,150,255],buyer:[106,163,255],avoid:[237,125,207]},$=new Map,L=new Set;for(const[l,[e,t,o]]of Object.entries(qe))$.set(l,C(e,t,o)),L.add(e<<16|t<<8|o);function H(l){const e=l.trim().toLowerCase(),t=$.get(e);if(t)return t;let o=2166136261;for(let c=0;c<e.length;c++)o^=e.charCodeAt(c),o=Math.imul(o,16777619)>>>0;let n=0,i=0,s=0,r=0;do{const c=o%3600/600,h=.5+(o>>>12)%25/100,b=.9+(o>>>20)%10/100,m=b*h,u=m*(1-Math.abs(c%2-1)),d=b-m;let p=0,v=0,E=0;c<1?(p=m,v=u):c<2?(p=u,v=m):c<3?(v=m,E=u):c<4?(v=u,E=m):c<5?(p=u,E=m):(p=m,E=u),n=Math.trunc((p+d)*255),i=Math.trunc((v+d)*255),s=Math.trunc((E+d)*255),r=n<<16|i<<8|s,o=o+2654435769>>>0}while(L.has(r));L.add(r);const g=C(n,i,s);return $.set(e,g),g}function Ae(l){return l?l.split(",").map(e=>e.trim()).filter(e=>e.length>0):[]}const w=40;class te{constructor(e,t){a(this,"root");a(this,"bridge");a(this,"unsubscribe",null);a(this,"snapshot",null);a(this,"activeMode","people");a(this,"sourceIndex",0);a(this,"taggedOnly",!1);a(this,"searchQuery","");a(this,"previousViewSignature","");a(this,"selectedIds",new Set);a(this,"selectionAnchorId","");a(this,"actionSelectedIds",new Set);a(this,"actionSelectionAnchorId","");a(this,"actionEditorSignature","");a(this,"rosterRowMap",new Map);a(this,"rosterRowSignature",new Map);a(this,"actionRowMap",new Map);a(this,"actionRowSignature",new Map);a(this,"watchRowMap",new Map);a(this,"filteredPeople",[]);a(this,"actionPeople",[]);a(this,"marketSearch","");a(this,"selectedMarketItemId",0);a(this,"selectedWatchId","");a(this,"showMatches",!1);a(this,"modalOpen",!1);a(this,"modalMode","confirm_party");a(this,"modalRecipients",[]);a(this,"modalResend",!1);a(this,"homeShowPrevious",!1);a(this,"virtualScrollTop",0);a(this,"virtualScrollLeft",0);a(this,"domRowCreatedCount",0);a(this,"domRowUpdatedCount",0);a(this,"domRowRemovedCount",0);a(this,"lastUpdatedRowIds",[]);a(this,"rosterScrollEl");a(this,"rosterTbodyEl");a(this,"actionScrollEl");a(this,"actionTbodyEl");a(this,"searchInputEl");a(this,"sourceSelectEl");a(this,"taggedOnlyEl");a(this,"rosterStatusEl");a(this,"selectionSummaryEl");a(this,"actionHeaderEl");a(this,"stageTagSelectEl");a(this,"applyTagSelectEl");a(this,"tagDraftInputEl");a(this,"joinAlertsCheckboxEl");a(this,"queueStatusEl");a(this,"footerStatusEl");a(this,"stageSelectedBtn");a(this,"removeActionBtn");a(this,"clearActionsBtn");a(this,"stageByTagBtn");a(this,"stageFriendsBtn");a(this,"stageOrgBtn");a(this,"addPresetTagBtn");a(this,"applyTagsBtn");a(this,"clearTagsBtn");a(this,"sendFriendsBtn");a(this,"invitePartyBtn");a(this,"viewQueueBtn");a(this,"pauseQueueBtn");a(this,"cancelQueueBtn");a(this,"peopleSectionEl");a(this,"marketSectionEl");a(this,"homeSectionEl");a(this,"settingsSectionEl");a(this,"modalBackdropEl");a(this,"modalTitleEl");a(this,"modalSummaryEl");a(this,"modalTbodyEl");a(this,"modalResendWrapEl");a(this,"modalResendCheckboxEl");a(this,"modalConfirmBtn");a(this,"modalCancelBtn");a(this,"modalPauseBtn");a(this,"modalStopQueueBtn");a(this,"marketSearchInputEl");a(this,"marketItemSelectEl");a(this,"marketQualityInputEl");a(this,"marketPriceInputEl");a(this,"marketUnitInputEl");a(this,"marketWatchesTbodyEl");a(this,"marketNoticesTbodyEl");a(this,"marketNoticesHeadingEl");a(this,"marketShowMatchesBtn");this.root=e,this.bridge=t,this.buildShell(),this.unsubscribe=this.bridge.subscribePeople(o=>{this.onSnapshot(o)})}destroy(){this.unsubscribe&&(this.unsubscribe(),this.unsubscribe=null)}getFilteredPeople(){return this.filteredPeople}getActionPeople(){return this.actionPeople}getSelectedIds(){return Array.from(this.selectedIds)}getActionSelectedIds(){return Array.from(this.actionSelectedIds)}getRosterRowElement(e){return this.rosterRowMap.get(e)}getActionRowElement(e){return this.actionRowMap.get(e)}isModalOpen(){return this.modalOpen}getScrollAnchor(){const e=Math.round(this.virtualScrollTop),t=Math.round(this.virtualScrollLeft),o=Math.max(0,Math.min(this.filteredPeople.length-1,Math.floor(e/w))),n=o>=0&&o<this.filteredPeople.length?this.filteredPeople[o].id:"",i=e-o*w;return{anchorId:n,offsetWithinRow:i,scrollTop:e,scrollLeft:t}}setRosterScroll(e,t=0){this.virtualScrollTop=Math.max(0,Math.round(e)),this.virtualScrollLeft=Math.max(0,Math.round(t)),this.rosterScrollEl.scrollTop=this.virtualScrollTop,this.rosterScrollEl.scrollLeft=this.virtualScrollLeft}buildShell(){this.root.innerHTML=`
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
      </div>
    `,this.rosterScrollEl=this.root.querySelector("#people-roster-scroll"),this.rosterTbodyEl=this.root.querySelector("#people-roster-tbody"),this.actionScrollEl=this.root.querySelector("#people-action-scroll"),this.actionTbodyEl=this.root.querySelector("#people-action-tbody"),this.searchInputEl=this.root.querySelector("#people-search-input"),this.sourceSelectEl=this.root.querySelector("#people-source-select"),this.taggedOnlyEl=this.root.querySelector("#people-tagged-only"),this.rosterStatusEl=this.root.querySelector("#people-roster-status"),this.selectionSummaryEl=this.root.querySelector("#people-selection-summary"),this.actionHeaderEl=this.root.querySelector("#people-action-header"),this.stageTagSelectEl=this.root.querySelector("#stage-tag-select"),this.applyTagSelectEl=this.root.querySelector("#apply-tag-select"),this.tagDraftInputEl=this.root.querySelector("#tag-draft-input"),this.joinAlertsCheckboxEl=this.root.querySelector("#join-alerts-checkbox"),this.queueStatusEl=this.root.querySelector("#queue-status-text"),this.footerStatusEl=this.root.querySelector("#companion-footer-status"),this.stageSelectedBtn=this.root.querySelector("#stage-selected-btn"),this.removeActionBtn=this.root.querySelector("#remove-action-btn"),this.clearActionsBtn=this.root.querySelector("#clear-actions-btn"),this.stageByTagBtn=this.root.querySelector("#stage-by-tag-btn"),this.stageFriendsBtn=this.root.querySelector("#stage-friends-btn"),this.stageOrgBtn=this.root.querySelector("#stage-org-btn"),this.addPresetTagBtn=this.root.querySelector("#add-preset-tag-btn"),this.applyTagsBtn=this.root.querySelector("#apply-tags-btn"),this.clearTagsBtn=this.root.querySelector("#clear-tags-btn"),this.sendFriendsBtn=this.root.querySelector("#send-friends-btn"),this.invitePartyBtn=this.root.querySelector("#invite-party-btn"),this.viewQueueBtn=this.root.querySelector("#view-queue-btn"),this.pauseQueueBtn=this.root.querySelector("#pause-queue-btn"),this.cancelQueueBtn=this.root.querySelector("#cancel-queue-btn"),this.peopleSectionEl=this.root.querySelector("#ss-view-people"),this.marketSectionEl=this.root.querySelector("#ss-view-market"),this.homeSectionEl=this.root.querySelector("#ss-view-home"),this.settingsSectionEl=this.root.querySelector("#ss-view-settings"),this.modalBackdropEl=this.root.querySelector("#ss-modal-backdrop"),this.modalTitleEl=this.root.querySelector("#ss-modal-title"),this.modalSummaryEl=this.root.querySelector("#ss-modal-summary"),this.modalTbodyEl=this.root.querySelector("#ss-modal-tbody"),this.modalResendWrapEl=this.root.querySelector("#ss-modal-resend-wrap"),this.modalResendCheckboxEl=this.root.querySelector("#ss-modal-resend-checkbox"),this.modalConfirmBtn=this.root.querySelector("#ss-modal-confirm-btn"),this.modalCancelBtn=this.root.querySelector("#ss-modal-cancel-btn"),this.modalPauseBtn=this.root.querySelector("#ss-modal-pause-btn"),this.modalStopQueueBtn=this.root.querySelector("#ss-modal-stop-btn"),this.marketSearchInputEl=this.root.querySelector("#market-search-input"),this.marketItemSelectEl=this.root.querySelector("#market-item-select"),this.marketQualityInputEl=this.root.querySelector("#market-quality-input"),this.marketPriceInputEl=this.root.querySelector("#market-price-input"),this.marketUnitInputEl=this.root.querySelector("#market-unit-input"),this.marketWatchesTbodyEl=this.root.querySelector("#market-watches-tbody"),this.marketNoticesTbodyEl=this.root.querySelector("#market-notices-tbody"),this.marketNoticesHeadingEl=this.root.querySelector("#market-notices-heading"),this.marketShowMatchesBtn=this.root.querySelector("#market-show-matches-btn"),this.bindEvents()}bindEvents(){this.root.querySelectorAll(".ss-tab").forEach(e=>{e.addEventListener("click",()=>{const t=e.dataset.mode??"people";this.setMode(t)})}),this.root.querySelectorAll("[data-nav]").forEach(e=>{e.addEventListener("click",()=>{const t=e.dataset.nav;t&&this.bridge.sendCommand({action:"navigate",target:t})})}),this.searchInputEl.addEventListener("input",()=>{this.searchQuery=this.searchInputEl.value,this.searchQuery.trim()===""&&this.sourceIndex===1&&(this.sourceIndex=0,this.sourceSelectEl.value="0"),this.renderPeople()}),this.root.querySelector("#people-clear-btn").addEventListener("click",()=>{this.searchQuery="",this.searchInputEl.value="",this.sourceIndex=0,this.sourceSelectEl.value="0",this.renderPeople()}),this.root.querySelector("#people-find-btn").addEventListener("click",()=>{this.sourceIndex=1,this.sourceSelectEl.value="1",this.bridge.sendCommand({action:"search",query:this.searchInputEl.value.trim()}),this.renderPeople()}),this.root.querySelector("#people-refresh-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_people"})}),this.sourceSelectEl.addEventListener("change",()=>{this.sourceIndex=Number(this.sourceSelectEl.value)||0,this.renderPeople()}),this.taggedOnlyEl.addEventListener("change",()=>{this.taggedOnly=this.taggedOnlyEl.checked,this.renderPeople()}),this.rosterScrollEl.addEventListener("scroll",()=>{this.virtualScrollTop=Math.round(this.rosterScrollEl.scrollTop),this.virtualScrollLeft=Math.round(this.rosterScrollEl.scrollLeft)}),this.rosterTbodyEl.addEventListener("click",e=>{const t=e.target.closest("tr[data-player-id]");if(!t)return;const o=t.dataset.playerId;this.toggleSelection(o,e.shiftKey,!1)}),this.actionTbodyEl.addEventListener("click",e=>{const t=e.target.closest("tr[data-player-id]");if(!t)return;const o=t.dataset.playerId;this.toggleSelection(o,e.shiftKey,!0)}),this.stageSelectedBtn.addEventListener("click",()=>{const e=this.getStageTargets().map(t=>t.id);e.length>0&&this.bridge.stagePlayers(e)}),this.removeActionBtn.addEventListener("click",()=>{const e=Array.from(this.actionSelectedIds);e.length>0&&this.bridge.sendCommand({action:"unstage_people",player_ids:e})}),this.clearActionsBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"clear_actions"})}),this.stageByTagBtn.addEventListener("click",()=>{const e=this.stageTagSelectEl.value;e&&this.bridge.sendCommand({action:"stage_tag",label:e,scope:"shard",include_org_affiliate:!1})}),this.stageFriendsBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"stage_tag",label:"Friend",scope:"shard",include_org_affiliate:!1})}),this.stageOrgBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"stage_tag",label:"Org",scope:"shard",include_org_affiliate:!0})}),this.addPresetTagBtn.addEventListener("click",()=>{const e=this.getActionTargets(),t=this.applyTagSelectEl.value;e.length>0&&t&&this.bridge.sendCommand({action:"tag_many",player_ids:e.map(o=>o.id),label:t})}),this.applyTagsBtn.addEventListener("click",()=>{const e=this.getActionTargets();if(e.length===0)return;const t=this.tagDraftInputEl.value.trim();e.length===1?this.bridge.sendCommand({action:"tag",player_id:e[0].id,label:t,alert:this.joinAlertsCheckboxEl.checked}):this.bridge.sendCommand({action:"tag_many",player_ids:e.map(o=>o.id),label:t})}),this.clearTagsBtn.addEventListener("click",()=>{const e=this.getActionTargets();e.length!==0&&(e.length===1?this.bridge.sendCommand({action:"tag",player_id:e[0].id,label:"",clear_tags:!0,alert:this.joinAlertsCheckboxEl.checked}):this.bridge.sendCommand({action:"tag_many",player_ids:e.map(t=>t.id),label:"",clear_tags:!0}))}),this.sendFriendsBtn.addEventListener("click",()=>{const e=this.getActionTargets().filter(t=>!t.is_friend);if(e.length===0){this.footerStatusEl.textContent="Add eligible players to the Action list first.";return}this.openConfirmationModal("confirm_friend",e)}),this.invitePartyBtn.addEventListener("click",()=>{const e=this.getActionTargets().filter(t=>!t.in_party);if(e.length===0){this.footerStatusEl.textContent="Add eligible players to the Action list first.";return}this.openConfirmationModal("confirm_party",e)}),this.viewQueueBtn.addEventListener("click",()=>{this.openQueueReportModal()}),this.pauseQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:e.paused?"resume_invites":"pause_invites",queue_id:e.id})}),this.cancelQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:"cancel_invites",queue_id:e.id})}),this.modalCancelBtn.addEventListener("click",()=>{this.closeModal()}),this.modalConfirmBtn.addEventListener("click",()=>{if(this.modalMode==="queue_report"){this.closeModal();return}const e=this.modalRecipients.map(n=>n.id).slice(0,y),t=this.modalResendCheckboxEl.checked,o=this.modalMode==="confirm_friend"?"friend_many":"party_many";this.closeModal(),e.length>0&&this.bridge.sendCommand({action:o,player_ids:e,from_actions:!0,confirmed:!0,resend:t})}),this.modalPauseBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:e.paused?"resume_invites":"pause_invites",queue_id:e.id})}),this.modalStopQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:"cancel_invites",queue_id:e.id})}),this.marketSearchInputEl.addEventListener("input",()=>{this.marketSearch=this.marketSearchInputEl.value,this.renderMarketCatalog()}),this.root.querySelector("#market-find-btn").addEventListener("click",()=>{this.marketSearch=this.marketSearchInputEl.value,this.renderMarketCatalog()}),this.root.querySelector("#market-refresh-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_market"})}),this.root.querySelector("#market-refresh-now-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_market"})}),this.root.querySelector("#market-watch-btn").addEventListener("click",()=>{const e=Number(this.marketItemSelectEl.value),t=Number(this.marketQualityInputEl.value),o=this.marketPriceInputEl.value.trim(),n=o?Number(o):0;if(!e||Number.isNaN(t)||t<0||t>9999||Number.isNaN(n)){this.footerStatusEl.textContent="Choose an item and enter a whole-number quality and valid minimum price.";return}this.bridge.sendCommand({action:"add_watch",item_id:e,quality:Math.trunc(t),price:n,unit:this.marketUnitInputEl.value.trim()||"unit"})}),this.root.querySelector("#market-toggle-watch-btn").addEventListener("click",()=>{this.selectedWatchId&&this.bridge.sendCommand({action:"toggle_watch",watch_id:this.selectedWatchId})}),this.root.querySelector("#market-remove-watch-btn").addEventListener("click",()=>{this.selectedWatchId&&this.bridge.sendCommand({action:"remove_watch",watch_id:this.selectedWatchId})}),this.marketShowMatchesBtn.addEventListener("click",()=>{this.showMatches=!this.showMatches,this.renderMarket()}),this.root.querySelector("#market-dismiss-notices-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"dismiss_notices"})}),this.root.querySelector("#home-session-current").addEventListener("click",()=>{this.homeShowPrevious=!1,this.renderHome()}),this.root.querySelector("#home-session-prev").addEventListener("click",()=>{this.homeShowPrevious=!0,this.renderHome()})}setMode(e){this.activeMode=e,this.peopleSectionEl.hidden=e!=="people",this.marketSectionEl.hidden=e!=="buyer_alerts",this.homeSectionEl.hidden=e!=="home",this.settingsSectionEl.hidden=e!=="settings",this.root.querySelectorAll(".ss-tab").forEach(n=>{const i=n.dataset.mode===e;n.classList.toggle("is-active",i),n.setAttribute("aria-selected",i?"true":"false")});const t=this.root.querySelector("#ss-page-title"),o=this.root.querySelector("#ss-page-subtitle");e==="people"?(t.textContent="People",o.textContent="A familiar face in a very large universe."):e==="buyer_alerts"?(t.textContent="Buyer Alerts",o.textContent="Watch UEX buy orders for your best mining and crafting hauls."):e==="home"?(t.textContent="Home",o.textContent="Find your next upgrade. See what you've accomplished."):(t.textContent="Settings & Modules",o.textContent="Customize HUD behavior, shortcuts, privacy, and installed modules.")}onSnapshot(e){const t=e.mode&&e.mode!==this.activeMode;this.snapshot=e,t&&e.mode&&this.setMode(e.mode),this.renderPeople(),this.renderMarketCatalog(),this.renderMarket(),this.renderHome(),this.modalOpen&&this.modalMode==="queue_report"&&this.renderQueueReportRows()}getCandidates(e){if(this.sourceIndex===2){const t=e.tags??{};return Object.entries(t).map(([o,n])=>k({id:o,handle:n.handle??o,tag:n.label??"",alert:n.alert,is_org:n.is_org}))}if(this.sourceIndex===3)return e.friend_people??[];if(this.sourceIndex===1){const t=this.searchQuery.trim().toLowerCase(),o=(e.search_query??"").trim().toLowerCase();return t.length>0&&t===o?e.search??[]:[]}return e.players}renderPeople(){const e=this.snapshot;if(!e)return;this.searchInputEl.placeholder=this.sourceIndex===1?"Enter an RSI handle, then click Find player":"Filter this list by handle or tag";const t=this.searchQuery.trim().toLowerCase(),o=`${e.session}|${this.sourceIndex}|${t}|${this.taggedOnly?"1":"0"}`,n=o!==this.previousViewSignature;this.previousViewSignature=o;const i=this.getCandidates(e),s=[];for(const d of i){const p=`${d.handle} ${d.tag??d.tags.join(" ")}`.toLowerCase();t&&!p.includes(t)||this.taggedOnly&&(!d.tags||d.tags.length===0)&&!d.tag||s.push(d)}const r=Math.round(this.virtualScrollTop),g=Math.round(this.virtualScrollLeft),c=Math.max(0,Math.min(this.filteredPeople.length-1,Math.floor(r/w))),h=this.filteredPeople.length>0?r-c*w:0;let b="";if(!n&&this.filteredPeople.length>0){const d=new Set(s.map(p=>p.id));for(let p=c;p<this.filteredPeople.length;p++)if(d.has(this.filteredPeople[p].id)){b=this.filteredPeople[p].id;break}if(!b){for(let p=c-1;p>=0;p--)if(d.has(this.filteredPeople[p].id)){b=this.filteredPeople[p].id;break}}}if(n){const d=new Set(s.map(p=>p.id));for(const p of Array.from(this.selectedIds))d.has(p)||this.selectedIds.delete(p)}else{const d=new Set;for(const p of s)d.add(p.id);for(const p of e.players)d.add(p.id);for(const p of e.friend_people??[])d.add(p.id);for(const p of Array.from(this.selectedIds))d.has(p)||this.selectedIds.delete(p)}if(this.filteredPeople=s,this.reconcileTableRows(this.rosterTbodyEl,this.rosterRowMap,this.rosterRowSignature,this.filteredPeople,this.selectedIds),n)this.virtualScrollTop=0,this.rosterScrollEl.scrollTop=0;else if(b){const d=this.filteredPeople.findIndex(p=>p.id===b);d>=0&&(this.virtualScrollTop=Math.max(0,d*w+h),this.rosterScrollEl.scrollTop=this.virtualScrollTop),this.virtualScrollLeft=g,this.rosterScrollEl.scrollLeft=g}const m=(e.action_people??[]).slice(0,y),u=new Set(m.map(d=>d.id));for(const d of Array.from(this.actionSelectedIds))u.has(d)||this.actionSelectedIds.delete(d);this.actionPeople=m,this.reconcileTableRows(this.actionTbodyEl,this.actionRowMap,this.actionRowSignature,this.actionPeople,this.actionSelectedIds,!1),this.updateTagSelectOptions(e.tag_options??["Org","Friendly","Aggressive","Trader","Friend"]),this.updateStatusAndControls()}computeRowSignature(e,t){var s,r;const o=I(e).css,n=(s=e.requests)!=null&&s.friend?`${e.requests.friend.outcome}:${e.requests.friend.detail??""}`:"",i=(r=e.requests)!=null&&r.party?`${e.requests.party.outcome}:${e.requests.party.detail??""}`:"";return`${e.handle}|${e.tag??e.tags.join(",")}|${e.relationship??""}|${o}|${t?"1":"0"}|${e.alert?"1":"0"}|${n}|${i}`}reconcileTableRows(e,t,o,n,i,s=!0){s&&(this.lastUpdatedRowIds=[]);const r=new Set(n.map(c=>c.id));for(const[c,h]of Array.from(t.entries()))r.has(c)||(h.remove(),t.delete(c),o.delete(c),s&&(this.domRowRemovedCount+=1));let g=e.firstChild;for(let c=0;c<n.length;c++){const h=n[c],b=i.has(h.id),m=this.computeRowSignature(h,b);let u=t.get(h.id);u?o.get(h.id)!==m&&(this.populateRowElement(u,h,b),o.set(h.id,m),s&&(this.domRowUpdatedCount+=1,this.lastUpdatedRowIds.push(h.id))):(u=e.ownerDocument.createElement("tr"),u.className="ss-person-row",u.dataset.playerId=h.id,this.populateRowElement(u,h,b),t.set(h.id,u),o.set(h.id,m),s&&(this.domRowCreatedCount+=1,this.lastUpdatedRowIds.push(h.id))),u!==g?e.insertBefore(u,g):g=g.nextSibling}}populateRowElement(e,t,o){const n=I(t);e.classList.toggle("is-selected",o),e.setAttribute("aria-selected",o?"true":"false"),e.style.height=`${w}px`;const s=(t.tags&&t.tags.length>0?t.tags:Ae(t.tag)).map(c=>{const h=H(c),b=Math.trunc((14*4+h.r)/5),m=Math.trunc((18*4+h.g)/5),u=Math.trunc((25*4+h.b)/5);return`<span class="ss-tag-chip" data-tag="${this.escapeHtml(c)}" style="color:${h.css};background:rgb(${b},${m},${u});border-color:rgba(${h.r},${h.g},${h.b},0.49)">${this.escapeHtml(c)}</span>`}).join(""),r=[];if(t.requests)for(const[c,h]of Object.entries(t.requests)){if(!h)continue;const b=c==="friend"?"Friend":"Party",m=h.outcome??"",u=h.detail??"";let d="",p="ss-receipt-muted";m==="Sent"?(d=`✓ ${b} sent`,p="ss-receipt-ok"):u==="Already a friend"||u==="Already in party"?d=`${b}: already ${c==="friend"?"friends":"in party"}`:m==="Queued"||m==="Sending"?d=`… ${b} ${m}`:(d=`⚠ ${b}: ${u||m}`,p="ss-receipt-warn"),r.push(`<span class="ss-receipt ${p}">${this.escapeHtml(d)}</span>`)}const g=t.relationship??(t.is_self?"You":t.in_party&&t.is_friend?"Party + Friend":t.in_party?"Party":t.is_friend?"Friend":"—");e.innerHTML=`
      <td class="col-player">
        <div class="ss-player-cell">
          <span class="ss-row-check ${o?"is-checked":""}" aria-hidden="true">${o?"✓":""}</span>
          <span class="ss-person-badge" style="color:${n.css}" aria-hidden="true">●</span>
          <div class="ss-player-stack">
            <span class="ss-player-handle">${this.escapeHtml(t.handle)}</span>
            ${r.length>0?`<div class="ss-receipts-row">${r.join("")}</div>`:""}
          </div>
        </div>
      </td>
      <td class="col-tags"><div class="ss-tags-run">${s}</div></td>
      <td class="col-rel" style="color:${n.css}">${this.escapeHtml(g)}</td>
    `}toggleSelection(e,t,o){const n=o?this.actionPeople:this.filteredPeople,i=o?this.actionSelectedIds:this.selectedIds,s=o?this.actionSelectionAnchorId:this.selectionAnchorId;if(t&&s){const r=n.findIndex(c=>c.id===s),g=n.findIndex(c=>c.id===e);if(r>=0&&g>=0){const c=Math.min(r,g),h=Math.max(r,g);for(let b=c;b<=h;b++)i.add(n[b].id)}else i.has(e)?i.delete(e):i.add(e)}else i.has(e)?i.delete(e):i.add(e),o?this.actionSelectionAnchorId=e:this.selectionAnchorId=e;o?this.reconcileTableRows(this.actionTbodyEl,this.actionRowMap,this.actionRowSignature,this.actionPeople,this.actionSelectedIds,!1):this.reconcileTableRows(this.rosterTbodyEl,this.rosterRowMap,this.rosterRowSignature,this.filteredPeople,this.selectedIds),this.updateStatusAndControls()}getChosenRosterPlayers(){return this.filteredPeople.filter(e=>this.selectedIds.has(e.id)&&!e.is_self)}getStageTargets(){return this.getChosenRosterPlayers().filter(e=>e.on_shard!==!1||!!e.is_friend)}getActionTargets(){return this.actionPeople.filter(e=>!e.is_self)}updateTagSelectOptions(e){const t=this.stageTagSelectEl.value,o=this.applyTagSelectEl.value,n=e.map(r=>`<option value="${this.escapeHtml(r)}">${this.escapeHtml(r)}</option>`).join("");this.stageTagSelectEl.innerHTML!==n&&(this.stageTagSelectEl.innerHTML=n,e.includes(t)&&(this.stageTagSelectEl.value=t));const i=e.filter(r=>r!=="Friend"),s=i.map(r=>`<option value="${this.escapeHtml(r)}">${this.escapeHtml(r)}</option>`).join("");this.applyTagSelectEl.innerHTML!==s&&(this.applyTagSelectEl.innerHTML=s,i.includes(o)&&(this.applyTagSelectEl.value=o))}updateStatusAndControls(){const e=this.snapshot;if(!e)return;const t=this.getActionTargets(),o=t.map(v=>v.id).join(","),i=this.root.ownerDocument.activeElement===this.tagDraftInputEl;if(o!==this.actionEditorSignature&&!i)if(this.actionEditorSignature=o,t.length===1){const v=t[0];this.tagDraftInputEl.value=v.manual_tag??v.tag??v.tags.join(", "),this.joinAlertsCheckboxEl.checked=!!v.alert}else this.tagDraftInputEl.value="",this.joinAlertsCheckboxEl.checked=!1;const s=!!(e.session&&e.session.length>0),r=!!e.social_busy,g=Math.min(y,e.action_limit??y),c=this.actionPeople.length<g,h=this.getStageTargets();this.stageSelectedBtn.disabled=!s||r||!c||h.length===0,this.removeActionBtn.disabled=!s||r||this.actionSelectedIds.size===0,this.clearActionsBtn.disabled=!s||r||this.actionPeople.length===0,this.stageByTagBtn.disabled=!s||r||!c,this.stageOrgBtn.disabled=!s||r||!c,this.stageFriendsBtn.disabled=!s||r||!c||!e.friends_known;const b=s&&!r&&t.length>0;this.applyTagsBtn.disabled=!b,this.clearTagsBtn.disabled=!b,this.addPresetTagBtn.disabled=!b,this.joinAlertsCheckboxEl.disabled=!b||t.length!==1,this.sendFriendsBtn.disabled=!b,this.invitePartyBtn.disabled=!b,this.actionHeaderEl.textContent=`Action list · ${this.actionPeople.length} / ${g}${r?" · queue running":""}`,this.selectionSummaryEl.textContent=`${this.selectedIds.size} selected · ${h.length} eligible`;let m=s?`${e.players.length} reported shard members`:"Waiting for current shard";if(this.sourceIndex===1){const v=this.searchQuery.trim();m=v?e.search_busy?"Searching handles…":`${this.filteredPeople.length} result(s) for “${e.search_query??v}”`:"Enter a handle, then click Find player."}else this.sourceIndex===3&&(m=e.friends_known?`${(e.friend_people??[]).length} friends`:"Friends list is loading or unavailable · Refresh shard to retry");e.roster_loading&&this.sourceIndex===0&&(m+=" · refreshing"),e.roster_error&&this.sourceIndex!==1&&(m+=` · ${e.roster_error}`),this.rosterStatusEl.textContent=m;const u=e.invite_queue,d=!!(u&&u.active&&!u.cancelling);this.viewQueueBtn.disabled=!(e.batch_results&&e.batch_results.length>0)&&!(u!=null&&u.id),this.pauseQueueBtn.disabled=!d,this.cancelQueueBtn.disabled=!d,this.pauseQueueBtn.textContent=u!=null&&u.paused?"Resume":"Pause",this.queueStatusEl.textContent=this.formatQueueSummary(u);let p=e.status??"Ready";p+=" · Tagged-player alerts report list appearances; the first snapshot stays quiet.",(e.friends_known===!1||e.party_known===!1)&&(p+=" · Friend / party status is checking or unavailable; unconfirmed rows stay neutral."),this.footerStatusEl.textContent=p}formatQueueSummary(e){if(!e||!e.id)return"Party invitations: idle · 0.09–0.99s paced gap";let o=`${e.operation==="friend"?"Friends: ":"Party: "}${e.state} · ${e.sent} sent · ${e.skipped} skipped · ${e.remaining} remaining`;return e.active&&!e.paused&&typeof e.next_in_seconds=="number"&&e.next_in_seconds>0&&(o+=` · next in ${Math.trunc(e.next_in_seconds)}s`),e.current_handle&&(o+=` · ${e.current_handle}`),o}openConfirmationModal(e,t){this.modalOpen=!0,this.modalMode=e,this.modalRecipients=t.slice(0,y),this.modalResend=!1,this.modalResendCheckboxEl.checked=!1,this.modalResendWrapEl.hidden=!1,this.modalConfirmBtn.hidden=!1,this.modalPauseBtn.hidden=!0,this.modalStopQueueBtn.hidden=!0,this.modalCancelBtn.textContent="Cancel";const o=e==="confirm_friend";this.modalTitleEl.textContent=o?"Confirm friend requests":"Confirm party invitations",this.modalSummaryEl.textContent=`${o?"Send friend requests to":"Invite"} ${this.modalRecipients.length} player(s)? Random 0.09–0.99s gap; current-shard membership is rechecked.`,this.modalTbodyEl.innerHTML=this.modalRecipients.map(n=>{const i=o?n.friend_requested_before:n.invited_before,s=i?"Previous attempt":o?"Add friend":"Invite",r=i?"Skipped unless repeat requests are explicitly enabled below; the previous attempt may be unconfirmed.":n.relationship??"Ready";return`
          <tr data-recipient-id="${this.escapeHtml(n.id)}">
            <td>${this.escapeHtml(n.handle)}</td>
            <td>${this.escapeHtml(s)}</td>
            <td>${this.escapeHtml(r)}</td>
          </tr>
        `}).join(""),this.modalBackdropEl.hidden=!1,this.modalCancelBtn.focus()}openQueueReportModal(){this.modalOpen=!0,this.modalMode="queue_report",this.modalResendWrapEl.hidden=!0,this.modalConfirmBtn.hidden=!0,this.modalPauseBtn.hidden=!1,this.modalStopQueueBtn.hidden=!1,this.modalCancelBtn.textContent="Close",this.modalTitleEl.textContent="Social action queue",this.renderQueueReportRows(),this.modalBackdropEl.hidden=!1,this.modalCancelBtn.focus()}renderQueueReportRows(){const e=this.snapshot,t=e==null?void 0:e.invite_queue;this.modalSummaryEl.textContent=this.formatQueueSummary(t);const o=!!(t&&t.active&&!t.cancelling);this.modalPauseBtn.disabled=!o,this.modalStopQueueBtn.disabled=!o,this.modalPauseBtn.textContent=t!=null&&t.paused?"Resume":"Pause";const n=(t==null?void 0:t.results)??(e==null?void 0:e.batch_results)??[];this.modalTbodyEl.innerHTML=n.map(i=>`
        <tr data-recipient-id="${this.escapeHtml(i.id)}">
          <td>${this.escapeHtml(i.handle)}</td>
          <td>${this.escapeHtml(i.outcome)}</td>
          <td>${this.escapeHtml(i.detail??"")}</td>
        </tr>
      `).join("")}closeModal(){this.modalOpen=!1,this.modalBackdropEl.hidden=!0}renderMarketCatalog(){var i;const e=((i=this.snapshot)==null?void 0:i.market_items)??[],t=this.marketSearch.trim().toLowerCase(),o=e.filter(s=>!t||s.name.toLowerCase().includes(t)).sort((s,r)=>s.name.localeCompare(r.name)).slice(0,500),n=o.map(s=>`<option value="${s.id}">${this.escapeHtml(s.name)}</option>`).join("");this.marketItemSelectEl.innerHTML!==n&&(this.marketItemSelectEl.innerHTML=n,this.selectedMarketItemId&&o.some(s=>s.id===this.selectedMarketItemId)&&(this.marketItemSelectEl.value=String(this.selectedMarketItemId)))}renderMarket(){const e=this.snapshot;if(!e)return;const t=e.watches??[];!this.selectedWatchId&&t.length>0&&(this.selectedWatchId=t[0].id);const o=new Set(t.map(i=>i.id));for(const[i,s]of Array.from(this.watchRowMap.entries()))o.has(i)||(s.remove(),this.watchRowMap.delete(i));for(const i of t){let s=this.watchRowMap.get(i.id);s||(s=this.marketWatchesTbodyEl.ownerDocument.createElement("tr"),s.dataset.watchId=i.id,s.addEventListener("click",()=>{this.selectedWatchId=i.id,this.renderMarket()}),this.watchRowMap.set(i.id,s),this.marketWatchesTbodyEl.appendChild(s)),s.classList.toggle("is-selected",i.id===this.selectedWatchId);const r=i.quality?`Q${i.quality}`:"Any",g=i.minimum_price?`${i.minimum_price} / ${i.unit??"unit"}`:"Any price",c=(i.matches??[]).length,h=i.enabled?i.error?"Refresh unavailable":"Checked":"Paused";s.innerHTML=`
        <td>${this.escapeHtml(i.name)}</td>
        <td>${this.escapeHtml(r)}</td>
        <td>${this.escapeHtml(g)}</td>
        <td>${c}</td>
        <td>${this.escapeHtml(h)}</td>
      `}this.marketNoticesHeadingEl.textContent=this.showMatches?"Current matching buy requests — select one to open its UEX advertisement":"Recent HUD notices — buyer matches and tagged-player appearances",this.marketShowMatchesBtn.textContent=this.showMatches?"Show notices":"Show matches";let n=e.notifications??[];if(this.showMatches){const i=t.find(s=>s.id===this.selectedWatchId);n=((i==null?void 0:i.matches)??[]).map(s=>({title:"BUY REQUEST",detail:`${s.price} UEC / ${s.unit} · ${s.location}`,at:s.renewed??0,url:s.url}))}this.marketNoticesTbodyEl.innerHTML=n.map(i=>`
        <tr>
          <td>${this.escapeHtml(`${i.title} · ${i.detail}`)}</td>
          <td>${i.at?"Recent":"—"}</td>
        </tr>
      `).join("")}renderHome(){var b;const e=(b=this.snapshot)==null?void 0:b.home,t=this.homeShowPrevious?e==null?void 0:e.previous:e==null?void 0:e.current,o=(t==null?void 0:t.blueprints)??[],n=(t==null?void 0:t.reputation)??[],i=(t==null?void 0:t.contracts_completed)??0;this.root.querySelector("#home-session-current").classList.toggle("is-active",!this.homeShowPrevious),this.root.querySelector("#home-session-prev").classList.toggle("is-active",this.homeShowPrevious);const s=this.root.querySelector("#home-metrics-row");s.innerHTML=`
      <div class="ss-metric-card">
        <span class="ss-metric-value">${o.length}</span>
        <span class="ss-metric-label">Blueprints received</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${i}</span>
        <span class="ss-metric-label">Contracts completed</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${n.length}</span>
        <span class="ss-metric-label">Reputation changes</span>
      </div>
    `;const r=this.root.querySelector("#home-blueprints-list");r.innerHTML=o.length===0?'<li class="ss-muted-text">No blueprint grants recorded in this session.</li>':o.map(m=>`<li>${this.escapeHtml(m.name)}</li>`).join("");const g=this.root.querySelector("#home-rep-list");g.innerHTML=n.length===0?'<li class="ss-muted-text">No balance changes between the saved reads.</li>':n.map(m=>`<li><strong>${this.escapeHtml(m.faction)}</strong> <span class="ss-accent-text">${m.delta>0?`+${m.delta}`:m.delta}</span></li>`).join("");const c=e==null?void 0:e.synthstrings,h=this.root.querySelector("#home-patch-banner");c!=null&&c.title?h.innerHTML=`
        <strong>${this.escapeHtml(c.patch_label??"Star Citizen")}</strong>
        <span>${this.escapeHtml(c.status_label??"Game text unchanged — No action needed")} · ${this.escapeHtml(c.summary??"")}</span>
      `:h.innerHTML=`
        <strong>${this.escapeHtml((e==null?void 0:e.identity)||"No live shard observation")}</strong>
        <span>Game text unchanged — No action needed</span>
      `}escapeHtml(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}}async function xe(l){const e=[],t=(f,S)=>(S||e.push(f),S),n=(f=>{const S=[];for(let _=0;_<f;_++){const we=`pilot-${String(_).padStart(3,"0")}`,Ee=`Pilot_${String(_).padStart(3,"0")}`;S.push({id:we,handle:Ee,tags:_%5===0?["Org","Friendly"]:["Friendly"],tag:_%5===0?"Org, Friendly":"Friendly",is_org:_%5===0,is_self:_===0,in_party:_===1,is_friend:_===2,on_shard:!0,relationship:_===0?"You":_===1?"Party":_===2?"Friend":"Shard"})}return S})(500),i=new K({revision:1,session:"synthetic-500-session",players:n,action_people:[n[1],n[2]],friends_known:!0,party_known:!0,status:"Synthetic 500-player regression fixture"}),s=new te(l,i),r=s.domRowCreatedCount;t("initial_500_rows_created",r===500);const g=I({is_self:!0,in_party:!0,is_friend:!0}),c=I({is_self:!1,in_party:!0,is_friend:!0}),h=I({is_self:!1,in_party:!1,is_friend:!0}),b=t("self_purple_party_blue_friend_green_priority",g.css===J.css&&c.css===Z.css&&h.css===ee.css),m=t("friend_and_friendly_distinct_green",H("Friend").css!==H("Friendly").css),u=(f,S=!1)=>{if(!f)return;const _=new MouseEvent("click",{bubbles:!0,cancelable:!0,shiftKey:S});f.dispatchEvent(_)};u(s.getRosterRowElement("pilot-142")),u(s.getRosterRowElement("pilot-145"));let d=s.getSelectedIds().length===2&&s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-145");u(s.getRosterRowElement("pilot-142")),d=d&&s.getSelectedIds().length===1&&s.getSelectedIds()[0]==="pilot-145",u(s.getRosterRowElement("pilot-142")),u(s.getActionRowElement("pilot-001")),u(s.getActionRowElement("pilot-002")),d=d&&s.getActionSelectedIds().length===2,u(s.getActionRowElement("pilot-001")),d=d&&s.getActionSelectedIds().length===1&&s.getActionSelectedIds()[0]==="pilot-002",u(s.getActionRowElement("pilot-002")),d=d&&s.getActionSelectedIds().length===0,t("plain_click_toggles_in_both_lists",d),u(s.getRosterRowElement("pilot-144"),!0);const p=t("shift_range_selection_works",s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-143")&&s.getSelectedIds().includes("pilot-144")&&s.getSelectedIds().includes("pilot-145")),E=140*w+12;s.setRosterScroll(E,24);const se=s.getScrollAnchor(),T=l.querySelector("#tag-draft-input");T.value="Scout, Unsaved draft";const O=s.domRowCreatedCount,ie=s.domRowUpdatedCount;for(let f=0;f<3;f++)i.publish({written_at:Date.now()/1e3,status:`Heartbeat ${f}`});const F=s.domRowCreatedCount-O,oe=s.domRowUpdatedCount-ie,A=s.getScrollAnchor(),ne=t("heartbeat_keeps_scroll",F===0&&oe===0&&A.anchorId==="pilot-140"&&A.offsetWithinRow===12&&A.scrollTop===se.scrollTop),U=i.getSnapshot().players.map(f=>f.id==="pilot-142"?{...f,is_friend:!0,relationship:"Friend"}:f);i.publish({players:U});const ae=t("single_row_update_on_relationship",s.lastUpdatedRowIds.length===1&&s.lastUpdatedRowIds[0]==="pilot-142"&&s.domRowCreatedCount===O),re=t("relationship_refresh_keeps_scroll",s.getScrollAnchor().anchorId==="pilot-140"&&s.getScrollAnchor().offsetWithinRow===12),Q=[];for(let f=0;f<5;f++)Q.push({id:`new-joiner-${f}`,handle:`A_NewJoiner_${f}`,tags:[],on_shard:!0});const N=[...Q,...U];i.publish({players:N});const x=s.getScrollAnchor(),le=t("membership_insert_keeps_anchor_and_selection",x.anchorId==="pilot-140"&&x.offsetWithinRow===12&&x.scrollTop===145*w+12&&s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-145")),ce=t("unsaved_tags_preserved",T.value==="Scout, Unsaved draft"),j=N.filter(f=>f.id!=="pilot-140");i.publish({players:j});const W=s.getScrollAnchor(),de=t("removed_anchor_keeps_neighbour",W.anchorId==="pilot-141"&&W.offsetWithinRow===12);await i.sendCommand({action:"tag_many",player_ids:["pilot-142","pilot-145"],label:"Trader, Crew"});const he=t("tag_reconciliation_updates_only_affected_rows",s.lastUpdatedRowIds.length===2&&s.lastUpdatedRowIds.includes("pilot-142")&&s.lastUpdatedRowIds.includes("pilot-145")),ue=j.slice(10,80).map(f=>f.id);await i.stagePlayers(ue);const pe=t("action_list_cap_enforced",s.getActionPeople().length===y),D=l.querySelector("#people-search-input");D.value="nonexistent_handle_xyz",D.dispatchEvent(new Event("input",{bubbles:!0}));const me=t("filter_resets_intentionally",s.getFilteredPeople().length===0&&s.getScrollAnchor().scrollTop===0),ge=t("action_list_independent_of_roster_filter",s.getActionPeople().length===y);l.querySelector("#people-clear-btn").click();const be=i.commands.filter(f=>f.action==="party_many"||f.action==="friend_many").length,z=l.querySelector("#invite-party-btn");z.click();const V=s.isModalOpen(),fe=l.querySelector("#ss-modal-resend-checkbox"),G=l.querySelector("#ss-modal-cancel-btn"),ye=t("cancel_is_default_and_resend_default_off",V&&!fe.checked&&l.ownerDocument.activeElement===G);G.click();const ve=i.commands.filter(f=>f.action==="party_many"||f.action==="friend_many").length,_e=t("confirmation_modal_blocks_unconfirmed_requests",V&&!s.isModalOpen()&&be===0&&ve===0);z.click(),l.querySelector("#ss-modal-confirm-btn").click();const R=i.commands.filter(f=>f.action==="party_many"),Se=t("confirmed_request_sends_bounded_batch",R.length===1&&R[0].confirmed===!0&&R[0].resend===!1&&Array.isArray(R[0].player_ids)&&R[0].player_ids.length<=y);let B=!1;try{await i.sendCommand({action:"party_many",player_ids:["pilot-142"],confirmed:!1})}catch{B=!0}t("unconfirmed_bridge_call_rejected",B),s.setRosterScroll(3200,0),T.value="Resize draft preserved";let q=!0;for(const[f,S]of[[860,700],[1240,840],[1600,1e3]])l.style.width=`${f}px`,l.style.height=`${S}px`,window.dispatchEvent(new Event("resize")),q=q&&T.value==="Resize draft preserved"&&s.getActionPeople().length===y&&s.getScrollAnchor().scrollTop===3200;return t("resize_preserves_state_and_fits",q),s.destroy(),{passed:e.length===0,roster_size:500,initial_created_rows:r,heartbeat_recreated_rows:F,heartbeat_keeps_scroll:ne,relationship_refresh_keeps_scroll:re,single_row_update_on_relationship:ae,membership_insert_keeps_anchor_and_selection:le,removed_anchor_keeps_neighbour:de,filter_resets_intentionally:me,unsaved_tags_preserved:ce,plain_click_toggles_in_both_lists:d,shift_range_selection_works:p,action_list_cap_enforced:pe,action_list_independent_of_roster_filter:ge,tag_reconciliation_updates_only_affected_rows:he,self_purple_party_blue_friend_green_priority:b,friend_and_friendly_distinct_green:m,confirmation_modal_blocks_unconfirmed_requests:_e,cancel_is_default_and_resend_default_off:ye,confirmed_request_sends_bounded_batch:Se,resize_preserves_state_and_fits:q,unconfirmed_bridge_call_rejected:B,outgoing_live_requests_sent:0,failures:e}}const P=document.querySelector("#app");var Y;if(P)if(new URLSearchParams(typeof location<"u"?location.search:"").get("suite")==="roster500")xe(P).then(e=>{var t,o;(o=(t=window.chrome)==null?void 0:t.webview)==null||o.postMessage({kind:"suite_result",result:e})});else{const t=typeof window<"u"&&!!((Y=window.chrome)!=null&&Y.webview)?new Ie:new K({revision:1,session:"standalone-preview-session",players:[{id:"self-pilot",handle:"YourPilot",tags:["Org"],is_self:!0,is_org:!0,in_party:!0,is_friend:!0,on_shard:!0,relationship:"You"},{id:"party-pilot",handle:"Cassiopeia",tags:["Crew","Friendly"],in_party:!0,is_friend:!0,on_shard:!0,relationship:"Party + Friend"},{id:"friend-pilot",handle:"NovaDrift",tags:["Trader","Friend"],is_friend:!0,on_shard:!0,relationship:"Friend",requests:{friend:{outcome:"Sent",detail:"Friend request receipt returned"}}},{id:"org-pilot",handle:"OrionAtlas",tags:["Org Affiliate"],is_org:!0,on_shard:!0,relationship:"Org"}],action_people:[],friends_known:!0,party_known:!0,status:"Standalone preview — no live game connection"}),o=new te(P,t);window.__synthscanDesktop={controller:o,bridge:t}}
