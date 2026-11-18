import { InMemoryDesktopBridge, type KnickKnackItem } from './bridge';
import { DesktopAppController } from './people_controller';
import { filterAndSortItems } from './knick_knacks_view';

export interface KnickKnacksSuiteReport {
  passed: boolean;
  checks: Record<string, boolean>;
}

export async function runKnickKnacksRegressionSuite(
  root: HTMLElement,
): Promise<KnickKnacksSuiteReport> {
  const sampleItems: KnickKnackItem[] = [
    {
      crc: 1001,
      name: 'FR-76',
      category: 'ship_components',
      category_label: 'Ship Components',
      sub_type: 'Shield',
      manufacturer: 'Gorgon Defender Industries',
      size: 2,
      grade: 1,
      is_wikelo: false,
      is_crafting: false,
      is_comp_board: false,
      is_ship_component: true,
      location_id: '848868938',
      location_name: 'Orbituary',
      system: 'Pyro',
      storage_kind: 'location',
      container: 'Local Storage',
      quantity: 3,
    },
    {
      crc: 1002,
      name: 'Carinite',
      category: 'mining_crafting',
      category_label: 'Mining & Crafting',
      sub_type: 'Raw resource',
      manufacturer: '',
      size: 1,
      grade: 1,
      is_wikelo: true,
      is_crafting: true,
      is_comp_board: false,
      is_ship_component: false,
      quality_tiers: [
        { quality: 959, units: 10, uscu: 10000, scu: 0.01 },
        { quality: 647, units: 28, uscu: 28000, scu: 0.028 },
      ],
      total_uscu: 38000,
      total_scu: 0.038,
      max_quality: 959,
      min_quality: 647,
      location_id: '848868938',
      location_name: 'Orbituary',
      system: 'Pyro',
      storage_kind: 'location',
      container: 'Local Storage',
      quantity: 38,
    },
    {
      crc: 1005,
      name: 'CQ7 Rifle',
      category: 'gear_weapons',
      category_label: 'FPS Gear & Weapons',
      sub_type: 'WeaponPersonal',
      manufacturer: 'Behring',
      size: null,
      grade: null,
      is_wikelo: false,
      is_crafting: false,
      is_comp_board: false,
      is_ship_component: false,
      is_crafted: true,
      crafted_quality: 900,
      crafted_ingredients: [
        { name: 'Aluminum', quality: 896, amount: 60000 },
        { name: 'Iron', quality: 907, amount: 10000 },
      ],
      location_id: '848868938',
      location_name: 'Orbituary',
      system: 'Pyro',
      storage_kind: 'location',
      container: 'Local Storage',
      quantity: 1,
    },
    {
      crc: 1003,
      name: 'DCHS-05 Orbital Positioning Comp-Board',
      category: 'comp_boards',
      category_label: 'Comp Boards & Keys',
      sub_type: 'RemovableChip',
      manufacturer: '',
      size: 1,
      grade: 1,
      is_wikelo: true,
      is_crafting: false,
      is_comp_board: true,
      is_ship_component: false,
      location_id: '3170699229',
      location_name: 'New Babbage',
      system: 'Stanton',
      storage_kind: 'hangar',
      container: 'Persistent Hangar',
      quantity: 5,
    },
    {
      crc: 1004,
      name: 'MG <script>Scrip',
      category: 'wikelo',
      category_label: 'Wikelo Turn-Ins',
      sub_type: 'Currency',
      manufacturer: '',
      size: 1,
      grade: 1,
      is_wikelo: true,
      is_crafting: false,
      is_comp_board: false,
      is_ship_component: false,
      location_id: '3170699229',
      location_name: 'New Babbage',
      system: 'Stanton',
      storage_kind: 'location',
      container: 'In Pembroke Backpack',
      quantity: 278,
    },
  ];

  const bridge = new InMemoryDesktopBridge({
    mode: 'knick_knacks',
    session: 'shard',
    players: [],
    knick_knacks: {
      schema: 1,
      status: 'ok',
      message: 'Synced',
      syncing: false,
      updated_at: Date.now() / 1000 - 15,
      mounted_excluded_count: 142,
      total_quantity: 324,
      unique_items: 4,
      locations: [
        { id: '848868938', name: 'Orbituary', system: 'Pyro', unique: 2, quantity: 41 },
        { id: '3170699229', name: 'New Babbage', system: 'Stanton', unique: 2, quantity: 283 },
      ],
      category_counts: {
        all: 325,
        crafted: 1,
        ship_components: 3,
        mining_crafting: 38,
        wikelo: 321,
        comp_boards: 5,
        gear_weapons: 1,
        other: 0,
      },
      items: sampleItems,
      account_counts: {
        all: 3,
        rsi_hangar: 2,
        ingame_ltp: 1,
        ships: 2,
        paints: 1,
        ship_components: 0,
        gear_weapons: 0,
        flair: 0,
      },
      account_items: [
        {
          crc: 9001,
          name: 'Crusader C1 Spirit',
          category: 'ships',
          category_label: 'Ships & Vehicles',
          sub_type: 'Ship / Vehicle',
          manufacturer: 'Crusader',
          size: null,
          grade: null,
          source_kind: 'rsi_hangar',
          source_label: 'RSI Hangar',
          status_label: 'Delivered',
          real_money: true,
          quantity: 1,
        },
        {
          crc: 9002,
          name: 'Spirit 2954 Best in Show Livery',
          category: 'paints',
          category_label: 'Paints & Liveries',
          sub_type: 'Paint',
          manufacturer: '',
          size: null,
          grade: null,
          source_kind: 'rsi_hangar',
          source_label: 'RSI Hangar',
          status_label: 'In Hangar (Unclaimed)',
          real_money: true,
          quantity: 1,
        },
        {
          crc: 9003,
          name: 'RSI Meteor Wikelo',
          category: 'ships',
          category_label: 'Ships & Vehicles',
          sub_type: 'Ship / Vehicle',
          manufacturer: 'RSI',
          size: null,
          grade: null,
          source_kind: 'ingame_ltp',
          source_label: 'In-Game Persistent (LTP)',
          status_label: 'Delivered',
          real_money: false,
          quantity: 1,
        },
      ],
      ship_counts: {
        all: 4,
        ingame_earned: 2,
        pledged: 1,
        unowned: 1,
        dealership: 1,
        wikelo: 2,
        exec_hangar: 1,
      },
      ships: [
        {
          crc: 101,
          name: 'Aegis Eclipse',
          company: 'Aegis Dynamics',
          role: 'Bomber',
          owned: true,
          ownership: 'ingame_earned',
          ownership_label: 'Earned In-Game',
          channel: 'dealership',
          channel_label: 'In-Game Dealership',
          price_auec: 7541100,
          dealer_label: 'New Deal Lorville',
          recipe: '',
          scu: 0,
          quantity: 1,
        },
        {
          crc: 104,
          name: 'Mirai Guardian MX Wikelo War Special',
          company: 'Mirai',
          role: 'Combat',
          owned: true,
          ownership: 'ingame_earned',
          ownership_label: 'Earned In-Game',
          channel: 'exec_hangar',
          channel_label: 'Executive Hangar',
          also_wikelo: true,
          price_auec: 0,
          dealer_label: 'PYAM-EXHANG-0-1 (Pyro)',
          recipe: 'PYAM Executive Hangar vault reward',
          scu: 0,
          quantity: 1,
        },
        {
          crc: 102,
          name: 'Crusader C1 Spirit',
          company: 'Crusader Industries',
          role: 'Cargo',
          owned: true,
          ownership: 'pledged',
          ownership_label: 'RSI Hangar (Pledged)',
          channel: 'rsi_hangar',
          channel_label: 'RSI Hangar',
          price_auec: 0,
          dealer_label: '',
          recipe: '',
          scu: 64,
          quantity: 1,
        },
        {
          crc: 103,
          name: 'Aegis Sabre Firebird Wikelo Special',
          company: 'Aegis',
          role: 'Wikelo Special',
          owned: false,
          ownership: 'unowned',
          ownership_label: 'Not Owned (Earnable)',
          channel: 'wikelo',
          channel_label: 'Wikelo Emporium',
          price_auec: 0,
          dealer_label: 'Wikelo Emporium (Dasi / Selo / Kinga)',
          recipe: '5x MG Scrip; 2x Quantanium',
          scu: 0,
          quantity: 0,
        },
      ],
    },
  });

  const controller = new DesktopAppController(root, bridge);
  const checks: Record<string, boolean> = {};

  const section = root.querySelector('#ss-view-knick-knacks') as HTMLElement | null;
  checks.mode_mounted_and_visible = Boolean(section && !section.hidden);

  const statsCount = root.querySelector('#kk-stats')!.querySelectorAll('.ss-kk-stat').length;
  checks.summary_stats_rendered = statsCount === 4;

  const tbody = root.querySelector('#kk-tbody')!;
  const initialRows = Array.from(tbody.querySelectorAll('tr'));
  checks.renders_all_items = initialRows.length === 5;
  checks.escapes_html_in_item_names = !tbody.innerHTML.includes('<script>');

  // Clicking expandable material row toggles inline quality breakdown dropdown
  const cariniteRow = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-expand-key]'))
    .find((tr) => tr.textContent?.includes('Carinite'));
  cariniteRow?.click();
  const detailRow = tbody.querySelector('tr.ss-kk-detail-row');
  checks.clicking_material_expands_quality_dropdown = Boolean(
    detailRow && detailRow.textContent?.includes('Q959') && detailRow.textContent?.includes('Q647'),
  );

  // Clicking Crafted category filters strictly crafted items
  const craftedBtn = Array.from(
    root.querySelector('#kk-category-bar')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.category === 'crafted');
  craftedBtn?.click();
  checks.crafted_category_filters_crafted_items =
    tbody.querySelectorAll('tr').length === 1 && Boolean(tbody.textContent?.includes('CQ7 Rifle'));

  // Cross-tagged item Carinite appears under both mining_crafting AND wikelo filters
  const wikeloOnly = filterAndSortItems(sampleItems, {
    query: '',
    category: 'wikelo',
    locationId: 'all',
    storageFilter: 'all',
    sort: 'qty_desc',
  });
  checks.wikelo_filter_includes_tagged_items = wikeloOnly.length === 3;

  // Clicking Wikelo category button updates table
  const wikeloBtn = Array.from(
    root.querySelector('#kk-category-bar')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.category === 'wikelo');
  wikeloBtn?.click();
  checks.category_button_filters_rows =
    Array.from(tbody.querySelectorAll('tr')).filter((tr) => !tr.classList.contains('ss-kk-detail-row')).length === 3;

  // Search filters narrowly
  const searchEl = root.querySelector('#kk-search-input') as HTMLInputElement;
  searchEl.value = 'dchs-05';
  searchEl.dispatchEvent(new Event('input', { bubbles: true }));
  checks.search_filters_rows = tbody.querySelectorAll('tr').length === 1;

  // Reset search and switch to Account Hangar tab
  searchEl.value = '';
  searchEl.dispatchEvent(new Event('input', { bubbles: true }));
  const accountTabBtn = Array.from(
    root.querySelector('#kk-view-tabs')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.tab === 'account');
  accountTabBtn?.click();
  checks.account_tab_shows_rsi_hangar_items = tbody.querySelectorAll('tr').length === 2;

  const ltpChip = Array.from(
    root.querySelector('#kk-location-chips')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.source === 'ingame_ltp');
  ltpChip?.click();
  checks.account_tab_switches_to_ltp = tbody.querySelectorAll('tr').length === 1;

  // Switch to Ships & Fleet tab, filter Unowned, and expand Wikelo recipe row
  const shipsTabBtn = Array.from(
    root.querySelector('#kk-view-tabs')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.tab === 'ships');
  shipsTabBtn?.click();
  checks.ships_tab_shows_all_ships = tbody.querySelectorAll('tr').length === 4;

  const execBtn = Array.from(
    root.querySelector('#kk-category-bar')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.category === 'exec_hangar');
  execBtn?.click();
  checks.ships_tab_exec_hangar_includes_owned =
    tbody.querySelectorAll('tr').length === 1 && Boolean(tbody.textContent?.includes('Mirai Guardian MX'));

  const wikeloShipCatBtn = Array.from(
    root.querySelector('#kk-category-bar')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.category === 'wikelo');
  wikeloShipCatBtn?.click();
  checks.ships_tab_wikelo_includes_owned_and_unowned = tbody.querySelectorAll('tr').length === 2;

  const unownedBtn = Array.from(
    root.querySelector('#kk-category-bar')!.querySelectorAll<HTMLButtonElement>('button'),
  ).find((b) => b.dataset.category === 'unowned');
  unownedBtn?.click();
  const wikeloShipRow = tbody.querySelector<HTMLTableRowElement>('tr[data-expand-key]');
  wikeloShipRow?.click();
  const shipRecipeRow = tbody.querySelector('tr.ss-kk-detail-row');
  checks.ships_tab_filters_unowned_and_expands_recipe = Boolean(
    shipRecipeRow && shipRecipeRow.textContent?.includes('5x MG Scrip'),
  );

  // Refresh button sends knick_knacks_refresh command
  const refreshBtn = root.querySelector('#kk-refresh-btn') as HTMLButtonElement;
  refreshBtn.click();
  checks.refresh_dispatches_command = bridge.commands.some((c) => c.action === 'knick_knacks_refresh');

  controller.destroy();
  const passed = Object.values(checks).every(Boolean);
  return { passed, checks };
}
