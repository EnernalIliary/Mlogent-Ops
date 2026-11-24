# Per-player bandwidth comparison — 2026-11-24

Passive eth0 public game-port 6567 accounting counted IPv4 TCP/UDP packet
lengths, including IP and transport headers but excluding Ethernet overhead.
Unclassifiable noninitial fragments are omitted. Discovery traffic on the same
port is included. No packet payloads or peer addresses were retained.

Both windows used Broken Moon Islands, 2040 synced buildings, and exactly one
player in every periodic population sample. Per-player rates use integrated
player-seconds. These are sequential live-play samples, not identical unit or
camera trajectories.

| Window | Current rules | Previous building rules |
|---|---:|---:|
| Sample duration | 60.0001s | 60.0230s |
| Units | 79–86 | 88–89 |
| UDP outbound bytes | 781085 | 857705 |
| TCP outbound bytes | 4666 | 4726 |
| UDP inbound bytes | 88246 | 87041 |
| TCP inbound bytes | 6920 | 6840 |
| Per-player total downlink | 104.767kbps | 114.947kbps |
| Per-player total uplink | 12.689kbps | 12.513kbps |
| Maximum 1s total outbound rate | 126.040kbps | 124.688kbps |

The previous-rules window disabled only building dedup and enemy offscreen
building filtering, after a 15-second warmup. C scheduling, six far buckets,
200ms near entities and 100ms controlled-unit supplementation stayed enabled.
A finally block restored both flags; live confirmation returned both true,
interest enabled and no fallback. Persistent profile was never disabled.

Observed downlink was about 8.86% lower with current rules. Unit counts differ,
so do not attribute the entire reduction to these two flags or promise the same
result under a larger camera or battle load. The one-second peak did not improve
in these samples.

Historical same-map aggregates retained on the server report 201 units / 2026
synced buildings: native 300ms UDP outbound 303.8068kbps; C-stagger-four-buckets
148.7928kbps. Current UDP outbound is about 104.1445kbps, roughly 65.7% below
that native sample and 30.0% below the older C sample. Historical C cadence,
controlled-unit interval, unit count and camera differ; these are historical
operating-point comparisons, not isolated optimization gains.

A different player briefly connected at 12:34:26 and disappeared at 12:34:27.
That event fell between the two measured windows; it is not included in their
byte totals. The server recorded no corresponding exception. The remote
client's crash reason requires its own crash report; no new local crash report
was found (latest local report remained 11:52:29).
