# Bounded building deduplication experiment — 2026-11-24

The public v160 server used C snapshot scheduling, a 12-player admission and
optimization limit, and the Broken Moon Islands map. The sample grew from one
to two connected players; building counts were about 2011–2015 and units 44–45.
This is not a controlled before/after bandwidth benchmark or a load-capacity test.

## Scope

- Compare complete serialized building records, including their position/type
  header, using exact byte-array equality and receiver/team/building identity.
- Up to 8 comparisons per second across the server, 64 cached records,
  2KiB per record, and 128KiB maximum retained byte arrays.
- Suppress only identical records. At 24 seconds since the last actual send,
  the next normal building dispatch sends the record again. Soft scheduling
  and overload can delay that dispatch; this is not a hard 24-second deadline.
- Force sends for new/replaced buildings, viewport entry, fog reveal and all
  reactor-priority updates. Native packet format and entity cadence stay intact.
- Unsampled sends invalidate an older comparison baseline. Map load clears
  cached bytes. Comparison errors send the original packet and disable dedup;
  send errors discard baselines and use existing synchronization fallback.

## Live results

After policy installation, a 30-second observation-only warmup delivered
1944 records / 91211 payload bytes / 145 packets. A following 60-second dedup
window delivered 3476 records / 163548 payload bytes / 271 packets and omitted
31 records / 1165 payload bytes / 3 complete packets.

Omitted payload was 1165 / (163548 + 1165), approximately **0.71%** of eligible
building payload in that window. This excludes transport headers, other RPCs,
entity snapshots and all other services. It is not total public-bandwidth saving.

At the end, the combined 90-second counters showed 389 byte samples, 325
comparable samples, 110 repeated samples, 48 forced repeat refreshes, about
2803 cached bytes, and no observer error or synchronization fallback.
Observation/comparison calls accumulated 39.40ms (warmup: 15.56ms), with a
maximum individual call of 1.86ms. A single overall synchronization work peak
of 199.66ms occurred during the later window. Attribution is unknown; the
three-consecutive-slow-dispatch guard did not fire. Do not expand the cohort
based on this short experiment alone.

## Validation and deployment

`python tools/check.py`: 35 tests passed, including exact filtered bytes/counts,
empty-packet suppression, periodic resend, A→B→A, unsampled intermediate
changes, receiver/replacement identity, fog reveal, reactor priority, sampling
failure after an earlier skip, and send failure recovery.

Deployed without a JVM restart. Persistent profile has `buildingObservation`
and `buildingDedup` set to true. To stop filtering live, set
`this._mcpSnapshotPolicy.buildingDedupEnabled=false` through the local world
control API; also set profile `buildingDedup` to false for future starts.
Observation can remain enabled. Pre-deployment backup is under
`out/deploy-backups/building-dedup-20261124` on the operations deployment.

Only this aggregate report is retained here; no raw per-player traffic or
continuous trace is committed. The existing incident-only recorder remains in use.
