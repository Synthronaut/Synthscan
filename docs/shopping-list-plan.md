# Finder shopping list proposal

Status: researched proposal, not an implemented cart or navigation feature.
Checked 8 November 2026 against UEX documentation, public API responses and the
installed Star Citizen 4.10.2 records. No purchases or game input were performed.

## Intended experience

Add ships, components, magazines, armor and other retail items from Finder to a
persistent list. Set quantities and an optional starting system, city or station.
An embedded Shopping list view shows destination cards, shops, items and quantities
at each stop, line totals and an estimated purchase total. Mark items bought
manually and recalculate the remaining list. Keep everything in the same window.

Favorites and shopping are separate intentions. Do not silently convert existing
favorites into purchases. The redundant material/blueprint shortcuts can be
removed now; recipe information already appears in item details. The eventual
main shopping action should say “Add to shopping list.”

## Available data

UEX provides exact item UUID lookups and vehicle purchase prices linked to terminal
IDs. Its terminal catalog has stable IDs for system, planet, orbit, city, station,
outpost and POI, plus availability and player-owned flags. Purchase quantities
must use the actual sellable unit, such as one magazine rather than one round.

Our shop cache keeps terminal IDs but flattens the location hierarchy into display
text. A cart must retain structured IDs and join to the terminal catalog, rather
than reconstruct geography by parsing names. Refresh this catalog off-thread,
respecting documented cache limits.

A live sample returned two M2 listings in Stanton: terminal 112 at the Orison
Crusader showroom and terminal 149 at Lorville’s Teasa Spaceport, at different
prices. Thus system, planet, landing destination and shop are distinct levels.
This sample is not a completed shopping itinerary and does not prove live stock.
The terminal catalog query returned 826 records; availability still needs checking
for each candidate, and catalog presence does not establish shard stock.

Sources:

- [Item purchase prices](https://uexcorp.space/api/documentation/id/get_items_prices/)
- [Vehicle purchase prices](https://uexcorp.space/api/documentation/id/get_vehicles_purchases_prices_all/)
- [Terminals and geographic IDs](https://uexcorp.space/api/documentation/id/get_terminals/)
- [Star systems and availability](https://uexcorp.space/api/documentation/id/get_star_systems/)

## Recommendation policy

1. Preserve exact item identity and quantity. No automatic substitutions. Show
   unavailable lines explicitly; never drop them to make a trip look complete.
   Prefer current-patch reports and label older or unknown reports.
2. Default to a complete plan within the starting system when possible. A cheaper
   trip elsewhere is an alternative. Offer “Stay in this system” as a hard
   constraint. If local coverage is incomplete, show missing items and a complete
   cross-system alternative.
3. Optimize the whole list. Start with items sold at only one destination, then
   exploit overlap. Choosing each item’s cheapest shop independently can create
   many unnecessary stops.
4. Count a city or station as a landing stop, with shops beneath it. Two shops at
   one destination are not two spaceflight stops. A city and its orbiting station
   remain separate, and a planet is not one landing stop. Do not merge aliases
   unless canonical location IDs support the merge.
5. Rank travel burden before small price savings: system crossings, landing
   stops and planetary backtracking. Use the starting location and show why the
   plan was chosen: “All 8 items · Stanton only · 2 landing stops · 3 shops.”
6. Show a few deduplicated alternatives: Recommended, Fewest stops and Lowest
   listed cost. Include cost differences and added stops or system crossings.

Do not hide an arbitrary aUEC-to-minutes conversion inside a score. Initially,
compare verified geography and stop counts without inventing travel times.
Precise leg ordering needs verified coordinates, a reachable jump graph and a
travel model beyond straight-line distance. The game map remains the flight
navigator. State when a distant stop order cannot be resolved.

## Implementation approach

- Persist exact item or UEX vehicle identity, quantity and manual bought/skipped
  state. Track quote time, patch and cart revision so late results cannot replace
  newer selections.
- Reuse background shop lookups. Keep all valid destinations, not just the
  cheapest one. Enrich terminal IDs with the geographic hierarchy.
- Represent destinations as item-coverage sets. Use branch-and-bound and bit
  masks for small carts, beginning with mandatory stops. Retain alternatives for
  purchase cost and travel burden. Bound large searches and call heuristic
  results “Suggested trip” when global optimality is not established.
- Assign each line to a shop within the selected destinations, respecting unit
  and quantity semantics. Then order destinations using verified location data.
  Set cover alone does not calculate the fastest route.
- Recalculate remaining purchases while retaining stable cards and scroll
  position. Preserve the cart offline and label cached price estimates.

## Version-one boundaries

Start with NPC retail. A player-market advertisement is not a confirmed meeting
point or an executable guaranteed price. Keep player listings visible separately;
do not route them as permanent stores. Quality-specific materials and crafting
ingredient shopping can be later explicit workflows.

This is an acquisition planner, not a ship build simulator. Mount summaries help
users know quantities and sizes; they do not replace Erkul, validate arbitrary
builds, or automatically purchase or equip items.

## Release checks

Test overlapping coverage, unique mandatory stops, local-system preference,
cross-system alternatives, city/station separation, aliases, quantities, missing
geography, stale patches, missing prices, partial availability, late lookup
results, offline persistence and duplicate additions. Benchmark realistic large
carts and verify compact and maximized layouts.

First milestone: persistent list and complete purchase options. Next: destination
consolidation and alternatives. Then: reliable destination ordering.
