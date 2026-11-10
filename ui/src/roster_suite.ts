import { ACTION_LIMIT, InMemoryDesktopBridge, Player } from './bridge';
import { FRIEND_GREEN, PARTY_BLUE, SELF_PURPLE, personColor, tagColor } from './colors';
import { DesktopAppController, ROW_HEIGHT_PX } from './people_controller';

export interface RosterSuiteResult {
  passed: boolean;
  roster_size: number;
  initial_created_rows: number;
  heartbeat_recreated_rows: number;
  heartbeat_keeps_scroll: boolean;
  relationship_refresh_keeps_scroll: boolean;
  single_row_update_on_relationship: boolean;
  membership_insert_keeps_anchor_and_selection: boolean;
  removed_anchor_keeps_neighbour: boolean;
  filter_resets_intentionally: boolean;
  unsaved_tags_preserved: boolean;
  plain_click_toggles_in_both_lists: boolean;
  shift_range_selection_works: boolean;
  action_list_cap_enforced: boolean;
  action_list_independent_of_roster_filter: boolean;
  tag_reconciliation_updates_only_affected_rows: boolean;
  self_purple_party_blue_friend_green_priority: boolean;
  friend_and_friendly_distinct_green: boolean;
  confirmation_modal_blocks_unconfirmed_requests: boolean;
  cancel_is_default_and_resend_default_off: boolean;
  confirmed_request_sends_bounded_batch: boolean;
  resize_preserves_state_and_fits: boolean;
  unconfirmed_bridge_call_rejected: boolean;
  outgoing_live_requests_sent: number;
  failures: string[];
}

