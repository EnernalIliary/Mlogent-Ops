#!/usr/bin/env python3
"""Passive IPv4 game-port accounting; no packet contents or peer IPs stored.

Counts IP bytes (including IP/TCP/UDP headers), not Ethernet overhead.
Noninitial IP fragments cannot be classified by port and are excluded.
"""
import argparse
import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import select
import socket
import time
import os
import signal


def resources(memory_group=Path('/sys/fs/cgroup/memory/system.slice/mlogent-world.service'),
              proc_root=Path('/proc')):
    """Read-only pressure context; cumulative faults let successive samples show rates."""
    result = {}
    try:
        meminfo = {line.split(':')[0]: int(line.split()[1]) * 1024
                   for line in (proc_root / 'meminfo').read_text().splitlines()
                   if line.split(':')[0] in ('MemAvailable', 'SwapTotal', 'SwapFree')}
        result['host_available_bytes'] = meminfo['MemAvailable']
        result['host_swap_bytes'] = meminfo['SwapTotal'] - meminfo['SwapFree']
        usage = int((memory_group / 'memory.usage_in_bytes').read_text())
        memsw = int((memory_group / 'memory.memsw.usage_in_bytes').read_text())
        result['world_memory_bytes'] = usage
        result['world_swap_bytes'] = max(0, memsw - usage)
        stat = dict(line.split() for line in (memory_group / 'memory.stat').read_text().splitlines())
        result['world_major_faults'] = int(stat.get('total_pgmajfault', stat.get('pgmajfault', 0)))
    except (OSError, ValueError, KeyError) as exc:
        result['collection_error'] = type(exc).__name__
    return result


def classify(packet, port):
    if len(packet) < 34 or packet[12:14] != b'\x08\x00':
        return None
    offset = 14 + (packet[14] & 15) * 4
    if packet[23] not in (6, 17) or len(packet) < offset + 4:
        return None
    if int.from_bytes(packet[20:22], 'big') & 0x1fff:
        return None
    src = int.from_bytes(packet[offset:offset + 2], 'big')
    dst = int.from_bytes(packet[offset + 2:offset + 4], 'big')
    if port not in (src, dst):
        return None
    return ('tcp' if packet[23] == 6 else 'udp',
            int.from_bytes(packet[16:18], 'big'))


def peak_rates(bins, keys, seconds):
    """Fixed-width bucket peaks in bits/second, including empty intervals."""
    return {k: round(max((b.get(k, 0) for b in bins.values()), default=0)
                     * 8 / seconds, 1) for k in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='eth0')
    parser.add_argument('--port', type=int, default=6567)
    parser.add_argument('--output')
    parser.add_argument('--incident-dir')
    parser.add_argument('--event-file')
    parser.add_argument('--status-file')
    parser.add_argument('--sample-seconds', type=float, default=10)
    args = parser.parse_args()
    if args.sample_seconds < 1 or (not args.output and not args.incident_dir):
        parser.error('Specify --output or --incident-dir; sample interval must be >= 1 second')
    recorder, sampler, logger = None, None, None
    latest_state, latest_world_at, world_available = None, None, None
    if args.incident_dir:
        from .world_flight_recorder import FlightRecorder, WorldSampler
        recorder, sampler = FlightRecorder(args.incident_dir), WorldSampler()
        sampler.start()
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger('traffic')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(args.output, maxBytes=10 * 1024 * 1024,
                                     backupCount=2, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
    sock.bind((args.interface, 0))
    sock.setblocking(False)
    started = time.monotonic()
    keys = ('tcp_in', 'tcp_out', 'udp_in', 'udp_out')
    totals = dict.fromkeys(keys, 0)
    bins, short_bins = {}, {}
    running, status_at, monitor_at = True, 0, 0
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        now = time.monotonic()
        if recorder and now >= monitor_at:
            monitor_at = now + .25
            recorder.advance(now)
            for observed, record in sampler.drain():
                recorder.add(record, observed)
                if record['kind'] == 'world':
                    latest_state = record['state']
                    latest_world_at, world_available = record['time_utc'], True
                elif record['kind'] == 'world-unavailable':
                    world_available = False
            event = None
            if args.event_file:
                try:
                    event = json.loads(Path(args.event_file).read_text())
                except (OSError, ValueError):
                    pass
            if event is None and latest_state:
                event = latest_state.get('fallback')
            if event and 0 <= time.time()-event.get('at', 0)/1000 <= 120:
                recorder.trigger(event, now)
                if args.event_file:
                    try:
                        marker = Path(args.event_file)
                        if json.loads(marker.read_text()).get('id') == event.get('id'):
                            marker.unlink()
                    except (OSError, ValueError):
                        pass
            if args.status_file and now >= status_at:
                status_at = now + 2
                target = Path(args.status_file)
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix('.tmp')
                tmp.write_text(json.dumps(dict(recorder.status(), world=latest_state,
                                              world_available=world_available, world_observed_utc=latest_world_at,
                                              time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())))
                os.replace(tmp, target)
        if now - started >= args.sample_seconds:
            seconds = now - started
            record = {
                'kind': 'traffic',
                'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'seconds': round(seconds, 3), 'port': args.port,
                'resources': resources(),
                'bytes': totals,
                'mean_bps': {k: round(v * 8 / seconds, 1) for k, v in totals.items()},
                'peak_1s_bps': peak_rates(bins, keys, 1),
                'peak_100ms_bps': peak_rates(short_bins, keys, .1),
            }
            if recorder:
                recorder.add(record, now)
            else:
                logger.info(json.dumps(record))
            started = now
            totals, bins, short_bins = dict.fromkeys(keys, 0), {}, {}
        if not select.select([sock], [], [], min(.25 if recorder else 1,
                                                max(0, args.sample_seconds - (now - started))))[0]:
            continue
        packet, address = sock.recvfrom(65535)
        parsed = classify(packet, args.port)
        if parsed is None:
            continue
        protocol, size = parsed
        key = protocol + ('_out' if address[2] == socket.PACKET_OUTGOING else '_in')
        totals[key] = totals.get(key, 0) + size
        elapsed = time.monotonic() - started
        second = int(elapsed)
        bucket = bins.setdefault(second, {})
        bucket[key] = bucket.get(key, 0) + size
        short_bucket = short_bins.setdefault(int(elapsed * 10), {})
        short_bucket[key] = short_bucket.get(key, 0) + size
    sock.close()
    if sampler:
        sampler.stop()
        recorder.finish(time.monotonic(), reason='collector-stopped')


if __name__ == '__main__':
    main()
