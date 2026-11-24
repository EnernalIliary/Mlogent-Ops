# Enemy building viewport filtering — 2026-11-24

The experimental C profile now supports `enemyBuildingsInViewOnly: true`.
Foreign-team buildings outside the receiver's padded interest rectangle are
rejected before periodic building serialization, including reactor-priority
records. Same-team far snapshots remain enabled. Native fog filtering precedes
the viewport gate. Reentry is marked due and forced through byte dedup; switching
the receiver's team clears its building scheduling state.

The camera rectangle keeps the existing 1.5 margin and building-size overlap.
Invalid camera metadata uses full delivery. PvP, native fallback, construction
events and other native RPCs are outside this filter; it is not an access-control
or map-secrecy guarantee. Unit snapshots are unchanged.

Live installation used the existing JVM without disconnecting players. After
30 seconds, one player was online, C and byte dedup were enabled, and there
were no new fallback or observer errors. The map had 2040 synced buildings:
44 sharded and 1996 crux. `interestBuildingOutsideSkipped` increased from 4836
at 15 seconds to 9666 at 30 seconds. These are skipped scan visits, not unique
buildings, previously due records, saved packets or a bandwidth percentage.

`python tools/check.py`: 36 tests passed. The new regression covers own-team
far delivery, enemy offscreen exclusion, viewport reentry, team switching,
fog hiding/reveal, invalid camera fallback, priority reactor filtering and
fog-disabled exclusion without serialization.

Profile flag and deployed source persist across wakes. Backup is under
`out/deploy-backups/enemy-interest-20261124` on the operations deployment.
Live rollback sets `this._mcpSnapshotPolicy.interestEnemyBuildingsInViewOnly=false`;
set the matching profile flag false to preserve rollback on future starts.
