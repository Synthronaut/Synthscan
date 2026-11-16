import { InMemoryDesktopBridge } from './bridge';
import { DesktopAppController } from './people_controller';
import {
  calculateCrewSplit,
  calculateGpsIntercept,
  calculateSnareGeometry,
  parseShowLocationText,
} from './piracy_data';

export interface PiracySuiteReport {
  passed: boolean;
  checks: Record<string, boolean>;
  details: Record<string, string>;
}

export async function runPiracyRegressionSuite(root: HTMLElement): Promise<PiracySuiteReport> {
  const bridge = new InMemoryDesktopBridge({
    mode: 'hud_piracy',
    session: 'shard-pyro-1',
    players: [],
    piracy: {
      session_token: 'shard-pyro-1',
      game_running: true,
      flight: {
        state: 'IN_FLIGHT',
        active_ship: 'Drake Corsair',
        active_mfg: 'Drake',
        active_color: '#c2a649',
        active_helm_s: 425,
        active_boarded_s: 510,
        active_jumps: 3,
        active_contracts: 1,
        active_route: 'Checkmate Station',
        jurisdiction: 'Ungoverned',
        monitored: false,
        entitlements: 12,
        total_sorties: 4,
        total_helm_s: 7400,
        total_jumps: 14,
        total_contracts: 6,
        total_losses: 1,
        fleet: [
          {
            name: 'Drake Corsair',
            mfg: 'Drake',
            color: '#c2a649',
            sorties: 3,
            seconds: 5400,
            jumps: 10,
            contracts: 4,
            losses: 0,
            pct: 73,
          },
          {
            name: 'RSI Mantis',
            mfg: 'RSI',
            color: '#62ccff',
            sorties: 1,
            seconds: 2000,
            jumps: 4,
            contracts: 2,
            losses: 1,
            pct: 27,
          },
        ],
        recent: [
          {
            ship: 'Drake Corsair',
            mfg: 'Drake',
            color: '#c2a649',
            duration_s: 1800,
            jumps: 4,
            contracts: 2,
            destination: 'Monox',
            incident: '',
            reason: 'Landed & Disembarked',
            time: '12:10',
          },
          {
            ship: 'RSI Mantis',
            mfg: 'RSI',
            color: '#62ccff',
            duration_s: 2000,
            jumps: 4,
            contracts: 2,
            destination: 'Bloom Orbit',
            incident: 'Fatal Collision',
            reason: 'Hull Destroyed (Collision)',
            time: '11:05',
          },
        ],
      },
      piracy_watch: {
        waiting_s: 95,
        waiting_active: true,
        pulls: [
          {
            id: 'pull-seed',
            at: 1700000000,
            target: 'Crusader C2 Hercules',
            lane: 'Monox -> Checkmate',
            outcome: 'catch',
            value_uec: 3200000,
            notes: 'Gold + RMC',
          },
        ],
        pull_stats: {
          total: 1,
          catches: 1,
          hit_rate: 100,
          total_loot_uec: 3200000,
        },
      },
    },
  });

  const controller = new DesktopAppController(root, bridge);
  const checks: Record<string, boolean> = {};
  const details: Record<string, string> = {};

  const piracySection = root.querySelector('#ss-view-piracy') as HTMLElement | null;
  checks.mode_mounted_and_visible = Boolean(piracySection && !piracySection.hidden);

  const shipEl = root.querySelector('#piracy-active-ship') as HTMLElement | null;
  const jurisEl = root.querySelector('#piracy-juris-badge') as HTMLElement | null;
  const routeEl = root.querySelector('#piracy-active-route') as HTMLElement | null;
  checks.telemetry_rendered = Boolean(
    shipEl?.textContent?.includes('Drake Corsair') &&
      jurisEl?.textContent?.includes('UNGOVERNED') &&
      routeEl?.textContent?.includes('Checkmate Station'),
  );

  // Donut circles & fleet bar buttons rendered
  const donutSvg = root.querySelector('#piracy-fleet-donut')!;
  const donutCircles = donutSvg.querySelectorAll('circle');
  const fleetBtns = Array.from(root.querySelectorAll<HTMLButtonElement>('button[data-hull-name]'));
  checks.fleet_svg_and_bars_rendered = donutCircles.length === 2 && fleetBtns.length === 2;

  // Hull filter click narrows sorties table to RSI Mantis
  const mantisBtn = fleetBtns.find((b) => b.dataset.hullName === 'RSI Mantis');
  mantisBtn?.click();
  const sortiesTbody = root.querySelector('#piracy-sorties-tbody')!;
  const filteredSortieRows = sortiesTbody.querySelectorAll('tr');
  checks.hull_filter_updates_sorties =
    filteredSortieRows.length === 1 && (filteredSortieRows[0].textContent ?? '').includes('RSI Mantis');
  // Toggle off
  mantisBtn?.click();

  // Subview switching works (Flight first, Piracy second)
  const flightDeck = root.querySelector('#piracy-section-flight') as HTMLElement | null;
  const piracyDeck = root.querySelector('#piracy-section-piracy') as HTMLElement | null;
  const flightDefaultOk = Boolean(flightDeck && !flightDeck.hidden && piracyDeck?.hidden);
  const piracyBtn = root.querySelector('button[data-piracy-subtab="piracy"]') as HTMLButtonElement | null;
  piracyBtn?.click();
  const piracySwitchOk = Boolean(flightDeck?.hidden && piracyDeck && !piracyDeck.hidden);
  checks.subview_switch_works = flightDefaultOk && piracySwitchOk;

  // Verify jurisdiction badge on Piracy tab
  checks.telemetry_rendered = Boolean(
    checks.telemetry_rendered && jurisEl?.textContent?.includes('UNGOVERNED'),
  );

  // Pure calculator sanity (SnarePlan-style coverage & no QT drive dependency)
  const geomOk = calculateSnareGeometry({
    laneDistanceMkm: 20,
    offsetMkmFromDest: 1.5,
    doglegKm: 4,
    qedRadiusKm: 20,
  });
  const geomMiss = calculateSnareGeometry({
    laneDistanceMkm: 20,
    offsetMkmFromDest: 1.5,
    doglegKm: 25,
    qedRadiusKm: 20,
  });
  checks.snare_geometry_math =
    geomOk.inRange && geomOk.coveragePct === 100 && !geomMiss.inRange && geomMiss.coveragePct === 0;

  // /showlocation GPS parser & 3D spline verification
  const originPt = parseShowLocationText('Coordinates: x:0 y:0 z:0');
  const destPt = parseShowLocationText('Coordinates: x:10000000000 y:0 z:0'); // 10 Mkm
  const shipPt = parseShowLocationText('Coordinates: x:9000000000 y:3000 z:0'); // 1 Mkm from dest, 3 km off-axis
  const gpsIntercept =
    originPt && destPt && shipPt ? calculateGpsIntercept(originPt, destPt, shipPt, 20) : null;
  checks.gps_showlocation_math = Boolean(
    gpsIntercept &&
      gpsIntercept.inRange &&
      gpsIntercept.lateralOffsetKm === 3 &&
      gpsIntercept.offsetMkmFromDest === 1 &&
      gpsIntercept.coveragePct === 100,
  );

  const split = calculateCrewSplit({
    totalLootAuec: 2_000_000,
    crewCount: 4,
    snareBonusPct: 10,
    fenceFeePct: 0,
  });
  // Bonus = 200k; evenPool = 1.8M / 4 = 450k -> snare = 650k, crew = 450k
  checks.crew_splitter_math = split.snareShareAuec === 650_000 && split.crewMemberShareAuec === 450_000;

  // Removed targetDriveSpeedKms dropdown & Prey Recon card
  checks.removed_obsolete_panels =
    !root.querySelector('#piracy-qtdrive-select') && !root.querySelector('#piracy-prey-select');

  // Wait timer command + log pull command + delete pull command
  const toggleWaitBtn = root.querySelector('#piracy-wait-toggle-btn') as HTMLButtonElement | null;
  toggleWaitBtn?.click();
  const logPullBtn = root.querySelector('#piracy-pull-log-btn') as HTMLButtonElement | null;
  logPullBtn?.click();
  await Promise.resolve();

  const pullsTbody = root.querySelector('#piracy-pulls-tbody')!;
  const pullRowsAfterAdd = pullsTbody.querySelectorAll('tr');
  checks.pull_logged_in_table = pullRowsAfterAdd.length === 2;

  const deleteBtns = Array.from(root.querySelectorAll<HTMLButtonElement>('button[data-delete-pull]'));
  const addedDeleteBtn = deleteBtns.find((b) => b.dataset.deletePull !== 'pull-seed');
  addedDeleteBtn?.click();
  await Promise.resolve();
  const pullRowsAfterDelete = pullsTbody.querySelectorAll('tr');
  checks.pull_deleted_from_table = pullRowsAfterDelete.length === 1;

  checks.commands_sent =
    bridge.commands.some((c) => c.action === 'piracy_toggle_wait') &&
    bridge.commands.some((c) => c.action === 'piracy_log_pull') &&
    bridge.commands.some((c) => c.action === 'piracy_delete_pull');

  controller.destroy();

  for (const [k, v] of Object.entries(checks)) {
    details[k] = v ? 'ok' : 'failed';
  }
  const passed = Object.values(checks).every(Boolean);
  return { passed, checks, details };
}
