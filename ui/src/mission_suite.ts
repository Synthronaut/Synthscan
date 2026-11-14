import { InMemoryDesktopBridge } from './bridge';
import { DesktopAppController } from './people_controller';
import { escapeHtml, groupBySession } from './mission_view';

export interface MissionSuiteReport {
  passed: boolean;
  checks: Record<string, boolean>;
}

export async function runMissionRegressionSuite(root: HTMLElement): Promise<MissionSuiteReport> {
  const entries = [
    { id: 'change:a', at: 300, session: 's2', cells: ['11-11 12:00', 'Mission reward', 'Increase', '1', '2', '+50,000', 'Delivery', 'x'], detail: 'A <b>detail</b>', change_id: 'a', is_wallet: true, category: 'mission_reward' },
    { id: 'mission:b', at: 250, session: 's2', cells: ['11-11 11:00', 'Wallet', 'Cargo', 'Increase', '—', '+1', 'x'], detail: 'B' },
    { id: 'change:c', at: 100, session: 's1', cells: ['11-10 09:00', 'Repairs', 'Decrease', '9', '8', '-1', '', 'x'], detail: 'C', change_id: 'c', is_wallet: true, category: 'repair' },
    { id: 'mission:d', at: 50, session: '', cells: ['11-09 09:00', 'Mission', 'Old', 'Complete', '—', '—', 'x'], detail: 'D' },
  ];
  const sessions = [
    { id: 's2', started_at: 200, ended_at: null, completed: 3, failed: 1, wallet: [{ currency: 'AUEC', delta: 50000 }] },
    { id: 's1', started_at: 90, ended_at: 4000, completed: 2, wallet: [{ currency: 'AUEC', delta: -1 }] },
  ];

  const bridge = new InMemoryDesktopBridge({
    mode: 'mission_log',
    session: 'shard',
    players: [],
    mission: {
      columns: [['Time', 100], ['Type', 80], ['Activity', 200], ['Outcome', 80], ['Rep', 60], ['aUEC', 80], ['Analysis', 120]],
      entries,
      sessions,
      current_session: 's2',
      display_count: 4,
      display_offset: 0,
      display_limit: 100,
      analytics: {
        totals: { gains: 50001, losses: 1, net: 50000, attributed: 50000, unattributed_gain: 1, missions_completed: 5 },
        factions: [
          { name: 'Hurston Dynamics', auec: 50000, missions: 2, rep_net: 120, avg_per_mission: 25000 },
          { name: 'Citizens <script>', auec: 10000, missions: 1, rep_net: 0, avg_per_mission: 10000 },
        ],
        categories: [{ key: 'repair', label: 'Repairs', gain: 0, loss: 1 }],
        daily: [{ day: '2026-11-10', gain: 5, loss: 1, net: 4 }, { day: '2026-11-11', gain: 50000, loss: 0, net: 50000 }],
        sessions: [{ id: 's1', net: -1, completed: 2 }, { id: 's2', net: 50000, completed: 3 }],
        top_missions: [{ title: 'Delivery', faction: 'Hurston Dynamics', auec: 50000, at: 300 }],
      },
    },
  });

  const controller = new DesktopAppController(root, bridge);
  const checks: Record<string, boolean> = {};

  const section = root.querySelector('#ss-view-mission') as HTMLElement | null;
  checks.mode_mounted_and_visible = Boolean(section && !section.hidden);
  checks.activation_requested_default_view = bridge.commands.some((c) => c.action === 'mission_view' && c.offset === 0);

  const rows = Array.from(root.querySelector('#mission-tbody')!.querySelectorAll<HTMLTableRowElement>('tr'));
  const dividers = rows.filter((r) => r.classList.contains('ss-session-divider'));
  checks.session_dividers_between_sessions = dividers.length === 3 && rows.length === 7;
  checks.live_session_marked = dividers[0].classList.contains('is-live') && !dividers[1].classList.contains('is-live');

  const factionRows = root.querySelector('#mission-factions')!.querySelectorAll('.ss-faction-row');
  checks.faction_bars_rendered = factionRows.length === 2;
  const factionText = root.querySelector('#mission-factions')!.innerHTML;
  checks.faction_names_escaped = !factionText.includes('<script>');

  const kpiText = root.querySelector('#mission-kpis')!.querySelectorAll('.ss-kpi-tile').length;
  checks.kpis_rendered = kpiText === 5;

  // Selecting a wallet row shows detail as text and the classify control.
  const entryRows = rows.filter((r) => r.dataset.entryId !== undefined);
  entryRows[0].click();
  const detail = root.querySelector('#mission-detail')!;
  const classifyRow = root.querySelector('#mission-classify-row') as HTMLElement;
  checks.detail_shown_as_text = detail.textContent === 'A <b>detail</b>';
  checks.classify_visible_for_wallet_row = !classifyRow.hidden;

  // Filter change sends a view command with the chosen mode.
  const modeSelect = root.querySelector('#mission-mode') as HTMLSelectElement;
  modeSelect.value = 'wallet';
  modeSelect.dispatchEvent(new Event('change', { bubbles: true }));
  checks.mode_change_sends_view = bridge.commands.some((c) => c.action === 'mission_view' && c.mode === 'wallet');

  // Export request carries only the format; the native side owns the save dialog.
  const exportBtn = Array.from(root.querySelectorAll<HTMLButtonElement>('button[data-mission-export]')).find((b) => b.dataset.missionExport === 'csv');
  exportBtn?.click();
  checks.export_sends_format = bridge.commands.some((c) => c.action === 'mission_export' && c.format === 'csv');

  // Pure helpers.
  const grouped = groupBySession([entries[0], entries[1]] as never, sessions, 's2');
  checks.grouping_single_session_one_divider = grouped.filter((r) => r.kind === 'divider').length === 1;
  checks.escape_helper = escapeHtml('<a href="x">&</a>') === '&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;';

  controller.destroy();
  return { passed: Object.values(checks).every(Boolean), checks };
}
