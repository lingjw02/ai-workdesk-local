# EMILIA LAB Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent units, then integrate and review in this session.

**Goal:** Implement the approved personal AI studio across the existing UI.

**Architecture:** Preserve FastAPI and engine contracts. Rebuild navigation and dashboard; normalize incumbent CSS and add a focused studio layout stylesheet and controller.

**Tech Stack:** Plain JavaScript, CSS, HTML, FastAPI, SQLite.

**Spec:** ../specs/2026-09-15-emilia-studio-design.md

## Global Constraints
- Retain EMILIA LAB and subtle existing character assets.
- Preserve existing element IDs used by feature controllers.
- Distinguish configuration from connectivity and demo from execution.
- Support desktop and narrow mobile viewports, keyboard focus, and reduced motion.
- No Git repository exists; back up edited files locally.

## Tasks
- [x] Dashboard: replace public/js/dashboard.js, add public/css/dashboard.css and focused tests. Consume existing Api methods and App view methods. Show attention queue, task rows, workers, recent conversations, configured providers. Test partial API failure and mixed task states before implementation.
- [x] Shell and workspace: modify public/index.html and public/js/app.js; add public/css/studio.css and public/js/studio.js. Preserve control IDs, expose missing nav items, implement command navigation, connection state, and lower session dock.
- [x] Consistency: consolidate theme variables, normalize tool headers/forms/cards, preserve document canvas colors, replace decorative status copy, add keyboard access.
- [x] Verify: JavaScript syntax checks, dashboard tests, server navigation across views, desktop/mobile screenshots, dock/command keyboard interactions, Impeccable detector and final review. Fix discovered issues in one batch and confirm.

## Verification record
Five dashboard tests pass. Desktop navigation through 15 views produced zero browser exceptions. 390px home/chat/office screenshots inspected; no document overflow. Command search and session dock collapse/open verified. Exact task selection, keyboard task focus, files navigation and mobile sidebar inert state verified. Mechanical detector ran; legacy CSS warnings remain outside the newly normalized surfaces. Approval parameter preview and stale task response guard added after scoped review. No paid model call or real approval was issued for these checks.
