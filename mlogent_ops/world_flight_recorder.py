"""Bounded in-memory telemetry; only safety-fallback windows reach persistent disk."""
from collections import deque
import datetime as dt
import hashlib
import json
from pathlib import Path
import queue
import threading
import time


class FlightRecorder:
    def __init__(self, directory, pre_seconds=90, post_seconds=30, max_cases=20):
        self.directory = Path(directory)
        self.pre_seconds, self.post_seconds = pre_seconds, post_seconds
        self.max_cases = max_cases
        self.ring = deque(maxlen=512)
        self.seen = deque(maxlen=64)
        self.active = None
        self.captures = 0
        self.discarded = 0

    def _write(self, record):
        line = json.dumps(record, ensure_ascii=False) + '\n'
        if len(line.encode('utf-8')) > 16384:
            line = json.dumps({'kind': 'oversize-record-omitted'}) + '\n'
        self.active['stream'].write(line)
        self.active['stream'].flush()

    def advance(self, now):
        while self.ring and self.ring[0][0] < now - self.pre_seconds:
            self.ring.popleft()
            self.discarded += 1
        if self.active and now >= self.active['end']:
            self.finish(now)

    def add(self, record, now):
        self.advance(now)
        self.ring.append((now, record))
        if self.active:
            self._write(record)

    def trigger(self, event, now):
        identity = str(event.get('id', ''))
        if not identity or identity in self.seen:
            return False
        self.advance(now)
        self.seen.append(identity)
        name = 'fallback-' + hashlib.sha256(identity.encode()).hexdigest()[:16] + '.jsonl'
        target = self.directory / name
        if target.exists():
            return False
        marker = {'kind': 'fallback', 'event': event}
        if self.active:
            # Additional failures are recorded without extending the 120-second window.
            self._write(marker)
            return True
        self.directory.mkdir(parents=True, exist_ok=True)
        self.active = dict(stream=target.open('x', encoding='utf-8'), path=target,
                           start=now, end=now + self.post_seconds)
        self._write({'kind': 'capture-start', 'pre_seconds': self.pre_seconds,
                     'post_seconds': self.post_seconds,
                     'available_pre_seconds': min(self.pre_seconds, now-self.ring[0][0]) if self.ring else 0})
        for _, record in self.ring:
            self._write(record)
        self._write(marker)
        self.captures += 1
        files = sorted((f for f in self.directory.glob('fallback-*.jsonl') if f != target),
                       key=lambda f: (f.stat().st_mtime_ns, f.name))
        # Exclude the active file before pruning: coarse/equal mtimes must not
        # accidentally select it, skip deletion and leave an extra old case.
        for old in files[:max(0, len(files)-(self.max_cases-1))]:
            old.unlink()
        return True

    def finish(self, now, reason='post-window-complete'):
        if self.active:
            self._write({'kind': 'capture-end', 'reason': reason,
                         'post_seconds_observed': max(0, now-self.active['start'])})
            self.active['stream'].close()
            self.active = None

    def status(self):
        return dict(mode='incident-only', ring_records=len(self.ring), discarded=self.discarded,
                    captures=self.captures, recording=self.active is not None,
                    pre_seconds=self.pre_seconds, post_seconds=self.post_seconds)


STATE_JS = r"""
var p=this._mcpSnapshotPolicy;
if(!p)sb.append(JSON.stringify({installed:false}));
else sb.append(JSON.stringify({installed:!!p.interestInstalled,enabled:!!p.interestEnabled,
stagger:!!p.interestStaggerEnabled,farBuckets:!!p.interestFarBucketsEnabled,
relaxed:!!p.interestRelaxedGuards,unitMode:p.interestUnitMode,
buildingMode:p.interestBuildingEffectiveMode,buildingCount:p.interestBuildingCount,
players:Groups.player.size(),units:Groups.unit.size(),map:String(Vars.state.map.name()),
maxPlayers:p.interestMaxPlayers,maxEntities:p.interestMaxEntities,
pid:p.interestPid||p.interestDiagnosticPid,tid:p.interestTid||p.interestDiagnosticTid,
ticks:p.interestTicks,phases:p.interestPhaseTicks,buckets:p.interestFarBucketRounds,
entityRecords:p.interestEntityRecords,buildingRecords:p.interestBuildingRecords,
maxSelection:p.interestEntityMaxSelection,workLastMs:p.interestWorkLastMs,
workMaxMs:p.interestWorkMaxMs,slowCount:p.interestSlowCount,memory:p.interestMemorySample,
fallback:p.interestLastFallbackEvent||null,recorderError:p.interestRecorderError||null,
interval:Packages.mindustry.net.Administration.Config.snapshotInterval.num(),
entityInterval:p.interestEntityIntervalMs||Packages.mindustry.net.Administration.Config.snapshotInterval.num(),
farBucketCount:p.interestFarBucketCount,controlledOutsideView:!!p.controlledOutsideView,controlledInterval:p.controlledInterval,
reactorEnabled:!!p.interestReactorEnabled,reactorInterval:p.interestReactorIntervalMs,
reactorThreshold:p.interestReactorHeatThreshold,reactorCandidates:p.interestReactorCount,
reactorTicks:p.interestReactorTicks,reactorRecords:p.interestReactorRecords,reactorMaxAgeMs:p.interestReactorMaxAgeMs}));
"""


def poll_world():
    from . import world_api
    from .world_interest_diagnostics import pressure_snapshot
    # Explicit hs bypasses the sleep supervisor; this must never wake a world.
    result = world_api.call({'op': 'js', 'code': STATE_JS},
                           hs=world_api.handshake(), timeout=2)
    if not result.get('ok'):
        raise RuntimeError('world telemetry unavailable')
    state = json.loads(result['lines'][-1])
    sample = {'kind': 'world', 'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'state': state}
    if state.get('pid'):
        sample['pressure'] = pressure_snapshot(state['pid'], tid=state.get('tid'))
    return sample


class WorldSampler:
    def __init__(self, interval=5, poll=poll_world):
        self.interval, self.poll = interval, poll
        self.items = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name='world-telemetry', daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            try:
                sample = self.poll()
            except Exception as exc:
                sample = {'kind': 'world-unavailable', 'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                          'error_type': type(exc).__name__}
            item = (time.monotonic(), sample)
            try:
                self.items.put_nowait(item)
            except queue.Full:
                try:
                    self.items.get_nowait()
                except queue.Empty:
                    pass
                self.items.put_nowait(item)
            self.stop_event.wait(self.interval)

    def drain(self):
        result = []
        while True:
            try:
                result.append(self.items.get_nowait())
            except queue.Empty:
                return result

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=3)
