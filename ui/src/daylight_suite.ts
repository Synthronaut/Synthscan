import { DaylightViewController } from './daylight_view';
import { InMemoryDesktopBridge } from './bridge';

export interface DaylightSuiteResult {
  passed: boolean;
  initial_system_stanton: boolean;
  initial_body_crusader: boolean;
  initial_site_orison: boolean;
  body_change_updates_sites: boolean;
  system_switch_to_pyro: boolean;
  poi_filter_works: boolean;
  arrival_mode_switch_works: boolean;
  solar_forecast_rendered: boolean;
  daylight_timeline_rendered: boolean;
  preference_command_sent: boolean;
  observation_modal_flow_works: boolean;
  failures: string[];
}

export async function runDaylightRegressionSuite(root: HTMLElement): Promise<DaylightSuiteResult> {
  const failures: string[] = [];
  const bridge = new InMemoryDesktopBridge();
  const controller = new DaylightViewController(root, bridge);

  // 1. Initial system
  const initialSystem = root.querySelector('.ss-system-pill.is-active')?.textContent?.trim();
  const initialSystemStanton = initialSystem === 'Stanton';
  if (!initialSystemStanton) failures.push(`Initial system expected Stanton, got: ${initialSystem}`);

  // 2. Initial body & site
  const bodySelect = root.querySelector<HTMLSelectElement>('#dl-body-select');
  const initialBodyCrusader = bodySelect?.value === 'Crusader';
  if (!initialBodyCrusader) failures.push(`Initial body expected Crusader, got: ${bodySelect?.value}`);

  const siteSelect = root.querySelector<HTMLSelectElement>('#dl-site-select');
  const initialSiteOrison = siteSelect?.value === 'Orison';
  if (!initialSiteOrison) failures.push(`Initial site expected Orison, got: ${siteSelect?.value}`);

  // 3. Changing body updates sites
  let bodyChangeUpdatesSites = false;
  if (bodySelect && siteSelect) {
    bodySelect.value = 'Hurston';
    bodySelect.dispatchEvent(new Event('change', { bubbles: true }));
    bodyChangeUpdatesSites = siteSelect.value === 'Lorville';
    if (!bodyChangeUpdatesSites) {
      failures.push(`Changing body to Hurston expected Lorville default, got: ${siteSelect.value}`);
    }
  }

  // 4. Initial forecast rendered
  const statusTag = root.querySelector('.ss-hero-status-tag')?.textContent?.trim();
  const solarForecastRendered = Boolean(statusTag && (statusTag.includes('DAYLIGHT') || statusTag.includes('NIGHT')));
  if (!solarForecastRendered) failures.push('Solar status tag not rendered in hero section');

  // 5. Timeline SVG rendered
  const timelineSvg = root.querySelector('.ss-timeline-svg');
  const daylightTimelineRendered = Boolean(timelineSvg);
  if (!daylightTimelineRendered) failures.push('Timeline SVG not found in DOM');

  // 6. Switch system to Pyro
  const pyroPill = root.querySelector<HTMLButtonElement>('.ss-system-pill[data-sys="Pyro"]');
  if (pyroPill) {
    pyroPill.click();
  }
  const activeSys = root.querySelector('.ss-system-pill.is-active')?.textContent?.trim();
  const systemSwitchToPyro = activeSys === 'Pyro';
  if (!systemSwitchToPyro) failures.push(`System switch to Pyro failed, active is: ${activeSys}`);

  // Check preference command was sent
  const preferenceCommandSent = bridge.commands.some(
    (c) => c.action === 'daylight_preferences' && c.system === 'Pyro',
  );
  if (!preferenceCommandSent) failures.push('daylight_preferences command not recorded on system switch');

  // Switch back to Stanton for POI testing
  const stantonPill = root.querySelector<HTMLButtonElement>('.ss-system-pill[data-sys="Stanton"]');
  if (stantonPill) stantonPill.click();

  // 7. POI Filter (Universal Verse Search)
  const searchInput = root.querySelector<HTMLInputElement>('#dl-poi-search');
  if (searchInput) {
    searchInput.focus();
    searchInput.value = 'Orison';
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
  }
  const dd = root.querySelector<HTMLElement>('#dl-poi-dropdown');
  const poiFilterWorks = Boolean(dd && !dd.hidden && dd.innerHTML.includes('Orison'));
  if (!poiFilterWorks) failures.push('Destination search dropdown failed to filter matching items');

  // 8. Arrival mode switch
  const minTab = root.querySelector<HTMLButtonElement>('.ss-tab-pill[data-arr="minutes"]');
  if (minTab) minTab.click();
  const minutesRow = root.querySelector<HTMLElement>('#dl-minutes-row');
  const arrivalModeSwitchWorks = Boolean(minutesRow && !minutesRow.hidden);
  if (!arrivalModeSwitchWorks) failures.push('Minutes arrival options row not visible after mode switch');

  // 9. Observation modal flow
  const observeBtn = root.querySelector<HTMLButtonElement>('#dl-observe-btn');
  if (observeBtn) observeBtn.click();
  const modal = root.querySelector<HTMLElement>('#dl-observe-modal');
  const modalOpened = Boolean(modal && !modal.hidden);

  const saveBtn = root.querySelector<HTMLButtonElement>('#dl-modal-save-btn');
  if (saveBtn) saveBtn.click();

  const observationCommandSent = bridge.commands.some(
    (c) => c.action === 'daylight_observe' && c.kind === 'sunrise',
  );
  const observationModalFlowWorks = modalOpened && observationCommandSent;
  if (!observationModalFlowWorks) {
    failures.push(`Observation modal flow failed: opened=${modalOpened}, commandSent=${observationCommandSent}`);
  }

  controller.destroy();

  return {
    passed: failures.length === 0,
    initial_system_stanton: initialSystemStanton,
    initial_body_crusader: initialBodyCrusader,
    initial_site_orison: initialSiteOrison,
    body_change_updates_sites: bodyChangeUpdatesSites,
    system_switch_to_pyro: systemSwitchToPyro,
    poi_filter_works: poiFilterWorks,
    arrival_mode_switch_works: arrivalModeSwitchWorks,
    solar_forecast_rendered: solarForecastRendered,
    daylight_timeline_rendered: daylightTimelineRendered,
    preference_command_sent: preferenceCommandSent,
    observation_modal_flow_works: observationModalFlowWorks,
    failures,
  };
}
