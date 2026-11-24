# polyAI cooperative-build verification — 2026-11-24

User authorized: five distinct teammate-following placement requests within
60 seconds trigger a three-option question; fail/close/30-second timeout kicks
the follower, success permits continued play. Single co-build does not kick.

`polyVerification: true` is independent of C scheduling, PvP and synchronization
fallback. The standard Administration action observer records first requester
by team, tile position, block ID and rotation; subsequent teammate requesters
count each distinct target at most once within a rolling minute. Repeated client
snapshots of one plan do not multiply hits; the first requester is not counted.
Tracker is capped at 2048 target slots and sweeps 32 entries per second.
Pooled actions, tiles and buildings are not retained. Connection references
are bounded and cleaned after disconnect/expiry. Disconnect and map load clear
state, preventing an old pending challenge from kicking a new connection.

Original config present / follower config absent is captured as a diagnostic
flag, not proof of config loss. This is a heuristic that can challenge normal
cooperative builders; the menu clearly explains the kick condition. Automated
solving/qualifying-request spoofing remains possible. No claim is made that it
identifies a particular client or prevents all config loss during verification.

Question success grants five minutes of grace. Failure calls the native
`player.kick(reason, 0)` overload (no ban period); repeated callbacks cannot kick
twice. It does not ban accounts/IPs. Menu send failure does not kick; observer
errors disable the mechanism. polyAI and AFK use distinct registered menu IDs;
polyAI pending defers AFK challenges, and successful polyAI answers satisfy AFK.

## Tests and deployment

`python tools/check.py`: 42 tests passed. New regression covers target-repeat
dedup, different teams, requester identity, config diagnostics, success grace,
window expiry, exact timeout, wrong/close, no repeated kick, failed menu send,
bounded/reused slots, disconnect/map cleanup and idempotent registration.

Source and profile were deployed to the server. The game was sleeping at the
deployment check; no wake was forced. It will register on the next normal wake.
Actual client menu rendering, reply and kick behavior have not been verified
against a real player, and no test kick was issued. AFK module source includes
the menu coordination change. Existing enabled services remained active.

Backup: `out/deploy-backups/poly-20261124` on the operations deployment.
Set profile `polyVerification` false to disable future starts; if awake, set
`this._mcpSnapshotPolicy.polyEnabled=false` for immediate disable.

Changes are uncommitted in the operations worktree at this stage.
