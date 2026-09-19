# Emilia in-app companion design

Status: approved by user on 2026-09-16 with “start implement it”. Builds on the approved EMILIA LAB studio redesign.

## Confirmed requirements
In-app only; continuous visual analysis under an explicit toggle; local-only screenshot processing; genuine input-driven Bongo mode; roaming and expressive interactions; persistent growth and dressing; chibi roaming plus normal-proportioned zoom; independent character and clothing layers. Supplied artwork establishes character identity.

## Experience
One persistent companion overlay follows navigation without resetting. It avoids modal dialogs and the message composer. Clicking opens a compact mode/action menu; dragging repositions without triggering the click action. Roam and Bongo are direct mode choices. A pause/hide command is always available.

Roaming uses actual walk animation frames and a small behavior state machine: idle, walk, sit/tea, ice practice, phone, greet, dragged and sleep. Safe furniture anchors represent an in-app shelf, chair and desk. Time of day changes idle probabilities rather than interrupting user work. Expressions and speech bubbles have cooldowns. Reduced motion uses stationary poses.

Bongo reacts to actual keydown/keyup and pointer input while this app is focused. Left and right hand poses correspond to input; release/blur resets the pose. Idle timers must never trigger typing. Password input and credential settings are ignored. No typed text or raw key history is stored.

## Companion room
A dedicated sidebar destination opens a care and wardrobe screen. The character is visible throughout. Chibi/full-form preview controls and zoom switch to normal proportions for close inspection, rather than enlarging the chibi sprite. Feeding, affection, energy, experience and outfit selection persist locally. Daily limits/cooldowns prevent input auto-repeat from generating unlimited experience. Growth never requires payments or punishes absence.

## Wardrobe and assets
Retain original source files untouched and copy only validated assets into this project. Inventory the six existing skins and corresponding skins_full. Rebuild damaged cutouts rather than declaring the current split layers usable.

Categories: tops, bottoms, full outfits, base garments, socks, shoes, headwear, glasses, earrings and other accessories. Only categories with actual artwork show equip choices; missing accessories are not represented by misleading substitutes. Full outfits can occupy multiple slots. A non-revealing fallback remains when slots are empty.

Separate character identity (face, ears, skin, hair and pose) from clothing. Asset manifest records form, pose, anchor coordinates, dimensions, layer order, slot exclusions and animation coverage. Each item has chibi/full variants where available. Pose-incompatible items must be labeled and use a supported stationary presentation; no false claim that the same cutout automatically animates in every pose. Repair default outfit first to prove alignment; then process and visually verify each existing outfit category.

## Local visual awareness
Off by default and off again after reload until explicitly enabled. A visible indicator states Watching this workspace, Paused, Analyzing, or Vision unavailable. Capture only the app content; exclude the companion itself, Settings, password fields and designated private regions. Capture visible changes at most once every ten seconds, with a single in-flight request and no queued frames. Stop on toggle off, hidden tab or page teardown, discard stale responses and release capture resources.

Prefer app-scoped rendering for capture. If browser screen-sharing is required for exact media pixels, require the user to select this app tab and reject monitor/window capture. No whole-desktop capture is part of this MVP. Unsupported media is disclosed rather than treated as seen.

A dedicated backend route validates image size/type and talks directly to a configured loopback-only vision endpoint. Disable redirects and all cloud fallbacks. Do not pass screenshots through the general model router. Images remain transient; no disk files, audit payloads or persistent screenshot history. Treat screen/model content as observation, never instructions to execute tools. Local model output drives brief contextual speech; app events support reliable task/page reactions independently of vision.

Common Ollama and OpenAI-compatible localhost ports were unavailable during discovery. The UI must provide endpoint/model configuration and a test control, and clearly disable vision when unavailable. Installing or downloading a model is a separate setup decision.

## Implementation units
1. Companion overlay, input/behavior controller, persistent state and care screen.
2. Asset manifest, transparent reference-derived sprites, wardrobe composition and full-form zoom.
3. Local-only capture/analysis endpoint, explicit controls, sampling and unavailable states.

## Verification
Behavior tests prove Bongo is idle without input and resets on blur; drag does not click; state persists and experience is bounded. Wardrobe tests prove slot changes preserve character identity and save/reload selections. Local vision tests reject external addresses and redirects, never invoke cloud providers, avoid requests when disabled and discard stale results. Inspect aligned asset composites and desktop/mobile UI; check keyboard interaction, pointer obstruction, reduced motion and page navigation.
