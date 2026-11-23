# Operations and synchronization experiments

Current profile: 200-ms near entities, 100-ms global controlled-unit supplements, 300-ms state/building dispatch, six far buckets (nominal 1200-ms coverage), and an eight-player guard. The dated evidence below describes earlier profiles and is not the current configuration.

Migrated from Mlogent on 2026-11-23. Active entry points live in the `mlogent_ops` package; older paths in experimental evidence describe the historical deployment.

### World resource budget on the current cgroup-v1 host

`mlogent-world-resources.conf` is a service drop-in for the 2-vCPU / 1.9-GiB
host. Install it as `zz-resource-budget.conf` so it overrides the older
`memory.conf`. Install `world-resource-budget.sh` at
`/etc/mlogent/world-resource-budget.sh` (root-owned). The combined proxy, world
daemon and game JVM receive a 100% CPU quota (one core; half of this host),
CPU shares 256, 700-MiB resident-memory cap, and 256-task cap. Nice 5 and
best-effort IO priority 7 lower their priority under contention.

The helper sets a 512-MiB v1 soft-memory reclaim hint and, when supported, a
900-MiB combined memory+swap cap. The soft value is not a guaranteed reservation
or throttle. The host uses mq-deadline: do not rely on BFQ/CFQ weights to provide
isolation. Whole-disk `/dev/vda` read/write caps are 20/10 MB/s (decimal) instead. Adjust
the device and budget before using these files on another machine. Buffered
writeback isolation remains limited by the legacy controller/kernel.

Existing processes can receive the limits without restarting the game: persist
the drop-in, daemon-reload, apply the matching CPU/memory/task/BlockIO properties
with `systemctl set-property --runtime`, and execute the helper. Subsequent
service starts apply the persistent settings plus the helper automatically.
OOM score adjustment 400 favors terminating game processes over the website
and bots during host-wide memory exhaustion; it does not reserve their memory.
These local budgets cannot isolate a saturated shared network link.

Install `mlogent-world-java-heap.conf` as a world-service drop-in to set
`JAVA_TOOL_OPTIONS=-Xms128m -Xmx384m -XX:MinHeapFreeRatio=10 -XX:MaxHeapFreeRatio=30 -XX:-ShrinkHeapInSteps`.
The 10/30 free ratios and disabled incremental shrinking are a world-only
memory-return experiment. The previous 40/70 -> 10/30 hot change plus one GC
reclaimed objects but left committed heap unchanged while incremental shrinking
was enabled. `ShrinkHeapInSteps` is not runtime-writable on this JVM, so applying
this setting requires a world-process restart. Check committed heap, RSS, GC
latency and host headroom after a full GC; collection does not guarantee that
all unused committed/resident memory can be released. Minimum heap remains 128m.
The JVM's container-aware automatic heap
was only about 170 MiB under the 700-MiB group cap, causing large-map Java heap
exhaustion before the group limit was reached. The 384m maximum leaves room
for non-heap memory; it does not guarantee every large map will fit. Restart
the world JVM to apply. Do not set this environment on MCP or other services.

`world_network_policy.py` installs a game-thread policy at world startup:
`rules.pvp` selects 200-ms entity snapshots; other rules select 300 ms.
World-load events and a once-per-second rule check cover map changes and late
rule edits. A manual snapshotInterval override is replaced by this policy.
The experimental controlled-unit supplement sends stock entity snapshots every
150 ms on the game thread for both PvP and other maps, only for living, added units owned by connected
players. IDs are deduplicated and each receiver's `isSyncHidden` visibility
filter is applied. Paused worlds send no supplements. A send error disables
the supplement and records `controlledError` instead of escaping the update
callback. There is no catch-up queue. The normal entity cadence remains active.
Private console JS can disable it immediately with
`this._mcpSnapshotPolicy.controlledEnabled=false` or enable it with `true`;
`controlledInterval` is the interval in milliseconds (default 150, reapplied by map policy). These
experimental switches are runtime-only and reset on a fresh JVM. Counters
`controlledBatches` and `controlledEntities` count receiver batches and entity
records, not byte totals. Use `world_traffic.py` to compare actual bandwidth.

