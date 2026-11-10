var ke=Object.defineProperty;var Ce=(d,e,t)=>e in d?ke(d,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):d[e]=t;var r=(d,e,t)=>Ce(d,typeof e!="symbol"?e+"":e,t);(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const n of document.querySelectorAll('link[rel="modulepreload"]'))i(n);new MutationObserver(n=>{for(const a of n)if(a.type==="childList")for(const s of a.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&i(s)}).observe(document,{childList:!0,subtree:!0});function t(n){const a={};return n.integrity&&(a.integrity=n.integrity),n.referrerPolicy&&(a.referrerPolicy=n.referrerPolicy),n.crossOrigin==="use-credentials"?a.credentials="include":n.crossOrigin==="anonymous"?a.credentials="omit":a.credentials="same-origin",a}function i(n){if(n.ep)return;n.ep=!0;const a=t(n);fetch(n.href,a)}})();const _=50,$e=new Set(["friend","friend_many","party","party_many"]);function se(d){if($e.has(d.action)){if(d.confirmed!==!0)throw new Error(`Unconfirmed outgoing social action rejected: ${d.action}`);if(d.action==="friend_many"||d.action==="party_many"){if(!Array.isArray(d.player_ids)||d.player_ids.length===0)throw new Error("Batch social action requires at least one recipient");if(d.player_ids.length>_)throw new Error(`Batch social action exceeds cap of ${_}`)}}if(d.action==="stage_people"&&Array.isArray(d.player_ids)&&d.player_ids.length>_)throw new Error(`Cannot stage more than ${_} players at once`);if(d.action==="open_uex_ad"){const e=d.url??"";if(!e.startsWith("https://uexcorp.space/marketplace/item/info/")||/[\r\n\t ]/.test(e))throw new Error("Invalid UEX advertisement URL")}}function T(d){const e=typeof d.tag=="string"?d.tag:Array.isArray(d.tags)?d.tags.join(", "):"",t=Array.isArray(d.tags)?d.tags:e.split(",").map(i=>i.trim()).filter(i=>i.length>0);return{...d,id:String(d.id),handle:String(d.handle??d.id),tags:t,tag:e}}function F(d){const t=(d.players??d.rows??[]).map(o=>T(o)),i=(d.action_people??[]).map(o=>T(o)),n=(d.friend_people??[]).map(o=>T(o)),a=(d.search??[]).map(o=>T(o)),s=d.session??d.session_token??"";return{...d,revision:typeof d.revision=="number"?d.revision:Date.now(),session:s,session_token:s,players:t,rows:t,action_people:i,friend_people:n,search:a,tag_options:d.tag_options??["Org","Friendly","Aggressive","Trader","Friend"],action_limit:typeof d.action_limit=="number"?d.action_limit:_}}class ie{constructor(e){r(this,"listeners",new Set);r(this,"snapshot");r(this,"commands",[]);this.snapshot=F(e??{revision:1,session:"synthetic-session",players:[],action_people:[],friends_known:!0,party_known:!0,roster_at:Date.now()/1e3-5,status:"Ready"})}getSnapshot(){return this.snapshot}publish(e){this.snapshot=F({...this.snapshot,...e,revision:(this.snapshot.revision??0)+1});for(const t of this.listeners)t(this.snapshot)}subscribePeople(e){return this.listeners.add(e),e(this.snapshot),()=>{this.listeners.delete(e)}}async stagePlayers(e){await this.sendCommand({action:"stage_people",player_ids:e.slice(0,_)})}async sendCommand(e){se(e),this.commands.push(structuredClone(e));const t=Math.min(_,this.snapshot.action_limit??_),i=new Map;for(const n of[this.snapshot.players,this.snapshot.friend_people??[],this.snapshot.search??[],this.snapshot.action_people??[]])for(const a of n)i.set(a.id,a);if(e.action==="stage_people"&&Array.isArray(e.player_ids)){const n=[...this.snapshot.action_people??[]],a=new Set(n.map(s=>s.id));for(const s of e.player_ids){if(n.length>=t)break;if(a.has(s))continue;const o=i.get(s);o&&!o.is_self&&(o.on_shard!==!1||o.is_friend)&&(n.push(o),a.add(s))}this.publish({action_people:n})}else if(e.action==="unstage_people"&&Array.isArray(e.player_ids)){const n=new Set(e.player_ids),a=(this.snapshot.action_people??[]).filter(s=>!n.has(s.id));this.publish({action_people:a})}else if(e.action==="clear_actions")this.publish({action_people:[]});else if(e.action==="stage_tag"&&e.label){const n=[...this.snapshot.action_people??[]],a=new Set(n.map(o=>o.id)),s=e.label.trim().toLowerCase();for(const o of this.snapshot.players){if(n.length>=t)break;if(o.is_self||a.has(o.id))continue;const l=o.tags.map(c=>c.toLowerCase());(s==="org"&&(o.is_org||l.includes("org")||e.include_org_affiliate&&l.includes("org affiliate"))||s==="friend"&&(o.is_friend||l.includes("friend"))||l.includes(s))&&(n.push(o),a.add(o.id))}this.publish({action_people:n})}else e.action==="tag"&&e.player_id?this.applyTagUpdate([e.player_id],e.label??"",!!e.clear_tags,e.alert):e.action==="tag_many"&&Array.isArray(e.player_ids)&&this.applyTagUpdate(e.player_ids,e.label??"",!!e.clear_tags)}applyTagUpdate(e,t,i,n){const a=new Set(e),s=i?[]:t.split(",").map(l=>l.trim()).filter(l=>l.length>0),o=l=>l.map(h=>{if(!a.has(h.id))return h;const c=i?[]:Array.from(new Set([...s]));return T({...h,tags:c,tag:c.join(", "),manual_tag:c.join(", "),alert:typeof n=="boolean"?n:h.alert})});this.publish({players:o(this.snapshot.players),action_people:o(this.snapshot.action_people??[])})}}class Te{constructor(){r(this,"listeners",new Set);r(this,"snapshot",null);r(this,"bridgeToken","");r(this,"sequence",0);var t;const e=typeof window<"u"?(t=window.chrome)==null?void 0:t.webview:void 0;e&&(e.addEventListener("message",i=>{var s;const n=typeof i.data=="string"?JSON.parse(i.data):i.data;if(!n||typeof n!="object")return;const a=n;if(typeof a.bridge_token=="string"&&a.bridge_token.length>0&&(this.bridgeToken=a.bridge_token),a.kind==="snapshot"&&a.state&&typeof a.state=="object"){const o=a.state;this.snapshot=F({...o,mode:a.mode??o.mode??"people",market_items:a.market_items??o.market_items,home:a.home??o.home,catalog:a.catalog??((s=this.snapshot)==null?void 0:s.catalog)??o.catalog,desktop:a.desktop??o.desktop});for(const l of this.listeners)l(this.snapshot)}}),e.postMessage({kind:"ui_ready",at:Date.now()/1e3}))}subscribePeople(e){return this.listeners.add(e),this.snapshot&&e(this.snapshot),()=>{this.listeners.delete(e)}}async stagePlayers(e){await this.sendCommand({action:"stage_people",player_ids:e.slice(0,_)})}async sendCommand(e){var i;se(e);const t=typeof window<"u"?(i=window.chrome)==null?void 0:i.webview:void 0;if(!t)throw new Error("WebView2 host channel is not available");this.sequence+=1,t.postMessage({kind:"command",bridge_token:this.bridgeToken,client_seq:this.sequence,at:Date.now()/1e3,command:e})}}function A(d,e,t){return{r:d,g:e,b:t,css:`rgb(${d}, ${e}, ${t})`}}const ae=A(193,157,255),ne=A(116,183,255),oe=A(121,225,158),Ae=A(234,240,247);function R(d){return d.is_self?ae:d.in_party?ne:d.is_friend?oe:Ae}const Me={org:[255,145,40],friend:[45,225,122],friendly:[166,231,190],aggressive:[255,105,112],trader:[75,207,232],"org affiliate":[231,204,80],crew:[184,150,255],buyer:[106,163,255],avoid:[237,125,207]},Q=new Map,j=new Set;for(const[d,[e,t,i]]of Object.entries(Me))Q.set(d,A(e,t,i)),j.add(e<<16|t<<8|i);function V(d){const e=d.trim().toLowerCase(),t=Q.get(e);if(t)return t;let i=2166136261;for(let h=0;h<e.length;h++)i^=e.charCodeAt(h),i=Math.imul(i,16777619)>>>0;let n=0,a=0,s=0,o=0;do{const h=i%3600/600,c=.5+(i>>>12)%25/100,g=.9+(i>>>20)%10/100,b=g*c,m=b*(1-Math.abs(h%2-1)),p=g-b;let u=0,v=0,S=0;h<1?(u=b,v=m):h<2?(u=m,v=b):h<3?(v=b,S=m):h<4?(v=m,S=b):h<5?(u=m,S=b):(u=b,S=m),n=Math.trunc((u+p)*255),a=Math.trunc((v+p)*255),s=Math.trunc((S+p)*255),o=n<<16|a<<8|s,i=i+2654435769>>>0}while(j.has(o));j.add(o);const l=A(n,a,s);return Q.set(e,l),l}function Re(d){return d?d.split(",").map(e=>e.trim()).filter(e=>e.length>0):[]}const Ie=1577836800,xe=2*Math.PI;function Le(d,e){const t=Math.sqrt(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]+d[3]*d[3]);if(t<1e-8)return e;const i=d[0]/t,n=d[1]/t,a=d[2]/t,s=d[3]/t,[o,l,h]=e;return[(1-2*a*a-2*s*s)*o+(2*n*a-2*s*i)*l+(2*n*s+2*a*i)*h,(2*n*a+2*s*i)*o+(1-2*n*n-2*s*s)*l+(2*a*s-2*n*i)*h,(2*n*s-2*a*i)*o+(2*a*s+2*n*i)*l+(1-2*n*n-2*a*a)*h]}function qe(d,e,t){try{const i=d.center_km,n=d.star_km,a=[n[0]-i[0],n[1]-i[1],n[2]-i[2]],[s,o,l]=Le(d.quaternion,a),h=Math.sqrt(s*s+o*o+l*l),c=Math.asin(d.star_radius_km/Math.max(h,d.star_radius_km+1)),g=Math.atan2(o,s)-Math.PI/2-d.correction_degrees*Math.PI/180,b=Math.atan2(l,Math.hypot(s,o)),[m,p,u]=e.coordinates,v=Math.sqrt(m*m+p*p+u*u),S=Math.atan2(u,Math.hypot(m,p)),C=Math.atan2(p,m),f=v>d.radius_km?Math.acos(Math.min(1,d.radius_km/v)):0,I=-Math.min(Math.PI/2,c+f),O=Math.sin(S)*Math.sin(b),x=Math.cos(S)*Math.cos(b),L=Math.abs(d.period_seconds),$=L>0?-xe/d.period_seconds:0,H=$?g-C+$*((t-Ie)%L):g-C,q=Math.max(-1,Math.min(1,O+x*Math.cos(H))),P=Math.asin(q);return{daylight:P>=I,altitude_degrees:Math.round(P*180/Math.PI*10)/10}}catch{return{daylight:!0,altitude_degrees:45}}}class Pe{constructor(e,t,i,n){r(this,"bridge");r(this,"catalog",null);r(this,"desktopState",null);r(this,"currentActivePage","people");r(this,"onNavigateRequested");r(this,"sidebarEl");r(this,"captureBadgeEl");r(this,"viewsContainerEl");r(this,"directoryQuery","");r(this,"directoryKind","");r(this,"directorySelectedId","");r(this,"blueprintQuery","");r(this,"blueprintType","");r(this,"plannerQuery","");r(this,"plannerFamily","Ship");r(this,"plannerSystem","");r(this,"daylightSystem","Stanton");r(this,"daylightBodyName","");r(this,"daylightSiteName","");r(this,"tickTimer",null);this.bridge=e,this.sidebarEl=t,this.viewsContainerEl=i,this.onNavigateRequested=n,this.buildSidebar(),this.buildViewsContainers(),this.startTickLoop()}destroy(){this.tickTimer!==null&&(clearInterval(this.tickTimer),this.tickTimer=null)}updateState(e){e.catalog&&(this.catalog=e.catalog),e.desktop&&(this.desktopState=e.desktop),this.renderCaptureBadge(),this.renderActiveView()}setActivePage(e){this.currentActivePage=e,this.sidebarEl.querySelectorAll(".ss-nav-btn[data-page]").forEach(i=>{const n=i.dataset.page===e;i.classList.toggle("is-active",n),i.setAttribute("aria-selected",n?"true":"false")});const t=["home","directory","people","mission_log","servers","blueprints","planner","diary","refinery","executive_hangar","hud_piracy","daylight","acceptance","settings"];for(const i of t){const n=this.viewsContainerEl.querySelector(`#ss-view-${i.replace(/_/g,"-")}`);n&&(n.hidden=i!==e)}this.renderActiveView()}buildSidebar(){const e=[{id:"home",label:"Home",icon:"M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"},{id:"directory",label:"Item & Ship Finder",icon:"M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"},{id:"people",label:"People",icon:"M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"},{id:"mission_log",label:"Mission & Wallet Log",icon:"M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"},{id:"servers",label:"Server History",icon:"M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"},{id:"blueprints",label:"Blueprint Library",icon:"M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"},{id:"planner",label:"Mining Planner",icon:"M13 10V3L4 14h7v7l9-11h-7z"},{id:"diary",label:"Mining Diary",icon:"M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"},{id:"refinery",label:"Refinery",icon:"M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"},{id:"executive_hangar",label:"Executive Hangar",icon:"M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z"},{id:"hud_piracy",label:"Piracy",icon:"M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"},{id:"daylight",label:"Day/Night Forecast",icon:"M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"},{id:"acceptance",label:"Automatic Acceptance",icon:"M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"},{id:"settings",label:"Settings",icon:"M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"}];let t="";for(const n of e)t+=`
        <button type="button" class="ss-nav-btn ${n.id==="people"?"is-active":""}" data-page="${n.id}" role="tab" aria-selected="${n.id==="people"}">
          <svg class="ss-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="${n.icon}"></path>
          </svg>
          <span class="ss-nav-label">${n.label}</span>
        </button>
      `;this.sidebarEl.innerHTML=`
      <div class="ss-sidebar-brand">
        <span class="ss-brand-badge" aria-hidden="true">◆</span>
        <div class="ss-brand-text">
          <span class="ss-brand-title">SynthScan</span>
          <span class="ss-brand-subtitle">YOUR VERSE, CONNECTED</span>
        </div>
      </div>
      <nav class="ss-sidebar-nav" role="tablist" aria-label="Desktop Navigation">
        ${t}
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
    `,this.captureBadgeEl=this.sidebarEl.querySelector("#ss-capture-badge"),this.sidebarEl.querySelectorAll(".ss-nav-btn[data-page]").forEach(n=>{n.addEventListener("click",()=>{const a=n.dataset.page;a&&(this.onNavigateRequested&&this.onNavigateRequested(a),this.bridge.sendCommand({action:"navigate",target:a}))})});const i=this.sidebarEl.querySelector("#ss-sidebar-exit-btn");i&&i.addEventListener("click",()=>{this.bridge.sendCommand({action:"open_dialog",target:"exit"})})}buildViewsContainers(){const e=[{id:"ss-view-directory",title:"Item & Ship Finder"},{id:"ss-view-mission-log",title:"Mission & Wallet Log"},{id:"ss-view-servers",title:"Server History"},{id:"ss-view-blueprints",title:"Blueprint Library"},{id:"ss-view-planner",title:"Mining Planner"},{id:"ss-view-diary",title:"Mining Diary"},{id:"ss-view-refinery",title:"Refinery"},{id:"ss-view-executive-hangar",title:"Executive Hangar"},{id:"ss-view-hud-piracy",title:"Piracy"},{id:"ss-view-daylight",title:"Day/Night Forecast"},{id:"ss-view-acceptance",title:"Automatic Acceptance"}];for(const t of e)if(!this.viewsContainerEl.querySelector(`#${t.id}`)){const i=document.createElement("section");i.id=t.id,i.className="ss-view",i.hidden=!0,this.viewsContainerEl.appendChild(i)}}startTickLoop(){this.tickTimer=window.setInterval(()=>{(this.currentActivePage==="refinery"||this.currentActivePage==="hud_piracy"||this.currentActivePage==="executive_hangar"||this.currentActivePage==="daylight")&&this.renderActiveView()},1e3)}renderCaptureBadge(){var n;if(!this.captureBadgeEl)return;const e=((n=this.desktopState)==null?void 0:n.capture_status)??"reading",t=this.captureBadgeEl.querySelector(".ss-capture-indicator-dot"),i=this.captureBadgeEl.querySelector(".ss-capture-status-text");t&&i&&(e==="paused"?(t.style.background="#ffb05a",i.textContent="CAPTURE PAUSED"):e==="idle"?(t.style.background="#98a3b3",i.textContent="CAPTURE IDLE · GAME ONLY"):(t.style.background="#2de17a",i.textContent="READING GAME WINDOW"))}renderActiveView(){switch(this.currentActivePage){case"directory":this.renderDirectory();break;case"mission_log":this.renderMissionLog();break;case"servers":this.renderServers();break;case"blueprints":this.renderBlueprints();break;case"planner":this.renderPlanner();break;case"diary":this.renderDiary();break;case"refinery":this.renderRefinery();break;case"executive_hangar":this.renderExecutiveHangar();break;case"hud_piracy":this.renderPiracy();break;case"daylight":this.renderDaylight();break;case"acceptance":this.renderAcceptance();break}}renderDirectory(){var h;const e=this.viewsContainerEl.querySelector("#ss-view-directory");if(!e||e.hidden)return;const t=((h=this.catalog)==null?void 0:h.directory_rows)??[],i=Array.from(new Set(t.map(c=>c.kind).filter(Boolean))),n=t.filter(c=>{if(this.directoryKind&&c.kind!==this.directoryKind)return!1;if(this.directoryQuery){const g=this.directoryQuery.toLowerCase();return c.name.toLowerCase().includes(g)||c.category&&c.category.toLowerCase().includes(g)||c.manufacturer&&c.manufacturer.toLowerCase().includes(g)}return!0}),a=['<option value="">All Categories</option>'].concat(i.map(c=>`<option value="${c}" ${c===this.directoryKind?"selected":""}>${c}</option>`)).join(""),s=n.slice(0,100).map(c=>`
        <tr data-row-id="${c.id}" class="${c.id===this.directorySelectedId?"is-selected":""}">
          <td><strong>${c.name}</strong></td>
          <td>${c.kind??"—"}</td>
          <td>${c.category??"—"}</td>
          <td>${c.manufacturer??"—"}</td>
          <td>${c.price_buy?`${c.price_buy.toLocaleString()} aUEC`:"—"}</td>
          <td>${c.location??"Various"}</td>
        </tr>
      `).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="dir-search" class="ss-input ss-grow" type="text" placeholder="Search commodities, ships, weapons, armor..." value="${this.directoryQuery}" />
          <select id="dir-kind" class="ss-select">${a}</select>
          <span class="ss-muted-text">${n.length} matches</span>
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
              ${s||'<tr><td colspan="6" class="ss-muted-text">No items matching criteria</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;const o=e.querySelector("#dir-search");o&&o.addEventListener("input",()=>{this.directoryQuery=o.value,this.renderDirectory()});const l=e.querySelector("#dir-kind");l&&l.addEventListener("change",()=>{this.directoryKind=l.value,this.renderDirectory()})}renderMissionLog(){var o,l,h,c,g,b,m,p;const e=this.viewsContainerEl.querySelector("#ss-view-mission-log");if(!e||e.hidden)return;const t=((l=(o=this.desktopState)==null?void 0:o.mission_log)==null?void 0:l.missions)??[],i=((c=(h=this.desktopState)==null?void 0:h.mission_log)==null?void 0:c.wallet_changes)??[],n=((b=(g=this.desktopState)==null?void 0:g.mission_log)==null?void 0:b.stats)??{total_completed:t.filter(u=>u.status==="completed").length,total_earned:t.reduce((u,v)=>u+(v.status==="completed"?v.payout:0),0)},a=t.map(u=>`
        <tr>
          <td><strong>${u.title}</strong></td>
          <td><span class="ss-badge ss-badge-${u.status}">${u.status}</span></td>
          <td>${u.category}</td>
          <td>${u.system}</td>
          <td>${u.payout.toLocaleString()} aUEC</td>
          <td>${u.completed_at?new Date(u.completed_at*1e3).toLocaleTimeString():"In progress"}</td>
        </tr>
      `).join(""),s=i.slice(0,50).map(u=>`
        <tr>
          <td>${new Date(u.at*1e3).toLocaleTimeString()}</td>
          <td class="${u.amount>=0?"ss-income":"ss-expense"}">${u.amount>=0?"+":""}${u.amount.toLocaleString()} aUEC</td>
          <td>${u.category}</td>
          <td>${u.note??"—"}</td>
        </tr>
      `).join("");e.innerHTML=`
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
            <div class="ss-stat-chip"><strong>${n.total_completed}</strong> completed</div>
            <div class="ss-stat-chip"><strong>${n.total_earned.toLocaleString()} aUEC</strong> total earned</div>
          </div>
          <div class="ss-table-scroll ss-log-scroll">
            <table class="ss-table">
              <thead><tr><th>CONTRACT</th><th>STATUS</th><th>CATEGORY</th><th>SYSTEM</th><th>PAYOUT</th><th>TIME</th></tr></thead>
              <tbody>${a||'<tr><td colspan="6" class="ss-muted-text">No mission logs recorded</td></tr>'}</tbody>
            </table>
          </div>
        </div>
        <div class="ss-card">
          <h2 class="ss-section-heading">WALLET TRANSACTIONS</h2>
          <div class="ss-table-scroll ss-log-scroll">
            <table class="ss-table">
              <thead><tr><th>TIME</th><th>AMOUNT</th><th>CATEGORY</th><th>NOTE</th></tr></thead>
              <tbody>${s||'<tr><td colspan="4" class="ss-muted-text">No balance changes logged</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>
    `,(m=e.querySelector("#ml-export-csv"))==null||m.addEventListener("click",()=>{this.bridge.sendCommand({action:"mission_export",format:"csv"})}),(p=e.querySelector("#ml-export-json"))==null||p.addEventListener("click",()=>{this.bridge.sendCommand({action:"mission_export",format:"json"})})}renderServers(){var s,o,l,h,c,g,b;const e=this.viewsContainerEl.querySelector("#ss-view-servers");if(!e||e.hidden)return;const t=((o=(s=this.desktopState)==null?void 0:s.servers)==null?void 0:o.entries)??[],i=((h=(l=this.desktopState)==null?void 0:l.server)==null?void 0:h.shard_id)??"Unknown",n=((g=(c=this.desktopState)==null?void 0:c.server)==null?void 0:g.region)??"US-East",a=t.map(m=>{const p=m.shard_id===i;return`
        <tr class="${p?"is-selected":""}">
          <td><strong>Shard ${m.shard_id}</strong> ${p?'<span class="ss-tag ss-tag-accent">Current</span>':""}</td>
          <td>${m.region}</td>
          <td>${m.visit_count}</td>
          <td>${new Date(m.last_seen*1e3).toLocaleString()}</td>
          <td>${m.custom_name??"—"}</td>
          <td>${m.notes??"—"}</td>
        </tr>
      `}).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">SERVER &amp; SHARD HISTORY</h2>
            <p class="ss-muted-text">Active connection: <strong>Shard ${i}</strong> · ${n}</p>
          </div>
          <button id="server-refresh-btn" class="ss-btn ss-btn-accent">Refresh shard</button>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>SHARD ID</th><th>REGION</th><th>VISITS</th><th>LAST OBSERVED</th><th>LABEL</th><th>NOTES</th></tr>
            </thead>
            <tbody>${a||'<tr><td colspan="6" class="ss-muted-text">No server history available</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `,(b=e.querySelector("#server-refresh-btn"))==null||b.addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_people"})})}renderBlueprints(){var l,h,c,g,b,m;const e=this.viewsContainerEl.querySelector("#ss-view-blueprints");if(!e||e.hidden)return;const t=((l=this.catalog)==null?void 0:l.blueprints)??[],i=((h=this.catalog)==null?void 0:h.blueprint_types)??[],n=new Set(((g=(c=this.desktopState)==null?void 0:c.blueprints)==null?void 0:g.owned)??[]),a=t.filter(p=>{if(this.blueprintType&&p.type!==this.blueprintType)return!1;if(this.blueprintQuery){const u=this.blueprintQuery.toLowerCase();return p.name.toLowerCase().includes(u)}return!0}),s=['<option value="">All Types</option>'].concat(i.map(p=>`<option value="${p}" ${p===this.blueprintType?"selected":""}>${p}</option>`)).join(""),o=a.slice(0,100).map(p=>{const u=n.has(p.name),v=p.slots.map(S=>`${S.material_name} (${S.scu?`${S.scu} SCU`:`${S.units} units`})`).join(", ");return`
        <div class="ss-bp-card ${u?"is-owned":""}">
          <div class="ss-bp-header">
            <div>
              <h3 class="ss-bp-title">${p.name}</h3>
              <span class="ss-bp-type">${p.type} · Grade ${p.grade||"Standard"}</span>
            </div>
            <label class="ss-checkbox-label">
              <input type="checkbox" data-bp-index="${p.id}" ${u?"checked":""} />
              <span>Owned</span>
            </label>
          </div>
          <div class="ss-bp-materials">
            <span class="ss-label-sm">Materials:</span>
            <span class="ss-bp-materials-list">${v||"Standard crafting bench components"}</span>
          </div>
        </div>
      `}).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="bp-search" class="ss-input ss-grow" type="text" placeholder="Search crafting recipes and materials..." value="${this.blueprintQuery}" />
          <select id="bp-type" class="ss-select">${s}</select>
          <span class="ss-muted-text">${n.size} of ${t.length} owned</span>
        </div>
        <div class="ss-bp-grid">
          ${o||'<div class="ss-muted-text">No blueprints match your filter</div>'}
        </div>
      </div>
    `,(b=e.querySelector("#bp-search"))==null||b.addEventListener("input",p=>{this.blueprintQuery=p.target.value,this.renderBlueprints()}),(m=e.querySelector("#bp-type"))==null||m.addEventListener("change",p=>{this.blueprintType=p.target.value,this.renderBlueprints()}),e.querySelectorAll("input[data-bp-index]").forEach(p=>{p.addEventListener("change",()=>{const u=Number(p.dataset.bpIndex);this.bridge.sendCommand({action:"toggle_blueprint_owned",blueprint_index:u})})})}renderPlanner(){var a,s,o;const e=this.viewsContainerEl.querySelector("#ss-view-planner");if(!e||e.hidden)return;const i=(((a=this.catalog)==null?void 0:a.mining_locations)??[]).filter(l=>{if(this.plannerFamily&&l.family!==this.plannerFamily||this.plannerSystem&&l.system!==this.plannerSystem)return!1;if(this.plannerQuery){const h=this.plannerQuery.toLowerCase();return l.mineral.toLowerCase().includes(h)||l.location.toLowerCase().includes(h)}return!0}),n=i.map(l=>`
        <tr>
          <td><strong>${l.mineral}</strong></td>
          <td><span class="ss-tag ss-tag-accent">${l.family}</span></td>
          <td>${l.location}</td>
          <td>${l.system}</td>
          <td>${l.kind}</td>
          <td><strong>${l.chance.toFixed(1)}%</strong></td>
          <td>${l.note||"—"}</td>
        </tr>
      `).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row">
          <input id="planner-search" class="ss-input ss-grow" type="text" placeholder="Filter mineral (e.g. Agricium, Quantainium, Bexalite, Gold)..." value="${this.plannerQuery}" />
          <div class="ss-segmented">
            <button class="ss-btn ${this.plannerFamily==="Ship"?"is-active":""}" data-fam="Ship">Ship</button>
            <button class="ss-btn ${this.plannerFamily==="ROC"?"is-active":""}" data-fam="ROC">ROC</button>
            <button class="ss-btn ${this.plannerFamily==="FPS"?"is-active":""}" data-fam="FPS">FPS</button>
          </div>
          <select id="planner-system" class="ss-select">
            <option value="" ${this.plannerSystem===""?"selected":""}>All Systems</option>
            <option value="Stanton" ${this.plannerSystem==="Stanton"?"selected":""}>Stanton</option>
            <option value="Pyro" ${this.plannerSystem==="Pyro"?"selected":""}>Pyro</option>
            <option value="Nyx" ${this.plannerSystem==="Nyx"?"selected":""}>Nyx</option>
          </select>
          <span class="ss-muted-text">${i.length} locations</span>
        </div>
        <div class="ss-table-scroll">
          <table class="ss-table">
            <thead>
              <tr><th>MINERAL</th><th>METHOD</th><th>LOCATION</th><th>SYSTEM</th><th>TYPE</th><th>DEPOSIT CHANCE</th><th>NOTES</th></tr>
            </thead>
            <tbody>${n||'<tr><td colspan="7" class="ss-muted-text">No deposit locations match your criteria</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `,(s=e.querySelector("#planner-search"))==null||s.addEventListener("input",l=>{this.plannerQuery=l.target.value,this.renderPlanner()}),e.querySelectorAll("[data-fam]").forEach(l=>{l.addEventListener("click",()=>{this.plannerFamily=l.dataset.fam||"Ship",this.renderPlanner()})}),(o=e.querySelector("#planner-system"))==null||o.addEventListener("change",l=>{this.plannerSystem=l.target.value,this.renderPlanner()})}renderDiary(){var a,s,o,l,h;const e=this.viewsContainerEl.querySelector("#ss-view-diary");if(!e||e.hidden)return;const t=((s=(a=this.desktopState)==null?void 0:a.diary)==null?void 0:s.entries)??[],i=((l=(o=this.desktopState)==null?void 0:o.diary)==null?void 0:l.auto_log)??!0,n=t.map(c=>`
        <tr>
          <td>${new Date(c.timestamp*1e3).toLocaleString()}</td>
          <td>${c.system} / ${c.body}</td>
          <td>${c.ship}</td>
          <td>${c.ores.map(g=>`${g.name} (${g.scu} SCU)`).join(", ")||"—"}</td>
          <td><strong>${c.total_value?`${c.total_value.toLocaleString()} aUEC`:"—"}</strong></td>
          <td>${c.notes??"—"}</td>
        </tr>
      `).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">MINING RUN DIARY</h2>
            <p class="ss-muted-text">Logs ore signatures, hauls, break metrics, and profits locally.</p>
          </div>
          <div class="ss-toolbar-actions">
            <label class="ss-checkbox-label">
              <input id="diary-auto-log" type="checkbox" ${i?"checked":""} />
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
            <tbody>${n||'<tr><td colspan="6" class="ss-muted-text">No recorded mining runs yet. Scan and extract ore to log entries automatically.</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `,(h=e.querySelector("#diary-auto-log"))==null||h.addEventListener("change",c=>{const g=c.target.checked;this.bridge.sendCommand({action:"diary_auto_log",auto_log:g})})}renderRefinery(){var a,s,o;const e=this.viewsContainerEl.querySelector("#ss-view-refinery");if(!e||e.hidden)return;const t=((s=(a=this.desktopState)==null?void 0:a.refinery)==null?void 0:s.orders)??[],i=Math.floor(Date.now()/1e3),n=t.map((l,h)=>{const c=Math.max(0,l.due-i),g=Math.floor(c/3600),b=Math.floor(c%3600/60),m=c%60,p=c===0?'<span class="ss-badge ss-badge-completed">READY TO COLLECT</span>':`${g}h ${b.toString().padStart(2,"0")}m ${m.toString().padStart(2,"0")}s remaining`,u=l.parts.map(v=>`${v.material}: ${v.yield} cSCU`).join(", ");return`
        <tr>
          <td><strong>#${l.number}</strong></td>
          <td>${l.station}</td>
          <td>${l.method||"Standard"}</td>
          <td>${u}</td>
          <td>${p}</td>
          <td>
            ${c===0?`<button class="ss-btn ss-btn-accent ss-btn-sm" data-collect-order="${h}">Collect</button>`:'<span class="ss-muted-text">Processing</span>'}
          </td>
        </tr>
      `}).join("");e.innerHTML=`
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
            <tbody>${n||'<tr><td colspan="6" class="ss-muted-text">No active refinery orders being tracked</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    `,e.querySelectorAll("[data-collect-order]").forEach(l=>{l.addEventListener("click",()=>{const h=Number(l.dataset.collectOrder);this.bridge.sendCommand({action:"refinery_collected",order_index:h})})}),(o=e.querySelector("#refinery-dismiss-btn"))==null||o.addEventListener("click",()=>{this.bridge.sendCommand({action:"dismiss_refinery"})})}renderExecutiveHangar(){var s,o;const e=this.viewsContainerEl.querySelector("#ss-view-executive-hangar");if(!e||e.hidden)return;const t=((s=this.desktopState)==null?void 0:s.executive_hangar)??{},i=t.timer_seconds??0,a=(t.ships??[{name:"RSI Perseus",bay:"Bay 01",ready:!0},{name:"Anvil Carrack",bay:"Bay 02",ready:!0},{name:"Aegis Eclipse",bay:"Bay 03",ready:!1,recall_seconds:i}]).map(l=>`
        <div class="ss-hangar-card ${l.ready?"is-ready":""}">
          <div class="ss-hangar-top">
            <span class="ss-hangar-bay">${l.bay}</span>
            <span class="ss-badge ${l.ready?"ss-badge-completed":"ss-badge-pending"}">${l.ready?"READY":"IN RECALL"}</span>
          </div>
          <h3 class="ss-hangar-ship">${l.name}</h3>
          <div class="ss-hangar-actions">
            ${l.ready?'<button class="ss-btn ss-btn-accent ss-btn-sm" data-hangar-act="recall">Depart Bay</button>':`<span class="ss-muted-text">Arrives in ${l.recall_seconds??0}s</span>`}
          </div>
        </div>
      `).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">EXECUTIVE HANGAR CONTROL</h2>
            <p class="ss-muted-text">Docking bay status, automated recall tracking, and departure sequencing.</p>
          </div>
          <button id="hangar-hud-btn" class="ss-btn ss-btn-accent">Open Hangar HUD</button>
        </div>
        <div class="ss-hangar-grid">
          ${a}
        </div>
      </div>
    `,(o=e.querySelector("#hangar-hud-btn"))==null||o.addEventListener("click",()=>{this.bridge.sendCommand({action:"hud_mode",target:"hud_hangars"})})}renderPiracy(){var s,o,l,h,c;const e=this.viewsContainerEl.querySelector("#ss-view-hud-piracy");if(!e||e.hidden)return;const t=((s=this.desktopState)==null?void 0:s.piracy)??{},i=t.wait_active??!1,n=t.wait_seconds??0,a=t.snare_alerts??!0;e.innerHTML=`
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
            <div class="ss-big-timer">${Math.floor(n/60)}m ${(n%60).toString().padStart(2,"0")}s</div>
            <div class="ss-toolbar-row">
              <button id="piracy-wait-toggle" class="ss-btn ${i?"ss-btn-accent":""}">${i?"Pause Timer":"Start Timer"}</button>
              <button id="piracy-wait-reset" class="ss-btn">Reset</button>
            </div>
          </div>
          <div class="ss-subcard">
            <h3>Snare Alerts &amp; Interdictions</h3>
            <label class="ss-checkbox-label">
              <input id="piracy-snare-toggle" type="checkbox" ${a?"checked":""} />
              <span>Enable audio/visual HUD alerts on snare interdiction</span>
            </label>
          </div>
        </div>
      </div>
    `,(o=e.querySelector("#piracy-hud-btn"))==null||o.addEventListener("click",()=>{this.bridge.sendCommand({action:"hud_mode",target:"hud_piracy"})}),(l=e.querySelector("#piracy-wait-toggle"))==null||l.addEventListener("click",()=>{this.bridge.sendCommand({action:"piracy_action",sub_action:"toggle_wait"})}),(h=e.querySelector("#piracy-wait-reset"))==null||h.addEventListener("click",()=>{this.bridge.sendCommand({action:"piracy_action",sub_action:"reset_wait"})}),(c=e.querySelector("#piracy-snare-toggle"))==null||c.addEventListener("change",g=>{const b=g.target.checked;this.bridge.sendCommand({action:"piracy_action",sub_action:"snare_alerts",enabled:b})})}renderDaylight(){var p,u,v,S,C;const e=this.viewsContainerEl.querySelector("#ss-view-daylight");if(!e||e.hidden)return;const t=(p=this.catalog)==null?void 0:p.daylight,i=t!=null&&t.systems?Object.keys(t.systems):["Stanton","Pyro","Nyx"],n=(u=t==null?void 0:t.systems)==null?void 0:u[this.daylightSystem],a=(n==null?void 0:n.bodies)??[];!this.daylightBodyName&&a.length>0&&(this.daylightBodyName=a[0].name);const s=a.find(f=>f.name===this.daylightBodyName)??a[0],o=(s==null?void 0:s.sites)??[];!this.daylightSiteName&&o.length>0&&(this.daylightSiteName=o[0].name);const l=o.find(f=>f.name===this.daylightSiteName)??o[0],h=Date.now()/1e3,c=s&&l?qe(s,l,h):{daylight:!0,altitude_degrees:42},g=i.map(f=>`<option value="${f}" ${f===this.daylightSystem?"selected":""}>${f}</option>`).join(""),b=a.map(f=>`<option value="${f.name}" ${f.name===this.daylightBodyName?"selected":""}>${f.name}</option>`).join(""),m=o.map(f=>`<option value="${f.name}" ${f.name===this.daylightSiteName?"selected":""}>${f.name}</option>`).join("");e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <div class="ss-toolbar-row ss-space-between">
          <div>
            <h2 class="ss-section-heading">DAY / NIGHT SOLAR FORECAST</h2>
            <p class="ss-muted-text">Real-time solar geometry and terminator line tracking for planetary surface approaches.</p>
          </div>
          <span class="ss-badge ${c.daylight?"ss-badge-completed":"ss-badge-pending"}">
            ${c.daylight?"☀ SUNLIT (DAY)":"☾ IN SHADOW (NIGHT)"}
          </span>
        </div>
        <div class="ss-toolbar-row">
          <label class="ss-inline-field">System: <select id="dl-sys" class="ss-select">${g}</select></label>
          <label class="ss-inline-field">Body: <select id="dl-body" class="ss-select">${b}</select></label>
          <label class="ss-inline-field">Surface Outpost: <select id="dl-site" class="ss-select">${m}</select></label>
        </div>
        <div class="ss-daylight-info">
          <div class="ss-subcard">
            <h3>Solar Altitude</h3>
            <div class="ss-big-timer">${c.altitude_degrees}°</div>
            <p class="ss-muted-text">${c.daylight?"Above horizon":"Below horizon"}</p>
          </div>
          <div class="ss-subcard">
            <h3>Surface Site Details</h3>
            <p><strong>Site:</strong> ${(l==null?void 0:l.name)??"—"}</p>
            <p><strong>Body Radius:</strong> ${(s==null?void 0:s.radius_km)??0} km</p>
            <p><strong>Rotation Period:</strong> ${Math.round(Math.abs((s==null?void 0:s.period_seconds)??0)/3600)}h</p>
          </div>
        </div>
      </div>
    `,(v=e.querySelector("#dl-sys"))==null||v.addEventListener("change",f=>{this.daylightSystem=f.target.value,this.daylightBodyName="",this.daylightSiteName="",this.renderDaylight()}),(S=e.querySelector("#dl-body"))==null||S.addEventListener("change",f=>{this.daylightBodyName=f.target.value,this.daylightSiteName="",this.renderDaylight()}),(C=e.querySelector("#dl-site"))==null||C.addEventListener("change",f=>{this.daylightSiteName=f.target.value,this.renderDaylight()})}renderAcceptance(){var s,o;const e=this.viewsContainerEl.querySelector("#ss-view-acceptance");if(!e||e.hidden)return;const t=((s=this.desktopState)==null?void 0:s.acceptance)??{},i=t.party_enabled??!0,n=t.friend_enabled??!0,a=t.hide_global_chat??!1;e.innerHTML=`
      <div class="ss-card ss-fill-pane">
        <h2 class="ss-section-heading">AUTOMATIC INVITATION ACCEPTANCE</h2>
        <p class="ss-muted-text">Hands-free handling of incoming requests while piloting or mining.</p>
        <div class="ss-settings-col">
          <label class="ss-checkbox-label">
            <input id="acc-party" type="checkbox" ${i?"checked":""} />
            <span>Automatically accept party invitations from recognized friends &amp; org members</span>
          </label>
          <label class="ss-checkbox-label">
            <input id="acc-friend" type="checkbox" ${n?"checked":""} />
            <span>Automatically accept incoming friend requests</span>
          </label>
          <label class="ss-checkbox-label">
            <input id="acc-hide-chat" type="checkbox" ${a?"checked":""} />
            <span>Hide global chat messages automatically upon entering session</span>
          </label>
          <div class="ss-toolbar-row">
            <button id="acc-save-btn" class="ss-btn ss-btn-accent">Save Settings</button>
          </div>
        </div>
      </div>
    `,(o=e.querySelector("#acc-save-btn"))==null||o.addEventListener("click",()=>{var g,b,m;const l=((g=e.querySelector("#acc-party"))==null?void 0:g.checked)??!0,h=((b=e.querySelector("#acc-friend"))==null?void 0:b.checked)??!0,c=((m=e.querySelector("#acc-hide-chat"))==null?void 0:m.checked)??!1;this.bridge.sendCommand({action:"save_acceptance",party_enabled:l,friend_enabled:h,hide_global_chat:c})})}}const k=40;class re{constructor(e,t){r(this,"root");r(this,"bridge");r(this,"unsubscribe",null);r(this,"desktopViews",null);r(this,"snapshot",null);r(this,"activeMode","people");r(this,"sourceIndex",0);r(this,"taggedOnly",!1);r(this,"searchQuery","");r(this,"previousViewSignature","");r(this,"selectedIds",new Set);r(this,"selectionAnchorId","");r(this,"actionSelectedIds",new Set);r(this,"actionSelectionAnchorId","");r(this,"actionEditorSignature","");r(this,"rosterRowMap",new Map);r(this,"rosterRowSignature",new Map);r(this,"actionRowMap",new Map);r(this,"actionRowSignature",new Map);r(this,"watchRowMap",new Map);r(this,"filteredPeople",[]);r(this,"actionPeople",[]);r(this,"marketSearch","");r(this,"selectedMarketItemId",0);r(this,"selectedWatchId","");r(this,"showMatches",!1);r(this,"modalOpen",!1);r(this,"modalMode","confirm_party");r(this,"modalRecipients",[]);r(this,"modalResend",!1);r(this,"homeShowPrevious",!1);r(this,"virtualScrollTop",0);r(this,"virtualScrollLeft",0);r(this,"domRowCreatedCount",0);r(this,"domRowUpdatedCount",0);r(this,"domRowRemovedCount",0);r(this,"lastUpdatedRowIds",[]);r(this,"rosterScrollEl");r(this,"rosterTbodyEl");r(this,"actionScrollEl");r(this,"actionTbodyEl");r(this,"searchInputEl");r(this,"sourceSelectEl");r(this,"taggedOnlyEl");r(this,"rosterStatusEl");r(this,"selectionSummaryEl");r(this,"actionHeaderEl");r(this,"stageTagSelectEl");r(this,"applyTagSelectEl");r(this,"tagDraftInputEl");r(this,"joinAlertsCheckboxEl");r(this,"queueStatusEl");r(this,"footerStatusEl");r(this,"stageSelectedBtn");r(this,"removeActionBtn");r(this,"clearActionsBtn");r(this,"stageByTagBtn");r(this,"stageFriendsBtn");r(this,"stageOrgBtn");r(this,"addPresetTagBtn");r(this,"applyTagsBtn");r(this,"clearTagsBtn");r(this,"sendFriendsBtn");r(this,"invitePartyBtn");r(this,"viewQueueBtn");r(this,"pauseQueueBtn");r(this,"cancelQueueBtn");r(this,"peopleSectionEl");r(this,"marketSectionEl");r(this,"homeSectionEl");r(this,"settingsSectionEl");r(this,"modalBackdropEl");r(this,"modalTitleEl");r(this,"modalSummaryEl");r(this,"modalTbodyEl");r(this,"modalResendWrapEl");r(this,"modalResendCheckboxEl");r(this,"modalConfirmBtn");r(this,"modalCancelBtn");r(this,"modalPauseBtn");r(this,"modalStopQueueBtn");r(this,"marketSearchInputEl");r(this,"marketItemSelectEl");r(this,"marketQualityInputEl");r(this,"marketPriceInputEl");r(this,"marketUnitInputEl");r(this,"marketWatchesTbodyEl");r(this,"marketNoticesTbodyEl");r(this,"marketNoticesHeadingEl");r(this,"marketShowMatchesBtn");this.root=e,this.bridge=t,this.buildShell(),this.unsubscribe=this.bridge.subscribePeople(i=>{this.onSnapshot(i)})}destroy(){this.desktopViews&&(this.desktopViews.destroy(),this.desktopViews=null),this.unsubscribe&&(this.unsubscribe(),this.unsubscribe=null)}getFilteredPeople(){return this.filteredPeople}getActionPeople(){return this.actionPeople}getSelectedIds(){return Array.from(this.selectedIds)}getActionSelectedIds(){return Array.from(this.actionSelectedIds)}getRosterRowElement(e){return this.rosterRowMap.get(e)}getActionRowElement(e){return this.actionRowMap.get(e)}isModalOpen(){return this.modalOpen}getScrollAnchor(){const e=Math.round(this.virtualScrollTop),t=Math.round(this.virtualScrollLeft),i=Math.max(0,Math.min(this.filteredPeople.length-1,Math.floor(e/k))),n=i>=0&&i<this.filteredPeople.length?this.filteredPeople[i].id:"",a=e-i*k;return{anchorId:n,offsetWithinRow:a,scrollTop:e,scrollLeft:t}}setRosterScroll(e,t=0){this.virtualScrollTop=Math.max(0,Math.round(e)),this.virtualScrollLeft=Math.max(0,Math.round(t)),this.rosterScrollEl.scrollTop=this.virtualScrollTop,this.rosterScrollEl.scrollLeft=this.virtualScrollLeft}buildShell(){this.root.innerHTML=`
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
          </div>
        </main>
      </div>
    `,this.rosterScrollEl=this.root.querySelector("#people-roster-scroll"),this.rosterTbodyEl=this.root.querySelector("#people-roster-tbody"),this.actionScrollEl=this.root.querySelector("#people-action-scroll"),this.actionTbodyEl=this.root.querySelector("#people-action-tbody"),this.searchInputEl=this.root.querySelector("#people-search-input"),this.sourceSelectEl=this.root.querySelector("#people-source-select"),this.taggedOnlyEl=this.root.querySelector("#people-tagged-only"),this.rosterStatusEl=this.root.querySelector("#people-roster-status"),this.selectionSummaryEl=this.root.querySelector("#people-selection-summary"),this.actionHeaderEl=this.root.querySelector("#people-action-header"),this.stageTagSelectEl=this.root.querySelector("#stage-tag-select"),this.applyTagSelectEl=this.root.querySelector("#apply-tag-select"),this.tagDraftInputEl=this.root.querySelector("#tag-draft-input"),this.joinAlertsCheckboxEl=this.root.querySelector("#join-alerts-checkbox"),this.queueStatusEl=this.root.querySelector("#queue-status-text"),this.footerStatusEl=this.root.querySelector("#companion-footer-status"),this.stageSelectedBtn=this.root.querySelector("#stage-selected-btn"),this.removeActionBtn=this.root.querySelector("#remove-action-btn"),this.clearActionsBtn=this.root.querySelector("#clear-actions-btn"),this.stageByTagBtn=this.root.querySelector("#stage-by-tag-btn"),this.stageFriendsBtn=this.root.querySelector("#stage-friends-btn"),this.stageOrgBtn=this.root.querySelector("#stage-org-btn"),this.addPresetTagBtn=this.root.querySelector("#add-preset-tag-btn"),this.applyTagsBtn=this.root.querySelector("#apply-tags-btn"),this.clearTagsBtn=this.root.querySelector("#clear-tags-btn"),this.sendFriendsBtn=this.root.querySelector("#send-friends-btn"),this.invitePartyBtn=this.root.querySelector("#invite-party-btn"),this.viewQueueBtn=this.root.querySelector("#view-queue-btn"),this.pauseQueueBtn=this.root.querySelector("#pause-queue-btn"),this.cancelQueueBtn=this.root.querySelector("#cancel-queue-btn"),this.peopleSectionEl=this.root.querySelector("#ss-view-people"),this.marketSectionEl=this.root.querySelector("#ss-view-market"),this.homeSectionEl=this.root.querySelector("#ss-view-home"),this.settingsSectionEl=this.root.querySelector("#ss-view-settings"),this.modalBackdropEl=this.root.querySelector("#ss-modal-backdrop"),this.modalTitleEl=this.root.querySelector("#ss-modal-title"),this.modalSummaryEl=this.root.querySelector("#ss-modal-summary"),this.modalTbodyEl=this.root.querySelector("#ss-modal-tbody"),this.modalResendWrapEl=this.root.querySelector("#ss-modal-resend-wrap"),this.modalResendCheckboxEl=this.root.querySelector("#ss-modal-resend-checkbox"),this.modalConfirmBtn=this.root.querySelector("#ss-modal-confirm-btn"),this.modalCancelBtn=this.root.querySelector("#ss-modal-cancel-btn"),this.modalPauseBtn=this.root.querySelector("#ss-modal-pause-btn"),this.modalStopQueueBtn=this.root.querySelector("#ss-modal-stop-btn"),this.marketSearchInputEl=this.root.querySelector("#market-search-input"),this.marketItemSelectEl=this.root.querySelector("#market-item-select"),this.marketQualityInputEl=this.root.querySelector("#market-quality-input"),this.marketPriceInputEl=this.root.querySelector("#market-price-input"),this.marketUnitInputEl=this.root.querySelector("#market-unit-input"),this.marketWatchesTbodyEl=this.root.querySelector("#market-watches-tbody"),this.marketNoticesTbodyEl=this.root.querySelector("#market-notices-tbody"),this.marketNoticesHeadingEl=this.root.querySelector("#market-notices-heading"),this.marketShowMatchesBtn=this.root.querySelector("#market-show-matches-btn"),this.bindEvents();const e=this.root.querySelector("#ss-app-sidebar"),t=this.root.querySelector("#ss-app-main .ss-shell");e&&t&&(this.desktopViews=new Pe(this.bridge,e,t,i=>this.setMode(i)))}bindEvents(){this.root.querySelectorAll(".ss-tab").forEach(e=>{e.addEventListener("click",()=>{const t=e.dataset.mode??"people";this.setMode(t)})}),this.root.querySelectorAll("[data-nav]").forEach(e=>{e.addEventListener("click",()=>{const t=e.dataset.nav;t&&this.bridge.sendCommand({action:"navigate",target:t})})}),this.searchInputEl.addEventListener("input",()=>{this.searchQuery=this.searchInputEl.value,this.searchQuery.trim()===""&&this.sourceIndex===1&&(this.sourceIndex=0,this.sourceSelectEl.value="0"),this.renderPeople()}),this.root.querySelector("#people-clear-btn").addEventListener("click",()=>{this.searchQuery="",this.searchInputEl.value="",this.sourceIndex=0,this.sourceSelectEl.value="0",this.renderPeople()}),this.root.querySelector("#people-find-btn").addEventListener("click",()=>{this.sourceIndex=1,this.sourceSelectEl.value="1",this.bridge.sendCommand({action:"search",query:this.searchInputEl.value.trim()}),this.renderPeople()}),this.root.querySelector("#people-refresh-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_people"})}),this.sourceSelectEl.addEventListener("change",()=>{this.sourceIndex=Number(this.sourceSelectEl.value)||0,this.renderPeople()}),this.taggedOnlyEl.addEventListener("change",()=>{this.taggedOnly=this.taggedOnlyEl.checked,this.renderPeople()}),this.rosterScrollEl.addEventListener("scroll",()=>{this.virtualScrollTop=Math.round(this.rosterScrollEl.scrollTop),this.virtualScrollLeft=Math.round(this.rosterScrollEl.scrollLeft)}),this.rosterTbodyEl.addEventListener("click",e=>{const t=e.target.closest("tr[data-player-id]");if(!t)return;const i=t.dataset.playerId;this.toggleSelection(i,e.shiftKey,!1)}),this.actionTbodyEl.addEventListener("click",e=>{const t=e.target.closest("tr[data-player-id]");if(!t)return;const i=t.dataset.playerId;this.toggleSelection(i,e.shiftKey,!0)}),this.stageSelectedBtn.addEventListener("click",()=>{const e=this.getStageTargets().map(t=>t.id);e.length>0&&this.bridge.stagePlayers(e)}),this.removeActionBtn.addEventListener("click",()=>{const e=Array.from(this.actionSelectedIds);e.length>0&&this.bridge.sendCommand({action:"unstage_people",player_ids:e})}),this.clearActionsBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"clear_actions"})}),this.stageByTagBtn.addEventListener("click",()=>{const e=this.stageTagSelectEl.value;e&&this.bridge.sendCommand({action:"stage_tag",label:e,scope:"shard",include_org_affiliate:!1})}),this.stageFriendsBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"stage_tag",label:"Friend",scope:"shard",include_org_affiliate:!1})}),this.stageOrgBtn.addEventListener("click",()=>{this.bridge.sendCommand({action:"stage_tag",label:"Org",scope:"shard",include_org_affiliate:!0})}),this.addPresetTagBtn.addEventListener("click",()=>{const e=this.getActionTargets(),t=this.applyTagSelectEl.value;e.length>0&&t&&this.bridge.sendCommand({action:"tag_many",player_ids:e.map(i=>i.id),label:t})}),this.applyTagsBtn.addEventListener("click",()=>{const e=this.getActionTargets();if(e.length===0)return;const t=this.tagDraftInputEl.value.trim();e.length===1?this.bridge.sendCommand({action:"tag",player_id:e[0].id,label:t,alert:this.joinAlertsCheckboxEl.checked}):this.bridge.sendCommand({action:"tag_many",player_ids:e.map(i=>i.id),label:t})}),this.clearTagsBtn.addEventListener("click",()=>{const e=this.getActionTargets();e.length!==0&&(e.length===1?this.bridge.sendCommand({action:"tag",player_id:e[0].id,label:"",clear_tags:!0,alert:this.joinAlertsCheckboxEl.checked}):this.bridge.sendCommand({action:"tag_many",player_ids:e.map(t=>t.id),label:"",clear_tags:!0}))}),this.sendFriendsBtn.addEventListener("click",()=>{const e=this.getActionTargets().filter(t=>!t.is_friend);if(e.length===0){this.footerStatusEl.textContent="Add eligible players to the Action list first.";return}this.openConfirmationModal("confirm_friend",e)}),this.invitePartyBtn.addEventListener("click",()=>{const e=this.getActionTargets().filter(t=>!t.in_party);if(e.length===0){this.footerStatusEl.textContent="Add eligible players to the Action list first.";return}this.openConfirmationModal("confirm_party",e)}),this.viewQueueBtn.addEventListener("click",()=>{this.openQueueReportModal()}),this.pauseQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:e.paused?"resume_invites":"pause_invites",queue_id:e.id})}),this.cancelQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:"cancel_invites",queue_id:e.id})}),this.modalCancelBtn.addEventListener("click",()=>{this.closeModal()}),this.modalConfirmBtn.addEventListener("click",()=>{if(this.modalMode==="queue_report"){this.closeModal();return}const e=this.modalRecipients.map(n=>n.id).slice(0,_),t=this.modalResendCheckboxEl.checked,i=this.modalMode==="confirm_friend"?"friend_many":"party_many";this.closeModal(),e.length>0&&this.bridge.sendCommand({action:i,player_ids:e,from_actions:!0,confirmed:!0,resend:t})}),this.modalPauseBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:e.paused?"resume_invites":"pause_invites",queue_id:e.id})}),this.modalStopQueueBtn.addEventListener("click",()=>{var t;const e=(t=this.snapshot)==null?void 0:t.invite_queue;e!=null&&e.id&&this.bridge.sendCommand({action:"cancel_invites",queue_id:e.id})}),this.marketSearchInputEl.addEventListener("input",()=>{this.marketSearch=this.marketSearchInputEl.value,this.renderMarketCatalog()}),this.root.querySelector("#market-find-btn").addEventListener("click",()=>{this.marketSearch=this.marketSearchInputEl.value,this.renderMarketCatalog()}),this.root.querySelector("#market-refresh-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_market"})}),this.root.querySelector("#market-refresh-now-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"refresh_market"})}),this.root.querySelector("#market-watch-btn").addEventListener("click",()=>{const e=Number(this.marketItemSelectEl.value),t=Number(this.marketQualityInputEl.value),i=this.marketPriceInputEl.value.trim(),n=i?Number(i):0;if(!e||Number.isNaN(t)||t<0||t>9999||Number.isNaN(n)){this.footerStatusEl.textContent="Choose an item and enter a whole-number quality and valid minimum price.";return}this.bridge.sendCommand({action:"add_watch",item_id:e,quality:Math.trunc(t),price:n,unit:this.marketUnitInputEl.value.trim()||"unit"})}),this.root.querySelector("#market-toggle-watch-btn").addEventListener("click",()=>{this.selectedWatchId&&this.bridge.sendCommand({action:"toggle_watch",watch_id:this.selectedWatchId})}),this.root.querySelector("#market-remove-watch-btn").addEventListener("click",()=>{this.selectedWatchId&&this.bridge.sendCommand({action:"remove_watch",watch_id:this.selectedWatchId})}),this.marketShowMatchesBtn.addEventListener("click",()=>{this.showMatches=!this.showMatches,this.renderMarket()}),this.root.querySelector("#market-dismiss-notices-btn").addEventListener("click",()=>{this.bridge.sendCommand({action:"dismiss_notices"})}),this.root.querySelector("#home-session-current").addEventListener("click",()=>{this.homeShowPrevious=!1,this.renderHome()}),this.root.querySelector("#home-session-prev").addEventListener("click",()=>{this.homeShowPrevious=!0,this.renderHome()})}setMode(e){e||(e="people"),this.activeMode=e,this.peopleSectionEl.hidden=e!=="people",this.marketSectionEl.hidden=e!=="buyer_alerts",this.homeSectionEl.hidden=e!=="home",this.settingsSectionEl.hidden=e!=="settings",this.root.querySelectorAll(".ss-tab").forEach(o=>{const l=o.dataset.mode===e;o.classList.toggle("is-active",l),o.setAttribute("aria-selected",l?"true":"false")});const t=this.root.querySelector(".ss-mode-tabs");t&&(t.hidden=e!=="people"&&e!=="buyer_alerts"),this.desktopViews&&this.desktopViews.setActivePage(e==="buyer_alerts"?"people":e);const i=this.root.querySelector("#ss-page-title"),n=this.root.querySelector("#ss-page-subtitle"),s={home:["Home","Find your next upgrade. See what you've accomplished."],directory:["Item & Ship Finder","Search Star Citizen commodities, ships, weapons, components, and armor."],people:["People","A familiar face in a very large universe."],buyer_alerts:["Buyer Alerts","Watch UEX buy orders for your best mining and crafting hauls."],mission_log:["Mission & Wallet Log","Track mission objectives, payouts, reputations, and balance changes."],servers:["Server History","Track shard visits, cooldowns, regional latencies, and player sessions."],blueprints:["Blueprint Library","Crafting blueprints, material costs, and collection progress."],planner:["Mining Planner","Ore compositions, optimal locations, rock density, and refinery yields."],diary:["Mining Diary","Log your mining runs, rock signatures, locations, and ore hauls."],refinery:["Refinery","Track active jobs, yields, completion timers, and order collections."],executive_hangar:["Executive Hangar","Automated ship recall, docking bay status, and departure sequencing."],hud_piracy:["Piracy","Interdiction traps, quantum snare timers, and ship cargo surveillance."],daylight:["Day/Night Forecast","Plan surface approaches with real-time solar illumination and terminator lines."],acceptance:["Automatic Acceptance","Hands-free party invitations, trade requests, and mission sharing."],settings:["Settings & Modules","Customize HUD behavior, shortcuts, privacy, and installed modules."]}[e]??["SynthScan","YOUR VERSE, CONNECTED"];i.textContent=s[0],n.textContent=s[1]}onSnapshot(e){const t=e.mode&&e.mode!==this.activeMode;this.snapshot=e,this.desktopViews&&this.desktopViews.updateState(e),t&&e.mode&&this.setMode(e.mode),this.renderPeople(),this.renderMarketCatalog(),this.renderMarket(),this.renderHome(),this.modalOpen&&this.modalMode==="queue_report"&&this.renderQueueReportRows()}getCandidates(e){if(this.sourceIndex===2){const t=e.tags??{};return Object.entries(t).map(([i,n])=>T({id:i,handle:n.handle??i,tag:n.label??"",alert:n.alert,is_org:n.is_org}))}if(this.sourceIndex===3)return e.friend_people??[];if(this.sourceIndex===1){const t=this.searchQuery.trim().toLowerCase(),i=(e.search_query??"").trim().toLowerCase();return t.length>0&&t===i?e.search??[]:[]}return e.players}renderPeople(){const e=this.snapshot;if(!e)return;this.searchInputEl.placeholder=this.sourceIndex===1?"Enter an RSI handle, then click Find player":"Filter this list by handle or tag";const t=this.searchQuery.trim().toLowerCase(),i=`${e.session}|${this.sourceIndex}|${t}|${this.taggedOnly?"1":"0"}`,n=i!==this.previousViewSignature;this.previousViewSignature=i;const a=this.getCandidates(e),s=[];for(const p of a){const u=`${p.handle} ${p.tag??p.tags.join(" ")}`.toLowerCase();t&&!u.includes(t)||this.taggedOnly&&(!p.tags||p.tags.length===0)&&!p.tag||s.push(p)}const o=Math.round(this.virtualScrollTop),l=Math.round(this.virtualScrollLeft),h=Math.max(0,Math.min(this.filteredPeople.length-1,Math.floor(o/k))),c=this.filteredPeople.length>0?o-h*k:0;let g="";if(!n&&this.filteredPeople.length>0){const p=new Set(s.map(u=>u.id));for(let u=h;u<this.filteredPeople.length;u++)if(p.has(this.filteredPeople[u].id)){g=this.filteredPeople[u].id;break}if(!g){for(let u=h-1;u>=0;u--)if(p.has(this.filteredPeople[u].id)){g=this.filteredPeople[u].id;break}}}if(n){const p=new Set(s.map(u=>u.id));for(const u of Array.from(this.selectedIds))p.has(u)||this.selectedIds.delete(u)}else{const p=new Set;for(const u of s)p.add(u.id);for(const u of e.players)p.add(u.id);for(const u of e.friend_people??[])p.add(u.id);for(const u of Array.from(this.selectedIds))p.has(u)||this.selectedIds.delete(u)}if(this.filteredPeople=s,this.reconcileTableRows(this.rosterTbodyEl,this.rosterRowMap,this.rosterRowSignature,this.filteredPeople,this.selectedIds),n)this.virtualScrollTop=0,this.rosterScrollEl.scrollTop=0;else if(g){const p=this.filteredPeople.findIndex(u=>u.id===g);p>=0&&(this.virtualScrollTop=Math.max(0,p*k+c),this.rosterScrollEl.scrollTop=this.virtualScrollTop),this.virtualScrollLeft=l,this.rosterScrollEl.scrollLeft=l}const b=(e.action_people??[]).slice(0,_),m=new Set(b.map(p=>p.id));for(const p of Array.from(this.actionSelectedIds))m.has(p)||this.actionSelectedIds.delete(p);this.actionPeople=b,this.reconcileTableRows(this.actionTbodyEl,this.actionRowMap,this.actionRowSignature,this.actionPeople,this.actionSelectedIds,!1),this.updateTagSelectOptions(e.tag_options??["Org","Friendly","Aggressive","Trader","Friend"]),this.updateStatusAndControls()}computeRowSignature(e,t){var s,o;const i=R(e).css,n=(s=e.requests)!=null&&s.friend?`${e.requests.friend.outcome}:${e.requests.friend.detail??""}`:"",a=(o=e.requests)!=null&&o.party?`${e.requests.party.outcome}:${e.requests.party.detail??""}`:"";return`${e.handle}|${e.tag??e.tags.join(",")}|${e.relationship??""}|${i}|${t?"1":"0"}|${e.alert?"1":"0"}|${n}|${a}`}reconcileTableRows(e,t,i,n,a,s=!0){s&&(this.lastUpdatedRowIds=[]);const o=new Set(n.map(h=>h.id));for(const[h,c]of Array.from(t.entries()))o.has(h)||(c.remove(),t.delete(h),i.delete(h),s&&(this.domRowRemovedCount+=1));let l=e.firstChild;for(let h=0;h<n.length;h++){const c=n[h],g=a.has(c.id),b=this.computeRowSignature(c,g);let m=t.get(c.id);m?i.get(c.id)!==b&&(this.populateRowElement(m,c,g),i.set(c.id,b),s&&(this.domRowUpdatedCount+=1,this.lastUpdatedRowIds.push(c.id))):(m=e.ownerDocument.createElement("tr"),m.className="ss-person-row",m.dataset.playerId=c.id,this.populateRowElement(m,c,g),t.set(c.id,m),i.set(c.id,b),s&&(this.domRowCreatedCount+=1,this.lastUpdatedRowIds.push(c.id))),m!==l?e.insertBefore(m,l):l=l.nextSibling}}populateRowElement(e,t,i){const n=R(t);e.classList.toggle("is-selected",i),e.setAttribute("aria-selected",i?"true":"false"),e.style.height=`${k}px`;const s=(t.tags&&t.tags.length>0?t.tags:Re(t.tag)).map(h=>{const c=V(h),g=Math.trunc((14*4+c.r)/5),b=Math.trunc((18*4+c.g)/5),m=Math.trunc((25*4+c.b)/5);return`<span class="ss-tag-chip" data-tag="${this.escapeHtml(h)}" style="color:${c.css};background:rgb(${g},${b},${m});border-color:rgba(${c.r},${c.g},${c.b},0.49)">${this.escapeHtml(h)}</span>`}).join(""),o=[];if(t.requests)for(const[h,c]of Object.entries(t.requests)){if(!c)continue;const g=h==="friend"?"Friend":"Party",b=c.outcome??"",m=c.detail??"";let p="",u="ss-receipt-muted";b==="Sent"?(p=`✓ ${g} sent`,u="ss-receipt-ok"):m==="Already a friend"||m==="Already in party"?p=`${g}: already ${h==="friend"?"friends":"in party"}`:b==="Queued"||b==="Sending"?p=`… ${g} ${b}`:(p=`⚠ ${g}: ${m||b}`,u="ss-receipt-warn"),o.push(`<span class="ss-receipt ${u}">${this.escapeHtml(p)}</span>`)}const l=t.relationship??(t.is_self?"You":t.in_party&&t.is_friend?"Party + Friend":t.in_party?"Party":t.is_friend?"Friend":"—");e.innerHTML=`
      <td class="col-player">
        <div class="ss-player-cell">
          <span class="ss-row-check ${i?"is-checked":""}" aria-hidden="true">${i?"✓":""}</span>
          <span class="ss-person-badge" style="color:${n.css}" aria-hidden="true">●</span>
          <div class="ss-player-stack">
            <span class="ss-player-handle">${this.escapeHtml(t.handle)}</span>
            ${o.length>0?`<div class="ss-receipts-row">${o.join("")}</div>`:""}
          </div>
        </div>
      </td>
      <td class="col-tags"><div class="ss-tags-run">${s}</div></td>
      <td class="col-rel" style="color:${n.css}">${this.escapeHtml(l)}</td>
    `}toggleSelection(e,t,i){const n=i?this.actionPeople:this.filteredPeople,a=i?this.actionSelectedIds:this.selectedIds,s=i?this.actionSelectionAnchorId:this.selectionAnchorId;if(t&&s){const o=n.findIndex(h=>h.id===s),l=n.findIndex(h=>h.id===e);if(o>=0&&l>=0){const h=Math.min(o,l),c=Math.max(o,l);for(let g=h;g<=c;g++)a.add(n[g].id)}else a.has(e)?a.delete(e):a.add(e)}else a.has(e)?a.delete(e):a.add(e),i?this.actionSelectionAnchorId=e:this.selectionAnchorId=e;i?this.reconcileTableRows(this.actionTbodyEl,this.actionRowMap,this.actionRowSignature,this.actionPeople,this.actionSelectedIds,!1):this.reconcileTableRows(this.rosterTbodyEl,this.rosterRowMap,this.rosterRowSignature,this.filteredPeople,this.selectedIds),this.updateStatusAndControls()}getChosenRosterPlayers(){return this.filteredPeople.filter(e=>this.selectedIds.has(e.id)&&!e.is_self)}getStageTargets(){return this.getChosenRosterPlayers()}getActionTargets(){return this.actionPeople.filter(e=>!e.is_self)}updateTagSelectOptions(e){const t=this.stageTagSelectEl.value,i=this.applyTagSelectEl.value,n=e.map(o=>`<option value="${this.escapeHtml(o)}">${this.escapeHtml(o)}</option>`).join("");this.stageTagSelectEl.innerHTML!==n&&(this.stageTagSelectEl.innerHTML=n,e.includes(t)&&(this.stageTagSelectEl.value=t));const a=e.filter(o=>o!=="Friend"),s=a.map(o=>`<option value="${this.escapeHtml(o)}">${this.escapeHtml(o)}</option>`).join("");this.applyTagSelectEl.innerHTML!==s&&(this.applyTagSelectEl.innerHTML=s,a.includes(i)&&(this.applyTagSelectEl.value=i))}updateStatusAndControls(){const e=this.snapshot;if(!e)return;const t=this.getActionTargets(),i=t.map(v=>v.id).join(","),a=this.root.ownerDocument.activeElement===this.tagDraftInputEl;if(i!==this.actionEditorSignature&&!a)if(this.actionEditorSignature=i,t.length===1){const v=t[0];this.tagDraftInputEl.value=v.manual_tag??v.tag??v.tags.join(", "),this.joinAlertsCheckboxEl.checked=!!v.alert}else this.tagDraftInputEl.value="",this.joinAlertsCheckboxEl.checked=!1;const s=!!(e.session&&e.session.length>0),o=!!e.social_busy,l=Math.min(_,e.action_limit??_),h=this.actionPeople.length<l,c=this.getStageTargets();this.stageSelectedBtn.disabled=!s||o||!h||c.length===0,this.removeActionBtn.disabled=!s||o||this.actionSelectedIds.size===0,this.clearActionsBtn.disabled=!s||o||this.actionPeople.length===0,this.stageByTagBtn.disabled=!s||o||!h,this.stageOrgBtn.disabled=!s||o||!h,this.stageFriendsBtn.disabled=!s||o||!h||!e.friends_known;const g=s&&!o&&t.length>0;this.applyTagsBtn.disabled=!g,this.clearTagsBtn.disabled=!g,this.addPresetTagBtn.disabled=!g,this.joinAlertsCheckboxEl.disabled=!g||t.length!==1,this.sendFriendsBtn.disabled=!g,this.invitePartyBtn.disabled=!g,this.actionHeaderEl.textContent=`Action list · ${this.actionPeople.length} / ${l}${o?" · queue running":""}`,this.selectionSummaryEl.textContent=`${this.selectedIds.size} selected · ${c.length} eligible`;let b=s?`${e.players.length} reported shard members`:"Waiting for current shard";if(this.sourceIndex===1){const v=this.searchQuery.trim();b=v?e.search_busy?"Searching handles…":`${this.filteredPeople.length} result(s) for “${e.search_query??v}”`:"Enter a handle, then click Find player."}else this.sourceIndex===3&&(b=e.friends_known?`${(e.friend_people??[]).length} friends`:"Friends list is loading or unavailable · Refresh shard to retry");e.roster_loading&&this.sourceIndex===0&&(b+=" · refreshing"),e.roster_error&&this.sourceIndex!==1&&(b+=` · ${e.roster_error}`),this.rosterStatusEl.textContent=b;const m=e.invite_queue,p=!!(m&&m.active&&!m.cancelling);this.viewQueueBtn.disabled=!(e.batch_results&&e.batch_results.length>0)&&!(m!=null&&m.id),this.pauseQueueBtn.disabled=!p,this.cancelQueueBtn.disabled=!p,this.pauseQueueBtn.textContent=m!=null&&m.paused?"Resume":"Pause",this.queueStatusEl.textContent=this.formatQueueSummary(m);let u=e.status??"Ready";u+=" · Tagged-player alerts report list appearances; the first snapshot stays quiet.",(e.friends_known===!1||e.party_known===!1)&&(u+=" · Friend / party status is checking or unavailable; unconfirmed rows stay neutral."),this.footerStatusEl.textContent=u}formatQueueSummary(e){if(!e||!e.id)return"Party invitations: idle · 0.09–0.99s paced gap";let i=`${e.operation==="friend"?"Friends: ":"Party: "}${e.state} · ${e.sent} sent · ${e.skipped} skipped · ${e.remaining} remaining`;return e.active&&!e.paused&&typeof e.next_in_seconds=="number"&&e.next_in_seconds>0&&(i+=` · next in ${Math.trunc(e.next_in_seconds)}s`),e.current_handle&&(i+=` · ${e.current_handle}`),i}openConfirmationModal(e,t){this.modalOpen=!0,this.modalMode=e,this.modalRecipients=t.slice(0,_),this.modalResend=!1,this.modalResendCheckboxEl.checked=!1,this.modalResendWrapEl.hidden=!1,this.modalConfirmBtn.hidden=!1,this.modalPauseBtn.hidden=!0,this.modalStopQueueBtn.hidden=!0,this.modalCancelBtn.textContent="Cancel";const i=e==="confirm_friend";this.modalTitleEl.textContent=i?"Confirm friend requests":"Confirm party invitations",this.modalSummaryEl.textContent=`${i?"Send friend requests to":"Invite"} ${this.modalRecipients.length} player(s)? Random 0.09–0.99s gap; current-shard membership is rechecked.`,this.modalTbodyEl.innerHTML=this.modalRecipients.map(n=>{const a=i?n.friend_requested_before:n.invited_before,s=a?"Previous attempt":i?"Add friend":"Invite",o=a?"Skipped unless repeat requests are explicitly enabled below; the previous attempt may be unconfirmed.":n.relationship??"Ready";return`
          <tr data-recipient-id="${this.escapeHtml(n.id)}">
            <td>${this.escapeHtml(n.handle)}</td>
            <td>${this.escapeHtml(s)}</td>
            <td>${this.escapeHtml(o)}</td>
          </tr>
        `}).join(""),this.modalBackdropEl.hidden=!1,this.modalCancelBtn.focus()}openQueueReportModal(){this.modalOpen=!0,this.modalMode="queue_report",this.modalResendWrapEl.hidden=!0,this.modalConfirmBtn.hidden=!0,this.modalPauseBtn.hidden=!1,this.modalStopQueueBtn.hidden=!1,this.modalCancelBtn.textContent="Close",this.modalTitleEl.textContent="Social action queue",this.renderQueueReportRows(),this.modalBackdropEl.hidden=!1,this.modalCancelBtn.focus()}renderQueueReportRows(){const e=this.snapshot,t=e==null?void 0:e.invite_queue;this.modalSummaryEl.textContent=this.formatQueueSummary(t);const i=!!(t&&t.active&&!t.cancelling);this.modalPauseBtn.disabled=!i,this.modalStopQueueBtn.disabled=!i,this.modalPauseBtn.textContent=t!=null&&t.paused?"Resume":"Pause";const n=(t==null?void 0:t.results)??(e==null?void 0:e.batch_results)??[];this.modalTbodyEl.innerHTML=n.map(a=>`
        <tr data-recipient-id="${this.escapeHtml(a.id)}">
          <td>${this.escapeHtml(a.handle)}</td>
          <td>${this.escapeHtml(a.outcome)}</td>
          <td>${this.escapeHtml(a.detail??"")}</td>
        </tr>
      `).join("")}closeModal(){this.modalOpen=!1,this.modalBackdropEl.hidden=!0}renderMarketCatalog(){var a;const e=((a=this.snapshot)==null?void 0:a.market_items)??[],t=this.marketSearch.trim().toLowerCase(),i=e.filter(s=>!t||s.name.toLowerCase().includes(t)).sort((s,o)=>s.name.localeCompare(o.name)).slice(0,500),n=i.map(s=>`<option value="${s.id}">${this.escapeHtml(s.name)}</option>`).join("");this.marketItemSelectEl.innerHTML!==n&&(this.marketItemSelectEl.innerHTML=n,this.selectedMarketItemId&&i.some(s=>s.id===this.selectedMarketItemId)&&(this.marketItemSelectEl.value=String(this.selectedMarketItemId)))}renderMarket(){const e=this.snapshot;if(!e)return;const t=e.watches??[];!this.selectedWatchId&&t.length>0&&(this.selectedWatchId=t[0].id);const i=new Set(t.map(a=>a.id));for(const[a,s]of Array.from(this.watchRowMap.entries()))i.has(a)||(s.remove(),this.watchRowMap.delete(a));for(const a of t){let s=this.watchRowMap.get(a.id);s||(s=this.marketWatchesTbodyEl.ownerDocument.createElement("tr"),s.dataset.watchId=a.id,s.addEventListener("click",()=>{this.selectedWatchId=a.id,this.renderMarket()}),this.watchRowMap.set(a.id,s),this.marketWatchesTbodyEl.appendChild(s)),s.classList.toggle("is-selected",a.id===this.selectedWatchId);const o=a.quality?`Q${a.quality}`:"Any",l=a.minimum_price?`${a.minimum_price} / ${a.unit??"unit"}`:"Any price",h=(a.matches??[]).length,c=a.enabled?a.error?"Refresh unavailable":"Checked":"Paused";s.innerHTML=`
        <td>${this.escapeHtml(a.name)}</td>
        <td>${this.escapeHtml(o)}</td>
        <td>${this.escapeHtml(l)}</td>
        <td>${h}</td>
        <td>${this.escapeHtml(c)}</td>
      `}this.marketNoticesHeadingEl.textContent=this.showMatches?"Current matching buy requests — select one to open its UEX advertisement":"Recent HUD notices — buyer matches and tagged-player appearances",this.marketShowMatchesBtn.textContent=this.showMatches?"Show notices":"Show matches";let n=e.notifications??[];if(this.showMatches){const a=t.find(s=>s.id===this.selectedWatchId);n=((a==null?void 0:a.matches)??[]).map(s=>({title:"BUY REQUEST",detail:`${s.price} UEC / ${s.unit} · ${s.location}`,at:s.renewed??0,url:s.url}))}this.marketNoticesTbodyEl.innerHTML=n.map(a=>`
        <tr>
          <td>${this.escapeHtml(`${a.title} · ${a.detail}`)}</td>
          <td>${a.at?"Recent":"—"}</td>
        </tr>
      `).join("")}renderHome(){var g;const e=(g=this.snapshot)==null?void 0:g.home,t=this.homeShowPrevious?e==null?void 0:e.previous:e==null?void 0:e.current,i=(t==null?void 0:t.blueprints)??[],n=(t==null?void 0:t.reputation)??[],a=(t==null?void 0:t.contracts_completed)??0;this.root.querySelector("#home-session-current").classList.toggle("is-active",!this.homeShowPrevious),this.root.querySelector("#home-session-prev").classList.toggle("is-active",this.homeShowPrevious);const s=this.root.querySelector("#home-metrics-row");s.innerHTML=`
      <div class="ss-metric-card">
        <span class="ss-metric-value">${i.length}</span>
        <span class="ss-metric-label">Blueprints received</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${a}</span>
        <span class="ss-metric-label">Contracts completed</span>
      </div>
      <div class="ss-metric-card">
        <span class="ss-metric-value">${n.length}</span>
        <span class="ss-metric-label">Reputation changes</span>
      </div>
    `;const o=this.root.querySelector("#home-blueprints-list");o.innerHTML=i.length===0?'<li class="ss-muted-text">No blueprint grants recorded in this session.</li>':i.map(b=>`<li>${this.escapeHtml(b.name)}</li>`).join("");const l=this.root.querySelector("#home-rep-list");l.innerHTML=n.length===0?'<li class="ss-muted-text">No balance changes between the saved reads.</li>':n.map(b=>`<li><strong>${this.escapeHtml(b.faction)}</strong> <span class="ss-accent-text">${b.delta>0?`+${b.delta}`:b.delta}</span></li>`).join("");const h=e==null?void 0:e.synthstrings,c=this.root.querySelector("#home-patch-banner");h!=null&&h.title?c.innerHTML=`
        <strong>${this.escapeHtml(h.patch_label??"Star Citizen")}</strong>
        <span>${this.escapeHtml(h.status_label??"Game text unchanged — No action needed")} · ${this.escapeHtml(h.summary??"")}</span>
      `:c.innerHTML=`
        <strong>${this.escapeHtml((e==null?void 0:e.identity)||"No live shard observation")}</strong>
        <span>Game text unchanged — No action needed</span>
      `}escapeHtml(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}}async function Be(d){const e=[],t=(y,E)=>(E||e.push(y),E),n=(y=>{const E=[];for(let w=0;w<y;w++){const we=`pilot-${String(w).padStart(3,"0")}`,Ee=`Pilot_${String(w).padStart(3,"0")}`;E.push({id:we,handle:Ee,tags:w%5===0?["Org","Friendly"]:["Friendly"],tag:w%5===0?"Org, Friendly":"Friendly",is_org:w%5===0,is_self:w===0,in_party:w===1,is_friend:w===2,on_shard:!0,relationship:w===0?"You":w===1?"Party":w===2?"Friend":"Shard"})}return E})(500),a=new ie({revision:1,session:"synthetic-500-session",players:n,action_people:[n[1],n[2]],friends_known:!0,party_known:!0,status:"Synthetic 500-player regression fixture"}),s=new re(d,a),o=s.domRowCreatedCount;t("initial_500_rows_created",o===500);const l=R({is_self:!0,in_party:!0,is_friend:!0}),h=R({is_self:!1,in_party:!0,is_friend:!0}),c=R({is_self:!1,in_party:!1,is_friend:!0}),g=t("self_purple_party_blue_friend_green_priority",l.css===ae.css&&h.css===ne.css&&c.css===oe.css),b=t("friend_and_friendly_distinct_green",V("Friend").css!==V("Friendly").css),m=(y,E=!1)=>{if(!y)return;const w=new MouseEvent("click",{bubbles:!0,cancelable:!0,shiftKey:E});y.dispatchEvent(w)};m(s.getRosterRowElement("pilot-142")),m(s.getRosterRowElement("pilot-145"));let p=s.getSelectedIds().length===2&&s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-145");m(s.getRosterRowElement("pilot-142")),p=p&&s.getSelectedIds().length===1&&s.getSelectedIds()[0]==="pilot-145",m(s.getRosterRowElement("pilot-142")),m(s.getActionRowElement("pilot-001")),m(s.getActionRowElement("pilot-002")),p=p&&s.getActionSelectedIds().length===2,m(s.getActionRowElement("pilot-001")),p=p&&s.getActionSelectedIds().length===1&&s.getActionSelectedIds()[0]==="pilot-002",m(s.getActionRowElement("pilot-002")),p=p&&s.getActionSelectedIds().length===0,t("plain_click_toggles_in_both_lists",p),m(s.getRosterRowElement("pilot-144"),!0);const u=t("shift_range_selection_works",s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-143")&&s.getSelectedIds().includes("pilot-144")&&s.getSelectedIds().includes("pilot-145")),S=140*k+12;s.setRosterScroll(S,24);const C=s.getScrollAnchor(),f=d.querySelector("#tag-draft-input");f.value="Scout, Unsaved draft";const I=s.domRowCreatedCount,O=s.domRowUpdatedCount;for(let y=0;y<3;y++)a.publish({written_at:Date.now()/1e3,status:`Heartbeat ${y}`});const x=s.domRowCreatedCount-I,L=s.domRowUpdatedCount-O,$=s.getScrollAnchor(),H=t("heartbeat_keeps_scroll",x===0&&L===0&&$.anchorId==="pilot-140"&&$.offsetWithinRow===12&&$.scrollTop===C.scrollTop),q=a.getSnapshot().players.map(y=>y.id==="pilot-142"?{...y,is_friend:!0,relationship:"Friend"}:y);a.publish({players:q});const P=t("single_row_update_on_relationship",s.lastUpdatedRowIds.length===1&&s.lastUpdatedRowIds[0]==="pilot-142"&&s.domRowCreatedCount===I),W=t("relationship_refresh_keeps_scroll",s.getScrollAnchor().anchorId==="pilot-140"&&s.getScrollAnchor().offsetWithinRow===12),z=[];for(let y=0;y<5;y++)z.push({id:`new-joiner-${y}`,handle:`A_NewJoiner_${y}`,tags:[],on_shard:!0});const Y=[...z,...q];a.publish({players:Y});const N=s.getScrollAnchor(),le=t("membership_insert_keeps_anchor_and_selection",N.anchorId==="pilot-140"&&N.offsetWithinRow===12&&N.scrollTop===145*k+12&&s.getSelectedIds().includes("pilot-142")&&s.getSelectedIds().includes("pilot-145")),ce=t("unsaved_tags_preserved",f.value==="Scout, Unsaved draft"),G=Y.filter(y=>y.id!=="pilot-140");a.publish({players:G});const K=s.getScrollAnchor(),de=t("removed_anchor_keeps_neighbour",K.anchorId==="pilot-141"&&K.offsetWithinRow===12);await a.sendCommand({action:"tag_many",player_ids:["pilot-142","pilot-145"],label:"Trader, Crew"});const he=t("tag_reconciliation_updates_only_affected_rows",s.lastUpdatedRowIds.length===2&&s.lastUpdatedRowIds.includes("pilot-142")&&s.lastUpdatedRowIds.includes("pilot-145")),pe=G.slice(10,80).map(y=>y.id);await a.stagePlayers(pe);const ue=t("action_list_cap_enforced",s.getActionPeople().length===_),X=d.querySelector("#people-search-input");X.value="nonexistent_handle_xyz",X.dispatchEvent(new Event("input",{bubbles:!0}));const me=t("filter_resets_intentionally",s.getFilteredPeople().length===0&&s.getScrollAnchor().scrollTop===0),ge=t("action_list_independent_of_roster_filter",s.getActionPeople().length===_);d.querySelector("#people-clear-btn").click();const be=a.commands.filter(y=>y.action==="party_many"||y.action==="friend_many").length,J=d.querySelector("#invite-party-btn");J.click();const Z=s.isModalOpen(),ye=d.querySelector("#ss-modal-resend-checkbox"),ee=d.querySelector("#ss-modal-cancel-btn"),ve=t("cancel_is_default_and_resend_default_off",Z&&!ye.checked&&d.ownerDocument.activeElement===ee);ee.click();const fe=a.commands.filter(y=>y.action==="party_many"||y.action==="friend_many").length,Se=t("confirmation_modal_blocks_unconfirmed_requests",Z&&!s.isModalOpen()&&be===0&&fe===0);J.click(),d.querySelector("#ss-modal-confirm-btn").click();const M=a.commands.filter(y=>y.action==="party_many"),_e=t("confirmed_request_sends_bounded_batch",M.length===1&&M[0].confirmed===!0&&M[0].resend===!1&&Array.isArray(M[0].player_ids)&&M[0].player_ids.length<=_);let D=!1;try{await a.sendCommand({action:"party_many",player_ids:["pilot-142"],confirmed:!1})}catch{D=!0}t("unconfirmed_bridge_call_rejected",D),s.setRosterScroll(3200,0),f.value="Resize draft preserved";let B=!0;for(const[y,E]of[[860,700],[1240,840],[1600,1e3]])d.style.width=`${y}px`,d.style.height=`${E}px`,window.dispatchEvent(new Event("resize")),B=B&&f.value==="Resize draft preserved"&&s.getActionPeople().length===_&&s.getScrollAnchor().scrollTop===3200;return t("resize_preserves_state_and_fits",B),s.destroy(),{passed:e.length===0,roster_size:500,initial_created_rows:o,heartbeat_recreated_rows:x,heartbeat_keeps_scroll:H,relationship_refresh_keeps_scroll:W,single_row_update_on_relationship:P,membership_insert_keeps_anchor_and_selection:le,removed_anchor_keeps_neighbour:de,filter_resets_intentionally:me,unsaved_tags_preserved:ce,plain_click_toggles_in_both_lists:p,shift_range_selection_works:u,action_list_cap_enforced:ue,action_list_independent_of_roster_filter:ge,tag_reconciliation_updates_only_affected_rows:he,self_purple_party_blue_friend_green_priority:g,friend_and_friendly_distinct_green:b,confirmation_modal_blocks_unconfirmed_requests:Se,cancel_is_default_and_resend_default_off:ve,confirmed_request_sends_bounded_batch:_e,resize_preserves_state_and_fits:B,unconfirmed_bridge_call_rejected:D,outgoing_live_requests_sent:0,failures:e}}const U=document.querySelector("#app");var te;if(U)if(new URLSearchParams(typeof location<"u"?location.search:"").get("suite")==="roster500")Be(U).then(e=>{var t,i;(i=(t=window.chrome)==null?void 0:t.webview)==null||i.postMessage({kind:"suite_result",result:e})});else{const t=typeof window<"u"&&!!((te=window.chrome)!=null&&te.webview)?new Te:new ie({revision:1,session:"standalone-preview-session",players:[{id:"self-pilot",handle:"YourPilot",tags:["Org"],is_self:!0,is_org:!0,in_party:!0,is_friend:!0,on_shard:!0,relationship:"You"},{id:"party-pilot",handle:"Cassiopeia",tags:["Crew","Friendly"],in_party:!0,is_friend:!0,on_shard:!0,relationship:"Party + Friend"},{id:"friend-pilot",handle:"NovaDrift",tags:["Trader","Friend"],is_friend:!0,on_shard:!0,relationship:"Friend",requests:{friend:{outcome:"Sent",detail:"Friend request receipt returned"}}},{id:"org-pilot",handle:"OrionAtlas",tags:["Org Affiliate"],is_org:!0,on_shard:!0,relationship:"Org"}],action_people:[],friends_known:!0,party_known:!0,status:"Standalone preview — no live game connection"}),i=new re(U,t);window.__synthscanDesktop={controller:i,bridge:t}}
