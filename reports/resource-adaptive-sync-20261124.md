# Resource-aware synchronization — 2026-11-24

The live report of stuttering was investigated before changing rates. Native v160
defaults to 200ms entity snapshots. Ordinary near-unit snapshots were already
200ms; the 100ms supplement applied only to player-controlled units. Those units
also entered the primary lane, producing duplicate, uneven updates. The client
uses the latest arrival spacing as its interpolation denominator.

A bounded 20-second server sample observed 17ms median frame time, one 224ms
frame, primary dispatch gaps of 118–256ms, and supplement gaps of 100–272ms.
These measure server scheduling, not client arrival times or perceptual quality.

Controlled units now use the supplement exclusively while it is healthy. The
primary selector resumes them if the supplement is disabled. Native fallback
and PvP do not add a second supplemental lane. Fog and AFK checks are preserved.
Missed controlled slots are skipped instead of replayed as a burst.

The bandwidth worker samples the world's cgroup CPU usage normalized to its
quota, host CPU and available memory every two seconds. The game accumulates at
most 240 frame gaps, consumed on resource feedback; existing memory samples
supply heap pressure. Missing or invalid data cannot enable a faster tier.
Thirty seconds of healthy samples are required per recovery step. Sustained
pressure lowers frequency with a minimum ten-second change spacing. Resource
tiers constrain bandwidth-derived per-player cadences; no hard network cap is
promised. The shortest ordinary cadence is 100ms and longest 500ms. Controlled
cadence ranges from 100 to 200ms. AFK remains a separate 1000ms override.

Regression coverage includes exclusive ownership and fallback, fog visibility,
100ms dispatch opportunities despite staggered phases, per-player isolation,
NAT accounting, resource hysteresis and staleness, and both cgroup v1/v2 quota
normalization. Deployment hot-installs policy functions while preserving AFK,
adaptive-client and building state; only bandwidth and telemetry services restart.

Live CPU sampling confirmed a one-core service quota. Readback confirmed zero
controlled units in primary selections, version-four supplement, active AOI,
fresh resource feedback, and no controlled transport error. At that readback
the connected player was in AFK; no claim of improved active-player visual
smoothness is based on this check. No client packet or frame capture was made.
