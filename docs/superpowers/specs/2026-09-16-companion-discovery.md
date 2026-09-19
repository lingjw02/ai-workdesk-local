# Emilia workspace companion: discovery

## Confirmed by user
- First version lives inside EMILIA LAB only.
- Continuous visual analysis while an explicit awareness toggle is enabled (confirmed 2026-09-16).
- React to app pages, tasks, keyboard and mouse.
- Roaming, real input-driven Bongo mode, click/drag interactions, expressions, speech, time-based behavior.
- Character growth, feeding, experience, dressing, visible model preview.
- Chibi roaming character; normal-proportioned character for zoom and dressing.
- Character layers independent from clothing layers, including separate accessories.

## Source assets located
Read-only source: `C:/Users/ling5/Doubao/chats/2026-07-27/new-chat/desktop_pet/assets`.
- `skins`: six full outfit images (default, casual, ice_queen, kimono, maid, swimsuit).
- `skins_full`: the same six outfit names in normal proportions.
- `layers`: 76 files including bases, raw outfits and clothing components, separated into `q` and `full`.
- Clothing categories present: headwear, tops, bottoms, socks, shoes, underwear.
- Bongo poses: idle, left_press, right_press.
- Roaming actions: idle, left walk, right walk, tea, magic, phone; one file per action folder.

## Visual findings
Inspected the provided turnaround and keyboard references, existing normal-proportioned default outfit, a split top layer, and the existing Bongo idle image. The split top has missing fabric and hair fragments. Existing Bongo art uses a musical keyboard, whereas the supplied requested reference is a computer keyboard and mouse. These are quality gaps, not ready-to-ship assets.

## Character direction
Retain silver hair, braided detail, pointed ears, violet eyes, white rose/ribbon and white-purple costume language. Gentle, caring behavior; ice magic as a characteristic animation. Official character reference: https://www.re-zero.com/character/エミリア/

## Architecture to propose
Persistent in-app overlay; finite-state behavior controller; actual keydown/keyup/pointer events driving Bongo poses; no timer-generated typing. Dedicated companion page with full-form preview and zoom. A versioned asset manifest maps form, pose, animation frame, clothing slot, layer order and anchors. Clothing must match each form/pose; no claim that a single flat outfit cutout fits all animations.

## Awareness design
Continuous analysis is user-selected, bounded to the visible EMILIA LAB workspace. Use a visible watching indicator and pause control; pause when hidden or disabled. Proposed sampling is on visible changes, no more than once per ten seconds, with one in-flight request and no backlog. Exclude Settings and credential/password fields from capture. Screenshots are transient and are not added to chat history or stored by this app. Bongo consumes input events only, without recording typed text.

The existing provider adapter accepts message objects, but the public model-router call endpoint only accepts text prompts. Visual analysis therefore needs a dedicated image-capable endpoint and explicit provider routing. Do not reuse the router's automatic local-to-cloud fallback for screenshots.

## Confirmed local-only boundary
The user requires screenshots to stay on this computer. No cloud fallback is permitted, including through the existing general-purpose model router. The awareness endpoint must accept only loopback model services, reject redirects and non-loopback targets, and return an unavailable state when no local vision model is ready. No capture or external transmission has been started.

Discovery checked the common local services at 127.0.0.1:11434 (Ollama) and 127.0.0.1:1234 (OpenAI-compatible). Neither responded on 2026-09-16. This does not establish whether a local model is installed or listening at a custom endpoint.

## Implementation status
Discovery only. New pet design and milestones need confirmation before implementation. Existing desktop pet source has not been modified.
