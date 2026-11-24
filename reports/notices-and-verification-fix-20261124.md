# Rotation, 200kbps and verification correction — 2026-11-24

## Superseding behavior

- Default adaptive target is now 200000bps per player (220000 downshift /
  170000 recovery thresholds). Live target and existing levels were reset on
  the user's request; source default persists on wake. The previous 100kbps
  experiment report remains historical evidence, not the current setting.
- `rotatingNotices: true`: one notice every five minutes, AFK → polyAI → MCP.
  No catch-up burst or empty-server broadcast; disabled-rule notices are skipped.
  MCP notice directs players to the private `/mcp` guide. Original listener is
  reused on hot installs. No credentials are included.
- AFK no longer asks arithmetic. After three minutes without qualifying actions,
  a two-choice confirmation opens. After thirty seconds without confirmation,
  the receiver enters AFK. Clicking the original “I am here” option later still
  restores normal synchronization. Closing or choosing to stay AFK leaves low
  frequency; `/afkverify` reopens it. No kick occurs.
- polyAI keeps the separately authorized challenge and failure kick. Its question
  and correct option now use explicit JavaScript integer generation.

## Bugs observed and corrected

On first real-client testing, AFK and polyAI had disabled themselves with
callback errors referring to a `KickCallPacket` instead of their policy object.
Generic `p`/`root` callback references were replaced with module-specific names;
adaptive and byte-observer closures were similarly isolated. Subsequent live
callbacks stayed enabled without those errors.

The user then reported decimal-heavy questions and unexpected AFK failure.
Rhino/Java overload resolution had selected floating random values; the expected
option was noninteger while client replies were integer indices. The old unit
test stub returned integers and compared the internal answer directly, hiding
this issue. The affected player's normal sync was restored immediately and
polyAI was paused during correction. polyAI's revised regression parses the
displayed question, solves it and clicks the displayed answer; all choices must
be integer strings with exactly one correct choice. AFK removed arithmetic at
the user's request rather than retaining the problematic design.

## Live verification limits

The earlier AFK menu rendered and returned an actual wrong-answer result, which
is now known to have been invalid because of the generator bug. Revised two-choice
AFK confirmation was sent to the authorized user's identified connection.
No claim of successful confirmation is made until an actual response is observed.
polyAI callback registration is enabled after correction, but no real user has
yet completed a revised polyAI question or been test-kicked. Only the authorized
user was targeted by manual prompts.

`python tools/check.py`: 43 tests passed. Notice regression checks single-message
rotation, no burst, empty server, disabled rules and listener reuse. AFK regression
checks late confirmation, no unsolicited restore, explicit stay-AFK, closed menu,
retry, cleanup and recovery. Source changes remain uncommitted at this point.
