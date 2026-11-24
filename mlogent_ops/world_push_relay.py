"""Deliver native game requests to the server Agent inbox. No chat-group sender."""
import json
import os
from pathlib import Path
import re
import time

from .world_push_inbox import remember

SPOOL = Path(os.environ.get('MLOGENT_PUSH_SPOOL', '/opt/mlogent/out/_world/server/push_replies'))
AGENT_CHANNEL = os.environ.get('MLOGENT_PUSH_AGENT_CHANNEL', '1103525264')


def collect_native_push(spool=None, deliver=None, now=None):
    spool = Path(spool) if spool is not None else SPOOL
    deliver = deliver or remember
    now = time.time() if now is None else now
    delivered = 0
    paths = sorted(spool.glob('*.json'), key=lambda p: p.stat().st_mtime_ns)
    for path in paths[:25]:
        if not re.fullmatch('[a-f0-9]{32}', path.stem):
            continue
        try:
            if path.stat().st_size > 20000:
                raise ValueError('Oversize push event')
            row = json.loads(path.read_text(encoding='utf-8'))
            if (row.get('reply_id') != path.stem or type(row.get('created_ms')) not in (int, float)
                    or not isinstance(row.get('message'), str) or not row['message'].strip()):
                raise ValueError('Invalid push event')
        except (ValueError, TypeError, KeyError):
            path.rename(path.with_suffix('.invalid'))
            continue
        if not 0 <= now * 1000 - row['created_ms'] < 240000:
            path.rename(path.with_suffix('.expired'))
            continue
        # A failed inbox write leaves the durable source queued for retry.
        deliver(AGENT_CHANNEL, [row])
        path.unlink()
        delivered += 1
    return delivered


def main():
    print('Game push -> server Agent inbox relay started', flush=True)
    while True:
        try:
            count = collect_native_push()
            if count:
                print('Queued %d request(s) for the server Agent' % count, flush=True)
        except Exception as exc:
            print('Agent inbox delivery retry: ' + type(exc).__name__, flush=True)
        time.sleep(2)


if __name__ == '__main__':
    main()