The v160-headless AOI experiment (`world_interest_policy.py`) replaces the
NetServer listener only when explicitly opted in with service environment
`MLOG_WORLD_VIEWPORT_SYNC=1`. It is disabled by default after a large-map zoom
test showed long snapshot gaps and control timeouts under heavy host swapping.
This does not establish a single root cause; the experiment needs load testing
and performance safeguards before re-enabling. Normal startup keeps the map-aware
300/200-ms global policy and 150-ms controlled-unit supplementation.
For a cold-process B control use `MLOG_WORLD_VIEWPORT_SYNC=wrapper`: the
identical adapter is installed, but `interestEnabled` starts false before any
update can run. Every frame delegates to the original NetServer; no AOI
selection, viewport checks, custom periodic scheduling or AOI resource guards
run. The independent controlled-unit supplement remains enabled in both A/B.
`experimentGroup` reports `A-native`, `B-wrapper-only`, or `C-interest-enabled`.
Use a temporary `/run/systemd/system` drop-in for the B test, not a permanent
change to the default. A B run is not the same as native A with no adapter.

The guarded prototype bypasses entity AOI when any connected player's buffered
camera covers at least 60% of the world (including an invalid initial camera).
It delegates entity/state scheduling to stock without forcing a packet every
render tick. Within capacity, custom building snapshots remain enabled and
fog-filtered in full-view mode; player caches survive that transition.
Cooperative checks use an 8-ms scheduling budget, 32-entity native write batches,
and hard bounds of 4 players / 1024 sync entities. Building AOI is separately
bounded to 3072 synced buildings and 3072 cached building states per receiver.
This experimental capacity includes the observed 2038-building attack map;
the approximately 4040-building extreme-map reference still delegates buildings
to native sync. Per-turn limits remain 64 records / approximately 16 KiB, and
the existing scheduling-time and memory guards are unchanged. A higher capacity
does not establish large-map performance or override a memory-pressure fallback.
Above the building bound, only buildings use native six-second synchronization;
unit AOI remains enabled. Team sequence sizes are counted before copying records,
and the native building timer is not suppressed in this mode. Capacity is checked
at most once per base scheduling interval; map loads invalidate this cache.
`interestUnitMode` and `interestBuildingEffectiveMode` report actual subsystem
modes (including full-view bypass); `interestBuildingCount` and
`interestBuildingReason` explain the capacity decision. Do not infer active
AOI from the experiment group label alone.
Exceeding entity/player bounds, a >750-ms
callback gap, >85% heap usage, or >64-MiB JVM swap
disables AOI, frees its per-client caches and restores vanilla scheduling.
Host available-memory protection samples once per second: below 128 MiB for
at least five continuously observed seconds triggers fallback; below 96 MiB
triggers immediately at the next sample. A recovery to >=128 MiB resets the
pending timer. Observation gaps over 2.5 seconds or a backward clock step reset
the timer rather than treating missing data as sustained pressure. The values
are conservative experiment settings, not a capacity guarantee. No JVM/service
memory cap is raised. `interestMemorySample` exposes actual values, thresholds,
`hostState` (`ok`, `pending`, `sustained`, `critical`) and `hostLowForMs`.
Fallback does not automatically reactivate AOI; operator retry should wait for
stable headroom (160 MiB or more is the suggested recovery target).
Fallback also removes the JS NetServer update wrapper and reinstates the
original listener, rather than merely leaving a disabled wrapper on each frame.
The Linux memory guards run at most once per second. These thresholds are
conservative experimental defaults, not validated capacity claims. Checks
cannot interrupt one native serialization call, GC pause, or kernel IO stall;
they act at cooperative boundaries or when the game thread resumes. The
prototype remains opt-in and has not passed a repeat of the large-map test.
The initial 4-ms cap tripped on 75 entities: dry selection took 4-11 ms due
to repeated JS/Java bridge calls. Selection now caches team/owner/class/camera
bounds, avoids repeated getters and skips fog checks only when vanilla does
(fog disabled); measured dry selection fell to approximately 2.7-4.5 ms on
the current host. The C experiment uses an 8-ms cooperative budget for added
AOI preflight/selection/serialization work. OS resource probes and existing
native NetServer updates are timed separately, rather than charged against AOI;
they still count toward the 750-ms callback-gap protection. Probe last/max time
is `interestGuardLastMs` / `interestGuardMaxMs`. This is not a hard frame-latency
guarantee or a proven large-map budget. Selections of up to 128 entities use
the stock native writer directly; larger selections retain checked batching.

