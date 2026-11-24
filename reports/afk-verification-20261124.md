# AFK verification and reduced receiver cadence — 2026-11-24

User selected 180 seconds without qualifying requests and 30 seconds to answer.
The opt-in experimental C profile uses `afkVerification: true`.

Activity comes from the original Administration action filter for placeBlock,
breakBlock, control, buildSelect (building possession), and commandUnits. The
observer always returns true and never changes other filters' authorization.
Position, periodic snapshots, mining, camera, chat and building simulation do
not refresh the timer. These are observed requests, not a guarantee of a human
or a completed construction. Automated meaningful requests can keep it active.

A native three-option randomized addition question opens after idle time.
Correct answers restore normal cadence and clear stale adaptive/building state.
Timeout, wrong answer or close switches only the receiver to 1000ms ordinary
entity snapshots and 1000ms controlled-unit supplements; six far buckets may
take approximately six seconds. The world, mining script, building/critical
events and other receivers keep running. No kicking or banning occurs.
Pending challenges cannot be cancelled by requests. `/afkverify` reopens one
after failure, keeping the receiver throttled until success. A new menu does
not extend the existing pending window. Callback failures disable AFK; menu
send failure does not newly penalize the player. State is cleaned on disconnect
or world change, and disabled in PvP/native fallback.

The menu ID and listeners are registered once per JVM; reinstallation reuses
callbacks. This is a convenience challenge against common unattended mining,
not a bot-proof authentication protocol. A script can solve arithmetic or
issue qualifying actions. The fixed menu callback has no cryptographic nonce.

## Deployment and validation

Hot-installed without restarting Java. Live server reported AFK enabled,
idleMs=180000, answerMs=30000, intervalMs=1000, menu ID 0, hooks installed,
no AFK error and C enabled. Zero players were online at this verification,
so actual client rendering/click roundtrip remains untested. No fake challenge
was sent or reported as a human-client test. Reflection-created String[][]
construction was separately checked on the live JVM.

`python tools/check.py`: 41 tests passed, including request whitelist, excluded
mining, exact timeout, pending non-bypass, wrong/closed/expired replies,
receiver identity, retry while throttled, correct-answer restore, menu failure,
map/disconnect cleanup and idempotent hooks. Integrated dispatch verifies one
AFK receiver receives three ordinary updates in three seconds while another
receives fifteen, and normal cadence resumes after clearing AFK.

Profile persists across wakes. Pre-deployment backup:
`out/deploy-backups/afk-20261124` on the operations deployment.
Live rollback sets `this._mcpSnapshotPolicy.afkEnabled=false`; also set profile
`afkVerification` false for future starts. Source remains in the operations
working tree; it has not been committed or pushed in this iteration.
