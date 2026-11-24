"""Ephemeral per-address public-port accounting feeds per-player cadence.

No payloads, addresses or raw traffic history are persisted. Shared public
addresses are apportioned equally across their connected players.
"""
import json
import queue
import select
import socket
import threading
import time

from . import world_api
from .world_traffic import classify
from .world_resource_sampler import ResourceSampler


def outbound_peer(packet, address, port=6567):
    parsed = classify(packet, port)
    if not parsed or address[2] != socket.PACKET_OUTGOING:
        return None
    offset = 14+(packet[14] & 15)*4
    # Exclude inbound packets reflected through a local interface.
    if int.from_bytes(packet[offset:offset+2], 'big') != port:
        return None
    return socket.inet_ntoa(packet[30:34]), parsed[1]


def feedback_worker(items):
    sampler = ResourceSampler()
    while True:
        rates = items.get()
        try:
            hs = world_api.handshake()  # Explicit handshake never wakes the server.
            try:
                resources = sampler.sample(int(hs['pid']))
            except (OSError, ValueError, KeyError, StopIteration, ZeroDivisionError):
                resources = None
            code = ('var p=this._mcpSnapshotPolicy;'
                    'if(p&&p.adaptiveEnabled&&typeof p.adaptiveFeedback==="function")'
                    '{p.adaptiveFeedback('+json.dumps(rates)+',java.lang.System.currentTimeMillis());}'
                    'if(p&&p.adaptiveEnabled&&typeof p.adaptiveResourceFeedback==="function")'
                    '{p.adaptiveResourceFeedback('+json.dumps(resources)+',java.lang.System.currentTimeMillis());}'
                    'sb.append("bandwidth feedback");')
            world_api.call({'op':'js', 'code':code}, hs=hs, timeout=2)
        except (OSError, ValueError, RuntimeError, KeyError):
            pass  # Stale feedback automatically restores normal C cadence.


def main():
    items = queue.Queue(maxsize=1)
    threading.Thread(target=feedback_worker, args=(items,), daemon=True).start()
    capture = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
    capture.bind(('eth0', 0))
    capture.setblocking(False)
    started, totals = time.monotonic(), {}
    while True:
        now = time.monotonic()
        if now-started >= 2:
            rates = {ip: size*8/(now-started) for ip, size in totals.items()}
            try:
                items.put_nowait(rates)
            except queue.Full:
                pass
            started, totals = now, {}
        if not select.select([capture], [], [], .2)[0]:
            continue
        packet, address = capture.recvfrom(65535)
        peer = outbound_peer(packet, address)
        if peer:
            ip, size = peer
            # Bound memory even under discovery scans or spoofed packets.
            if ip in totals or len(totals) < 256:
                totals[ip] = totals.get(ip, 0)+size


if __name__ == '__main__':
    main()
