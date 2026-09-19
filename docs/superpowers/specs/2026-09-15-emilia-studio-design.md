# EMILIA LAB studio redesign

Approved in conversation: retain EMILIA LAB with subtle character details; office/team beside chat and tasks, approvals, outputs below. Implement across the existing frontend without changing backend contracts.

## Deliverables
- Simplified, accessible navigation with all existing views reachable.
- Cohesive graphite/cool-blue styling, selective existing artwork, responsive controls.
- Office/chat upper split and collapsible lower task/session dock.
- Action-focused dashboard with real task states, accurate configuration labels, recoverable loading errors.
- Navigation command search and live server connection state.
- Desktop/mobile browser verification, navigation smoke coverage, focused dashboard tests.

## Boundaries
New execution capabilities, real remote agents, and provider health probing are future work. Keep existing task/approval semantics. Do not infer provider health from configured keys. Use existing files and endpoints. Workspace has no Git repository; preserve a local backup of edited files.
