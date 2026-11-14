# Missions HUD — 2026-10-22

Open the activity HUD with **HUD +** on the server ribbon, then select
**Missions** beside Mining and Piracy. **Next** cycles the observed active
contracts. It defaults to the latest accepted contract; it does not yet follow
the contract selected for tracking in mobiGlas. The current mode is saved.

Missions pauses the mining scanner and diary observations. Returning to Mining
restores its previous scan setting. Dragging, locking, collapsing and the server
ribbon work as before. Organization-name reputation annotations are unchanged.

## Data and refresh

- Game.log acceptance notifications supply the contract name and mission ID.
  Objective-marker events link that ID to a contract definition. New-objective
  and EndMission events update the observation. Abandonment is not completion;
  repeated notification presentations do not award anything.
- The authenticated read-only MissionService is queried only for the current
  locally signed-in character. Mission detail records must match its returned
  IDs and explicitly include that character as a participant.
- While Missions is selected, account reads run in a background worker every
  30 seconds, with an earlier refresh after contract events. Reputation comes
  from the verified own-character ReputationService. Estimated rewards are
  never added to the balance. Expired credentials and unavailable reads are
  displayed as unavailable; the last saved snapshot is preserved.
- Current-build configuration covers 1,801 older mission entries and 2,155
  embedded career contracts. Career completion rewards use the same result-slot
  convention as the preserved native contract generator. Definitions are base
  estimates, not proof of a particular payout. Dynamic cash rewards remain
  unknown until a supported runtime source supplies them.
- Participant counts come from the mission service, not the general party
  roster. Equal-split figures are explicitly hypothetical; actual sharing rules,
  eligibility, bonuses, modifiers and individual contribution still need field
  verification. An unknown participant count produces no split figure.

The existing game-name annotations remain a saved localization snapshot and
require a game text reload. HUD refreshes do not rewrite game localization.

## Verified evidence

The real log linked `Retrieve Additional Smuggler Intel` to definition
`4f735fe1-caec-4c9d-acba-606d8e096ba6`. The current career definition resolves
that to InterSec Defense Solutions / Standing, 100 base reputation and blueprint
rewards. The observed ending was **Abandon**. No reputation was credited locally.

The live read-only integration check returned 18 verified own-character balances
and zero active service missions. This validates account access, not every field
of a live accepted/completed mission. A full live completion and its reward split
have not been validated yet.

Verification artifacts:

- `research/questing_live_verification_20261022.json`
- `research/questing_final_ui_20261022/ui_test.json`
- `research/questing_ribbon_20261022/`
- `research/questing_deployment_20261022.json`

New source extraction:

```powershell
third_party/starbreaker/v0.3.2/starbreaker.exe dcb extract --dcb research/local_game_12913470/archive/Data/Game2.dcb --output research/questing_definitions_12913470 --format json --filter '**/contracts/**'
```

Service schemas were parsed from the installed executable using
`tools.inspect_game_schema.iter_descriptors`, saved as a protobuf FileDescriptorSet
in `research/game_services.pb`, and stamped with the build ID in
`research/game_services_manifest.json`. A changed game build stops service reads
and configured reward mapping until the reference data is refreshed. No token is
saved in those artifacts. Runtime service dependencies are pinned in
`requirements-services.txt`; the current Windows grpc runtime is stored in
`third_party/python_services`, independently of temporary research packages.
