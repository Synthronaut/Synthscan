# Organization distribution and updates

Distribute the guided Windows installer from a versioned GitHub release of
Synthronaut/Synthscan. Each person installs once and selects their game folder.
Records, credentials and caches remain in their Windows profile, outside the app.

## Automatic reference updates

The installed game build is checked automatically. Outdated local catalogs rebuild
using the bundled pinned extractor after Star Citizen closes. Complete generations
publish atomically; failures retain the previous catalog. Item directory and Finder
reload without restarting SynthScan.

SCMDB public JSON is checked every six hours, with five-minute failure retries.
The installed version, build and LIVE/PTU channel must match exactly. Blueprint
mission sources and default unlock flags match by blueprint UUID. Numeric mining
head/module/gadget stats are validated against supported engine identities and
applied between scans. New equipment identities or changed calculations need an
app release. Missing exact-build data is reported as not published.

Recipes and material quality requirements come from local game records. Finder
shows recipes plus unlock missions when ownership is unrecorded or inferred.
Confirmed log/manual ownership hides unlock missions and retains materials.
Reward pools are labelled as pools rather than guaranteed rewards.

UEX retail prices use exact item UUIDs and a 24-hour cache. Vehicle indexing and
purchase prices use exact UEX identities and a 12-hour cache. Background lookups
retain cached results offline and show source patch/date and refresh age.
Pledge and rental prices are excluded.

Executive Hangar timing checks and official reset checks remain independent of
the selected HUD mode. Status exposes freshness and verification; an unavailable
source does not manufacture a new synchronization timestamp.

## Signed application updates

Packaged installations check a signed manifest every six hours and stage a full
Windows x64 package in the background. Development checkouts do not replace source
files. Data updates provides an automatic-app-update toggle and separate
checked/staged/applied/deferred/rollback states.

update_trust.json pins the release public key and HTTPS hosts. ECDSA P-256,
expiry, monotonic sequence, platform/schema, size bounds, SHA-256, safe archive
paths and complete package integrity are checked before activation. The signing
private key is never distributed. This is separate from Windows Authenticode.

Activation waits until Star Citizen and guided setup are closed and SynthScan
has no active desktop windows. A detached bundled runtime stops the watcher and
helpers, extracts a version directory, switches the stable launcher, and checks
native readiness. Failure restores the previous version; interrupted activation
recovers on the next launch. Profiles remain outside the app. SynthScan never
closes the game to install an update.

## Publishing a release

Clients cannot receive an unpublished release. The stable channel is
https://github.com/Synthronaut/Synthscan/releases/download/update-channel/synthscan-update.json.

1. Build and test a clean ZIP and installer as described in BUILDING.md. Bump the
   version for each release. Never publish the workspace or local profile.
2. Sign the ZIP with tools/sign_release.py, targeting its immutable versioned
   release URL. Local signing uses the DPAPI-protected key outside this repository;
   CI uses the matching SYNTHSCAN_SIGNING_PRIVATE_B64 secret. Keep an encrypted
   private backup under the repository owner's control.
3. Publish versioned ZIP, installer and checksums first; promote the signed
   manifest to update-channel after those assets are available. Never replace an
   already published versioned application package.
4. The Windows workflow defaults to artifact-only builds. Its explicit publish
   input uses the community-release environment. Configure required reviewers
   there if the organization wants an approval gate.

Each recipient needs this initial installer once. Older installations without the
updater also need it once. Future compatible app releases and reference updates
then require no manual download.

GitHub Releases is sufficient; Oracle Ampere hosting is optional. A future host
migration needs a trusted channel configuration update while the current host is
still available. ARM hosting does not change the Windows x64 client.

## Sources

- [SCMDB public version index](https://scmdb.net/data/versions.json)
- [UEX item prices](https://uexcorp.space/api/documentation/id/get_items_prices/)
- [UEX ship purchase prices](https://uexcorp.space/api/documentation/id/get_vehicles_purchases_prices/)
- [GitHub releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
