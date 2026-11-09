# SynthScan interface standards

SynthScan is a polished companion for players. Setup must feel like part of the
app, not a generic Windows utility. These rules apply to future UI work.

- Use the existing deep navy, translucent blue surfaces, cyan accents and
  restrained amber capability notices. Rounded cards, generous spacing and
  clear typography create hierarchy. Avoid harsh blue selection blocks.
- Lead with what helps the player. Use short headings and one or two sentences
  per feature. Put technical details behind optional help. No walls of text.
- Feature selection uses large clickable cards with unmistakable included/off
  states. The whole card works, including its text. Keep keyboard navigation
  and accessible text. Do not use a tiny stock checklist as the main interface.
- Size onboarding generously for the display, without covering the taskbar or
  clipping at smaller resolutions/high DPI. Break long selections into clear
  groups if necessary. Body text must be comfortably readable.
- Use Bahnschrift for display headings where available and Segoe UI for body
  text. Use icons purposefully; do not substitute emoji for the brand system.
- Explain screen reading with a visible amber eye/scan badge: it reads the game
  window locally, does not upload frames, pauses on focus loss by default, and
  is optional. Describe implemented protections. Never promise absolute safety,
  OS sandboxing, independent certification or zero Windows warnings.
- No analytics consent flow or usage beacon. GitHub download counts suffice.
- Do not change a working HUD's design incidentally during a functional fix.
  A redesign must follow the user's current request.
- Test installers must have separate folders, profiles, shortcuts and uninstall
  identities. Block game-text/permission changes in that test mode. Never seed
  a test with the real player's records without an explicit request.
- Verify actual rendered layout and interaction, not just source or compilation.
  Stop UI input immediately when the user stops computer control.