When opted in, the experiment replaces the
NetServer application listener in-place with a delegating listener, retaining
the original NetServer object and all packet handlers/commands. On non-PvP
worlds it suppresses only the original periodic state/entity branches
and sends stock packets itself. State and non-unit entities stay global at
the configured snapshot interval (currently 300 ms); units inside 1.5x the reported camera rectangle use the same interval, while units
outside use a 1000-ms global refresh. The receiver's own unit stays near-rate.
All entity selection retains `isSyncHidden` checks. Invalid or initial camera
dimensions fall back to full-rate selection. Empty viewports get heartbeat
entity packets. Player-local custom entities keep their original cadence.

Within the building capacity bound, the native periodic building timer is
suppressed and only original `BlockFlag.synced` buildings are scheduled: near 6000 ms, far
12000 ms. Building candidates use a resumable round-robin cursor: each turn
examines at most 128 candidates and sweeps at most 16 cached positions. The
soft building-work budget is 2 ms per receiver, also reserving 0.5 ms before
the global deadline. Exhausting a soft slice yields successfully and retries
unprocessed candidates later; it does not disable unit AOI. There is no full
per-player live-set construction, priority-list scan, or cache-key enumeration.
Removed entries are retired by a bounded generational sweep after missing a
complete subsequent scan pass (or immediately encountered in an empty list).
There are no per-cached-entry Java world/tile lookups. Same-type replacements
are detected by entity ID during candidate scanning;
fixed-capacity cache slots and a free-slot stack keep cleanup/insertion bounded.
Native serialization buffers initialize lazily and are reused across turns.
With war fog enabled, each candidate uses the native `Building.inFogTo(team)`
decision for the receiving player before serialization. Own-team buildings
remain visible under that native rule; hidden enemies produce no custom
periodic building records. A cached building observed hidden is immediately
due when next observed visible, regardless of its previous 6/12-second timer.
`interestBuildingFogSkipped` and `interestBuildingRevealed` count skipped
candidates and refreshed cached reappearances; `visibility` has separate timing.
Fog-disabled maps skip these visibility calls. Full-view entity bypass does not
duplicate native entity/state snapshots or reset building cursors every frame.
This filter applies to the custom C building path, not native/PvP/over-capacity
fallback, the initial world-data transfer, or separate building event RPCs.
Each player receives
at most 64 building records or about 16 KiB per base scheduling turn (one
large record may exceed the byte target); ordinary records are chunked at the
stock 800-byte boundary. Camera transitions and overload can extend delivery
beyond nominal periods. New player state, map loads and reconnects reset the
building schedule. Build/configuration/removal/health RPC paths are untouched.
The first increment preserves fair cursor progress rather than globally
prioritizing every newly visible building. Visibility changes are noticed when
the cursor revisits a candidate, so scheduling caps can delay delivery beyond
the nominal 6/12-second periods. Spatial indexing and timing wheels are not
implemented in this increment. Per-stage last/max/total/call timings are exposed
in `interestBuildingTimings` (`capacity`, `cleanup`, `visibility`, `initialize`, `scan`,
`serialize`, `total`), including measured serialization overruns. Scan, cleanup,
and soft-yield counters are `interestBuildingScanned`, `interestBuildingCleaned`,
and `interestBuildingYields`. Native calls remain indivisible; the unchanged
8-ms hard guard can still trigger on a slow allocation or serialization.

### Opt-in AOI diagnostics

#### Persistent experimental profile and fallback-only recording

`MLOG_WORLD_VIEWPORT_SYNC=experimental` enables C + stagger + four far buckets.
The owned `out/_world/snapshot-profile.json` can select the same profile using
`{"mode":"experimental","eventPath":"/opt/mlogent/out/_world/aoi-fallback.json"}`.
This file is read by each fresh world daemon, including wakes of an already
running sleep supervisor; it overrides the supervisor's inherited mode. Delete
it or set `mode` to `native` to opt out. The deployment drop-in
`mlogent-world-snapshot-experimental.conf` makes the equivalent environment
choice on a supervisor restart. A safety fallback stays native for the current
JVM; it does not automatically retry each frame or world load.

This profile keeps the 20-ms scheduling deadline for soft building yields, but
only three consecutive slow dispatches over 100 ms trigger a timing fallback.
A completed healthy dispatch resets the streak; idle update frames do not.
The callback-gap line is 5 seconds. Host memory below 96 MiB for 10 continuously
observed seconds or below 64 MiB immediately triggers fallback; JVM swap above
128 MiB or heap above 93% also triggers it. Default non-experimental guards are
unchanged. Player/entity/building count bounds and the 2-ms building soft slice
are unchanged. Native calls still cannot be preempted by these checks.

