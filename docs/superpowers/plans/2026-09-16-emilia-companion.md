# Emilia Companion Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the isolated backend and state controller; root owns integration, art and browser verification.

**Goal:** Ship the approved in-app Emilia companion with care, modular wardrobe, real input reactions and strictly local visual awareness.

**Architecture:** Vanilla JavaScript persistent overlay and room, pure state controller, JSON art manifest and local FastAPI router. Existing execution and cloud routing remain separate.

**Tech Stack:** HTML/CSS/JavaScript, Python/FastAPI, standard-library HTTP client; local bundled DOM-to-canvas capture library.

**Spec:** ../specs/2026-09-16-emilia-companion-design.md

## Global constraints
- Awareness is opt-in per page load, app-only, loopback-only, no redirects, proxies or cloud fallbacks.
- Never persist screenshots or typed key values; analyze one frame at a time, at most once per ten seconds and only when changed.
- Bongo reacts to real input and resets on blur; drag must not trigger click; preserve reduced-motion support.
- Outfit components preserve the character identity. Unsupported form/pose combinations are explicit.
- User-provided source artwork remains untouched. Image edits use the native image tool.
- No Git repository; keep local backups of existing files modified for integration.

## Task 1: Local vision boundary
Files: new companion_vision.py, tests/test_companion_vision.py; root imports router in main.py.
Contract: GET /api/companion/vision/status returns {available,model,endpoint,models,message}; POST /api/companion/vision/config accepts {endpoint,model}; POST /api/companion/vision/test accepts no required body; POST /api/companion/vision/analyze accepts {image: data URL, context: string}, returns {observation,model}. Config persistence stores endpoint/model only. Test forbidden endpoints/redirects/proxies and malformed/oversized images before implementing. Validate browser origin/Host for these routes. Never import the general model router.

## Task 2: Companion state and behavior
Files: public/js/pet-state.js, tests/pet-state.test.cjs.
Contract: global/CommonJS PetState.create(saved?, now?) returns serializable validated state; PetState.reduce(state, action, now?) returns next state; PetState.level(state), PetState.daypart(now), PetState.chooseIdle(now, random?), PetState.bongoPose(input), PetState.isPrivateInput(element). Actions: mode/set, visible/set, position/set, feed, pet, play, outfit/set, activity/set. Fields version, mode(roam|bongo), visible, position{x,y}, xp, energy, affection, outfit{top,bottom,socks,shoes,headwear,glasses,earrings}, activity, lastRewardAt, lastFeedAt. No browser globals in module import. Meaningful tests cover persistence sanitization, growth limits, input pose and private input.

## Task 3: Artwork and wardrobe
Files: public/assets/pet/* and manifest.json. Inventory originals; native image generation repairs character transparency, actual walking frames, idle poses, Bongo computer keyboard poses, standard-pose wardrobe components. Manifest records source, pixel/frame dimensions, anchors, slot and form. Browser renders atlases directly where practical to preserve native alpha. Store availability for each supported pose rather than pretending static outfit cutouts animate.

## Task 4: Companion UI and capture
Files: public/js/pet.js, public/css/pet.css, public/index.html, public/js/studio.js; vendor html2canvas locally. Room includes always-visible normal-form character preview and zoom, wardrobe categories, care actions/XP, furniture and explicit awareness setup. Overlay survives App.showView; event reactions exclude private inputs. Capture only visible app region and mask private/unsupported surfaces; stop/abort and discard on disable/hidden. Expose a small pure awareness helper if needed to test sampling.

## Task 5: Verification and review
Run state/backend tests, JS syntax, browser desktop/mobile with actual clicks/drag/typing and persistence, local mock vision tests for no disabled requests and no overlapping calls. Inspect sprite transparency and wardrobe fit. Reviewer checks final source/security boundary and screenshots. Fix one batch, confirm and document limitations.
