# Showing the HUD in a screen share

SynthScan's server ribbon, mining/activity HUD, HUD +/- controls, and region
history windows allow Windows screen capture, including while live mining scans
run. They are separate windows placed above the game.

In Discord, share the screen/monitor containing Star Citizen to include these
windows. Sharing only the Star Citizen application can omit external overlays.
See [Discord's overlay capture explanation](https://support.discord.com/hc/en-us/articles/25289844838551--Known-Issue-Game-Overlay).

This does not change SynthScan's OCR capture scope. Windows readers capture the
verified StarCitizen.exe game-window surface, without a desktop fallback. The
signature search uses a central aim region and tracking margin scaled by the
game viewport's height. Other mining and terminal readers can inspect a larger
part of that game surface to find their panels. Separate SynthScan HUD windows
are not pixels on the game's own capture surface.

The piracy jurisdiction badge shows game-log notifications. A change to a
different named jurisdiction clears the previous monitoring status until a new
monitoring notification arrives. “Ungoverned” is the jurisdiction name; it does
not establish absent monitoring or predict CrimeStat, faction hostility, or
station reactions. Armistice notices are tracked independently. CIG describes
law enforcement as depending on monitoring and the controlling faction in its
[Crime Rating guide](https://support.robertsspaceindustries.com/hc/en-us/articles/360008162913-Crime-Rating).