`world_traffic.py --incident-dir ... --event-file ... --sample-seconds 1` stores
normal traffic/resources only in a bounded 90-second memory ring. A background
worker polls aggregate game state and Linux process/thread counters every five
seconds through an explicit existing handshake, never through a wake request.
It does not block raw-packet accounting if the game control socket times out.
Only a safety fallback creates a persistent case: the preceding 90 seconds,
the reason/stage/memory/counters and the following 30 seconds. Expected PvP,
full-view and building-capacity delegation are not safety incidents. Repeated
events do not extend a case indefinitely; at most 20 owned case files remain.
An interrupted collector marks an incomplete post-window rather than inventing
missing history. No packet payloads, peer IPs or chat messages are stored.
The volatile `/run/mlogent-world-recorder/status.json` exposes current collector
health and latest aggregate state, with availability and observation time.
No continuous `samples.jsonl` is opened in incident-only mode. Existing manual
benchmark summaries and processor backups are separate from this telemetry.
Set the collector service's `MLOG_WORLD_RELEASE_ROOT` to its actual release root.
The collector has a 64-MiB memory cap; the world JVM/service caps are unchanged.

For bounded experiments, `interestStaggerEnabled=true` separates state,
entity and incremental-building dispatch into offsets 0, one third and two
thirds of the configured snapshot interval (0/100/200 ms at 300 ms). Each
phase retains its original interval; missed slots are skipped instead of
replayed. Full-view still delegates state/entities to native, and only custom
buildings are phased. World-load and view-mode transitions reset alignment.
The switch defaults off; controlled-unit supplementation is unchanged.
`interestFarBucketsEnabled=true` optionally replaces the concentrated distant-unit
refresh with four stable entity-ID buckets, one bucket per completed entity
dispatch. At 300 ms, steady distant-unit coverage is nominally 1200 ms, matching
the existing 1000-ms due check rounded to four 300-ms rounds. Near units,
the receiver's own unit and non-unit metadata bypass buckets. Camera entry
therefore refreshes on the next near round; fog checks still run first.
Missed rounds do not skip bucket IDs or replay a backlog. New receiver/world
state starts at bucket zero. Native full-view/PvP paths remain unchanged.
This experiment defaults off; `interestFarBucketRounds` and
`interestEntityMaxSelection` expose rotation counts and largest selected batch.
`interestPhaseTicks` reports each phase, `interestDispatchTicks` actual dispatch
callbacks, `interestDispatchMaxMs` the largest part and `interestMaxMs` the
largest combined work in one aligned cycle. No timing guard is removed by
this feature. Tests may temporarily bypass time fallback with an independent
expiration/cleanup while retaining resource and count protections.

`world_interest_diagnostics.py` provides a separate `INSTALL_JS` observer; the
normal interest-policy installer leaves diagnostics disabled. Install the
observer only during a bounded experiment. It observes due snapshot rounds,
keeps at most 64 records and labels the first 10 as `warmup` (configurable via
`interestDiagnostics.warmupTraces`). Warm-up labels never bypass hard guards.
`interestDiagnostics.records` contains stage wall/thread-CPU times, native-update
and resource-guard time separately, GC count/time deltas, class-loading and JIT
compilation deltas, observer overhead, exact latest resource-guard sample, and
the fallback error/stage. A native update crossing a due boundary opens a
`send-only` trace; other traces have scope `update`. These scopes must not be
compared as equal coverage. `interestDiagnosticPid` / `interestDiagnosticTid`
identify the JVM and native game thread for the external sampler. Optional
observer failures disable diagnostics only. `disableInterestDiagnostics()`
stops collection; records remain available for export.

Only while enabled, building timings additionally split `encode` (including
record headers), `copy` (`toByteArray`) and `send` (native packet dispatch).
Observer mark bookkeeping is measured and excluded from the scheduling deadline;
bean-read setup/finish overhead is outside measured work and reported separately.
Probe overhead and coarse management counters still limit precision. GC/JIT
counters describe the JVM; a wall-minus-thread-CPU gap is not proof of I/O or GC.
CPU and wall-clock reads have slightly different boundaries. Tiny empty samples
can show CPU overhang; `cpuMeasurementOverhangMs` reports this measurement noise
instead of silently treating sub-observer-scale differences as useful work.