export async function runPeopleRosterRegressionSuite(
  container: HTMLElement,
): Promise<RosterSuiteResult> {
  const failures: string[] = [];
  const check = (name: string, condition: boolean): boolean => {
    if (!condition) {
      failures.push(name);
    }
    return condition;
  };

  // Build initial 500-player roster
  const makeRoster = (count: number): Player[] => {
    const list: Player[] = [];
    for (let i = 0; i < count; i++) {
      const id = `pilot-${String(i).padStart(3, '0')}`;
      const handle = `Pilot_${String(i).padStart(3, '0')}`;
      list.push({
        id,
        handle,
        tags: i % 5 === 0 ? ['Org', 'Friendly'] : ['Friendly'],
        tag: i % 5 === 0 ? 'Org, Friendly' : 'Friendly',
        is_org: i % 5 === 0,
        is_self: i === 0,
        in_party: i === 1,
        is_friend: i === 2,
        on_shard: true,
        relationship: i === 0 ? 'You' : i === 1 ? 'Party' : i === 2 ? 'Friend' : 'Shard',
      });
    }
    return list;
  };

  const initialPlayers = makeRoster(500);
  const bridge = new InMemoryDesktopBridge({
    revision: 1,
    session: 'synthetic-500-session',
    players: initialPlayers,
    action_people: [initialPlayers[1], initialPlayers[2]],
    friends_known: true,
    party_known: true,
    status: 'Synthetic 500-player regression fixture',
  });

  const controller = new DesktopAppController(container, bridge);
  const initialCreatedRows = controller.domRowCreatedCount;
  check('initial_500_rows_created', initialCreatedRows === 500);

  // 1. Relationship color priority & distinct tag greens
  const selfC = personColor({ is_self: true, in_party: true, is_friend: true });
  const partyC = personColor({ is_self: false, in_party: true, is_friend: true });
  const friendC = personColor({ is_self: false, in_party: false, is_friend: true });
  const relationshipColorsOk = check(
    'self_purple_party_blue_friend_green_priority',
    selfC.css === SELF_PURPLE.css &&
      partyC.css === PARTY_BLUE.css &&
      friendC.css === FRIEND_GREEN.css,
  );
  const distinctGreenOk = check(
    'friend_and_friendly_distinct_green',
    tagColor('Friend').css !== tagColor('Friendly').css,
  );

  // 2. Ordinary click toggles in both Roster and Action lists + Shift-click range
  const clickRow = (tr: HTMLTableRowElement | undefined, shiftKey = false): void => {
    if (!tr) return;
    const ev = new MouseEvent('click', { bubbles: true, cancelable: true, shiftKey });
    tr.dispatchEvent(ev);
  };

  clickRow(controller.getRosterRowElement('pilot-142'));
  clickRow(controller.getRosterRowElement('pilot-145'));
  let plainClickOk =
    controller.getSelectedIds().length === 2 &&
    controller.getSelectedIds().includes('pilot-142') &&
    controller.getSelectedIds().includes('pilot-145');
  // Toggle off pilot-142 with an ordinary click
  clickRow(controller.getRosterRowElement('pilot-142'));
  plainClickOk =
    plainClickOk &&
    controller.getSelectedIds().length === 1 &&
    controller.getSelectedIds()[0] === 'pilot-145';
  // Toggle pilot-142 back on
  clickRow(controller.getRosterRowElement('pilot-142'));

  // Action list ordinary click toggles
  clickRow(controller.getActionRowElement('pilot-001'));
  clickRow(controller.getActionRowElement('pilot-002'));
  plainClickOk = plainClickOk && controller.getActionSelectedIds().length === 2;
  clickRow(controller.getActionRowElement('pilot-001'));
  plainClickOk =
    plainClickOk &&
    controller.getActionSelectedIds().length === 1 &&
    controller.getActionSelectedIds()[0] === 'pilot-002';
  clickRow(controller.getActionRowElement('pilot-002'));
  plainClickOk = plainClickOk && controller.getActionSelectedIds().length === 0;
  check('plain_click_toggles_in_both_lists', plainClickOk);

  // Shift-click range selection from pilot-142 to pilot-144
  clickRow(controller.getRosterRowElement('pilot-144'), true);
  const shiftRangeOk = check(
    'shift_range_selection_works',
    controller.getSelectedIds().includes('pilot-142') &&
      controller.getSelectedIds().includes('pilot-143') &&
      controller.getSelectedIds().includes('pilot-144') &&
      controller.getSelectedIds().includes('pilot-145'),
  );

  // 3. Scroll anchor preservation across heartbeats, relationship updates, and insertions
  const targetRowIndex = 140;
  const targetScrollTop = targetRowIndex * ROW_HEIGHT_PX + 12;
  controller.setRosterScroll(targetScrollTop, 24);
  const anchorBefore = controller.getScrollAnchor();

  // Enter unsaved tag draft
  const draftInput = container.querySelector<HTMLInputElement>('#tag-draft-input')!;
  draftInput.value = 'Scout, Unsaved draft';

  const createdBeforeHeartbeats = controller.domRowCreatedCount;
  const updatedBeforeHeartbeats = controller.domRowUpdatedCount;
  for (let beat = 0; beat < 3; beat++) {
    bridge.publish({
      written_at: Date.now() / 1000,
      status: `Heartbeat ${beat}`,
    });
  }
  const heartbeatRecreated = controller.domRowCreatedCount - createdBeforeHeartbeats;
  const heartbeatUpdated = controller.domRowUpdatedCount - updatedBeforeHeartbeats;
  const anchorAfterHeartbeat = controller.getScrollAnchor();
  const heartbeatScrollOk = check(
    'heartbeat_keeps_scroll',
    heartbeatRecreated === 0 &&
      heartbeatUpdated === 0 &&
      anchorAfterHeartbeat.anchorId === 'pilot-140' &&
      anchorAfterHeartbeat.offsetWithinRow === 12 &&
      anchorAfterHeartbeat.scrollTop === anchorBefore.scrollTop,
  );

  // 4. Single-row relationship change updates only that row and keeps scroll anchor
  const playersWithRelUpdate = bridge.getSnapshot().players.map((p) =>
    p.id === 'pilot-142'
      ? { ...p, is_friend: true, relationship: 'Friend' }
      : p,
  );
  bridge.publish({ players: playersWithRelUpdate });
  const singleRowRelOk = check(
    'single_row_update_on_relationship',
    controller.lastUpdatedRowIds.length === 1 &&
      controller.lastUpdatedRowIds[0] === 'pilot-142' &&
      controller.domRowCreatedCount === createdBeforeHeartbeats,
  );
  const relScrollOk = check(
    'relationship_refresh_keeps_scroll',
    controller.getScrollAnchor().anchorId === 'pilot-140' &&
      controller.getScrollAnchor().offsetWithinRow === 12,
  );

  // 5. Insert 5 new players at the top of the roster -> anchor stays on pilot-140!
  const prepended: Player[] = [];
  for (let k = 0; k < 5; k++) {
    prepended.push({
      id: `new-joiner-${k}`,
      handle: `A_NewJoiner_${k}`,
      tags: [],
      on_shard: true,
    });
  }
  const expandedRoster = [...prepended, ...playersWithRelUpdate];
  bridge.publish({ players: expandedRoster });
  const anchorAfterInsert = controller.getScrollAnchor();
  const membershipScrollOk = check(
    'membership_insert_keeps_anchor_and_selection',
    anchorAfterInsert.anchorId === 'pilot-140' &&
      anchorAfterInsert.offsetWithinRow === 12 &&
      anchorAfterInsert.scrollTop === (140 + 5) * ROW_HEIGHT_PX + 12 &&
      controller.getSelectedIds().includes('pilot-142') &&
      controller.getSelectedIds().includes('pilot-145'),
  );

  // 6. Unsaved tag draft preserved across all refreshes
  const draftPreservedOk = check(
    'unsaved_tags_preserved',
    draftInput.value === 'Scout, Unsaved draft',
  );

  // 7. Remove the top visible anchor player (pilot-140) -> falls back to surviving neighbor (pilot-141)
  const withoutAnchor = expandedRoster.filter((p) => p.id !== 'pilot-140');
  bridge.publish({ players: withoutAnchor });
  const anchorAfterRemove = controller.getScrollAnchor();
  const removedAnchorOk = check(
    'removed_anchor_keeps_neighbour',
    anchorAfterRemove.anchorId === 'pilot-141' && anchorAfterRemove.offsetWithinRow === 12,
  );

  // 8. Tag reconciliation updates only affected rows
  await bridge.sendCommand({
    action: 'tag_many',
    player_ids: ['pilot-142', 'pilot-145'],
    label: 'Trader, Crew',
  });
  const tagReconOk = check(
    'tag_reconciliation_updates_only_affected_rows',
    controller.lastUpdatedRowIds.length === 2 &&
      controller.lastUpdatedRowIds.includes('pilot-142') &&
      controller.lastUpdatedRowIds.includes('pilot-145'),
  );

  // 9. Action list 50-person cap enforcement & filter independence
  const seventyIds = withoutAnchor.slice(10, 80).map((p) => p.id);
  await bridge.stagePlayers(seventyIds);
  const capEnforcedOk = check(
    'action_list_cap_enforced',
    controller.getActionPeople().length === ACTION_LIMIT,
  );

  // Filter roster to something that matches 0 rows; Action list must keep all 50 rows
  const searchInput = container.querySelector<HTMLInputElement>('#people-search-input')!;
  searchInput.value = 'nonexistent_handle_xyz';
  searchInput.dispatchEvent(new Event('input', { bubbles: true }));
  const filterResetOk = check(
    'filter_resets_intentionally',
    controller.getFilteredPeople().length === 0 &&
      controller.getScrollAnchor().scrollTop === 0,
  );
  const actionIndependentOk = check(
    'action_list_independent_of_roster_filter',
    controller.getActionPeople().length === ACTION_LIMIT,
  );

  // Clear filter
  const clearBtn = container.querySelector<HTMLButtonElement>('#people-clear-btn')!;
  clearBtn.click();

  // 10. Social action confirmation modal & zero unconfirmed outgoing requests
  const commandsBeforeModal = bridge.commands.filter(
    (c) => c.action === 'party_many' || c.action === 'friend_many',
  ).length;
  const inviteBtn = container.querySelector<HTMLButtonElement>('#invite-party-btn')!;
  inviteBtn.click();
  const modalOpened = controller.isModalOpen();
  const resendCheckbox = container.querySelector<HTMLInputElement>('#ss-modal-resend-checkbox')!;
  const cancelBtn = container.querySelector<HTMLButtonElement>('#ss-modal-cancel-btn')!;
  const cancelDefaultAndResendOff = check(
    'cancel_is_default_and_resend_default_off',
    modalOpened &&
      !resendCheckbox.checked &&
      container.ownerDocument.activeElement === cancelBtn,
  );
  // Cancel modal -> must not send any command
  cancelBtn.click();
  const commandsAfterCancel = bridge.commands.filter(
    (c) => c.action === 'party_many' || c.action === 'friend_many',
  ).length;
  const modalBlocksUnconfirmed = check(
    'confirmation_modal_blocks_unconfirmed_requests',
    modalOpened && !controller.isModalOpen() && commandsBeforeModal === 0 && commandsAfterCancel === 0,
  );

  // Open modal again and explicitly confirm
  inviteBtn.click();
  const confirmBtn = container.querySelector<HTMLButtonElement>('#ss-modal-confirm-btn')!;
  confirmBtn.click();
  const partyCommands = bridge.commands.filter((c) => c.action === 'party_many');
  const confirmedRequestOk = check(
    'confirmed_request_sends_bounded_batch',
    partyCommands.length === 1 &&
      partyCommands[0].confirmed === true &&
      partyCommands[0].resend === false &&
      Array.isArray(partyCommands[0].player_ids) &&
      partyCommands[0].player_ids.length <= ACTION_LIMIT,
  );

  // Verify unconfirmed direct bridge call is rejected
  let rejectedUnconfirmed = false;
  try {
    await bridge.sendCommand({
      action: 'party_many',
      player_ids: ['pilot-142'],
      confirmed: false,
    });
  } catch {
    rejectedUnconfirmed = true;
  }
  check('unconfirmed_bridge_call_rejected', rejectedUnconfirmed);

  // 11. Resize across compact, normal, and large preserves state
  controller.setRosterScroll(3200, 0);
  draftInput.value = 'Resize draft preserved';
  let resizeOk = true;
  for (const [w, h] of [
    [860, 700],
    [1240, 840],
    [1600, 1000],
  ]) {
    container.style.width = `${w}px`;
    container.style.height = `${h}px`;
    window.dispatchEvent(new Event('resize'));
    resizeOk =
      resizeOk &&
      draftInput.value === 'Resize draft preserved' &&
      controller.getActionPeople().length === ACTION_LIMIT &&
      controller.getScrollAnchor().scrollTop === 3200;
  }
  check('resize_preserves_state_and_fits', resizeOk);

  controller.destroy();

  return {
    passed: failures.length === 0,
    roster_size: 500,
    initial_created_rows: initialCreatedRows,
    heartbeat_recreated_rows: heartbeatRecreated,
    heartbeat_keeps_scroll: heartbeatScrollOk,
    relationship_refresh_keeps_scroll: relScrollOk,
    single_row_update_on_relationship: singleRowRelOk,
    membership_insert_keeps_anchor_and_selection: membershipScrollOk,
    removed_anchor_keeps_neighbour: removedAnchorOk,
    filter_resets_intentionally: filterResetOk,
    unsaved_tags_preserved: draftPreservedOk,
    plain_click_toggles_in_both_lists: plainClickOk,
    shift_range_selection_works: shiftRangeOk,
    action_list_cap_enforced: capEnforcedOk,
    action_list_independent_of_roster_filter: actionIndependentOk,
    tag_reconciliation_updates_only_affected_rows: tagReconOk,
    self_purple_party_blue_friend_green_priority: relationshipColorsOk,
    friend_and_friendly_distinct_green: distinctGreenOk,
    confirmation_modal_blocks_unconfirmed_requests: modalBlocksUnconfirmed,
    cancel_is_default_and_resend_default_off: cancelDefaultAndResendOff,
    confirmed_request_sends_bounded_batch: confirmedRequestOk,
    resize_preserves_state_and_fits: resizeOk,
    unconfirmed_bridge_call_rejected: rejectedUnconfirmed,
    outgoing_live_requests_sent: 0,
    failures,
  };
}