The passive Linux collector reads process CPU/faults/swap, native game-thread
scheduler runtime/wait (or explicitly labels a leader-only fallback), and cgroup
CPU throttling. It never opens the game control socket or wakes a sleeping world:

```bash
python tools/world_interest_diagnostics.py --pid JAVA_PID --tid GAME_THREAD_TID \
  --seconds 90 --interval 1 --output /var/log/mlogent-world-traffic/pressure.jsonl
```

Cumulative counters are differenced only across matching PID/start identities;
missing metrics are reported as unavailable, not fabricated zeros. Correlate
external intervals with JVM traces before attributing a pause to throttling,
faults, compilation or GC. The observer does not silently raise production
budgets, memory limits or the existing fallback protections.

PvP bypasses AOI and delegates to the original global sync at 200 ms.

`this._mcpSnapshotPolicy.interestEnabled=false` immediately restores the
original scheduling path without a JVM restart. A scheduler exception performs
the same fallback and records `interestError`. Controlled-unit supplementation
is separately switchable; AOI restricts other controlled units to the receiver's
buffered viewport, while retaining their own unit. Shutdown/restart recreates
the policy with defaults. `interestTicks`, `interestEntityRecords`,
`interestBuildingRecords`, `interestTotalMs`, `interestMaxMs` expose scheduling
cost and delivered receiver-record counts, not compressed wire-byte totals.
This is not an anti-cheat visibility boundary: client camera reports are
untrusted and never override fog-of-war checks. Test minimap freshness, camera
jumps, block state correctness and CPU load before treating AOI as production.

Managed cold startup loads the named default map through the native world API,
because Wayzer overrides the console host command with numeric map IDs.

`mlogent-world-traffic.service` optionally records IPv4 public-port 6567 IP-byte
counts on eth0 every ten seconds, split by TCP/UDP and inbound/outbound, with
one-second and 100-ms fixed-bucket peaks (both in bits/second). Bucket peaks
are not rolling-window maxima or evidence of public delivery beyond shaping.
It stores no payloads or peer addresses. Logs rotate
at 10 MiB with two backups. Noninitial IP fragments and separate Steam relay
traffic are excluded. Deploy `world_traffic.py` at `/etc/mlogent/` before
enabling the unit; statistics live in `/var/log/mlogent-world-traffic/`.
Each sample also records host MemAvailable/swap, world cgroup memory/swap,
and cumulative major page faults. Fault deltas between samples help distinguish
snapshot silence during memory stalls from actual network saturation. Missing
resource metrics do not stop packet accounting. The resource helper sets only
the world's cgroup-v1 swappiness to 10 (previously 60), preferring cache reclaim
over world-process swapping; the host setting and other services are unchanged.
This cannot guarantee resident memory and does not immediately page old data in.

### ScriptAgent long-console allocation diagnosis (2026-11-23)

Isolated v160 probes found native and minimal-adapter paths stable. With the
server's ScriptAgent/Wayzer program fixture and Serial GC / 2 active CPUs,
the full B script and an equally long no-op console payload expanded the heap
substantially. Keeping the full B program identical but loading UTF-8 source
from a file reduced sampled peak RSS from about 536 MiB to 278 MiB and committed
heap from about 371 MiB to 124 MiB in the 20-second local probe. This identifies
the long-console transport/parsing path as an important allocation trigger;
it does not prove a retained-heap leak or that AOI algorithms are validated.

`WorldChannel.js` now uses an ASCII short loader for source over 2048 UTF-8
bytes. Small source retains base64 inline transport. The program is written
under the owned game cwd and read at execution time, preserving Unicode,
comments and backslashes. Source is removed after either success or an error
result; timeout source is retained because its queued invocation may still
need it, and for diagnosis. This change does not alter the public MCP schema.

Run `python tools/world_snapshot_diagnostics.py --help` for the local isolated
probe. It starts fresh owned JVMs, uses no live-server connection and binds no
game port. `--runtime` accepts a sanitized plugin/libs/script fixture; account
data, DBs, and chat logs must not be included. `--inline-limit 1000000000`
reproduces the former console path; default 2048 uses the corrected transport.
`--scenario simulated-hosted-idle` runs the paused server branch using a private
server flag and generated 64x64 world without opening a socket. Outputs are
under `out/diagnostics/`, and JVM cleanup runs even on probe errors.
