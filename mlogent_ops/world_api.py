"""Small existing-daemon protocol client; never starts or wakes a game world."""
import json
import os
from pathlib import Path
import socket


def core_root(root=None):
    value = root or os.environ.get('MLOGENT_ROOT')
    if not value:
        raise RuntimeError('Set MLOGENT_ROOT to the Mlogent checkout or deployed release')
    return Path(value).resolve()


def handshake(root=None):
    path = core_root(root) / 'out/_world/daemon.json'
    if path.stat().st_size > 65536:
        raise ValueError('Oversize local world handshake')
    result = json.loads(path.read_text(encoding='utf-8'))
    if not 1 <= int(result['apiPort']) <= 65535:
        raise ValueError('Invalid local control port')
    return result


def call(request, timeout=2, hs=None, root=None):
    connection = hs if hs is not None else handshake(root)
    with socket.create_connection(('127.0.0.1', int(connection['apiPort'])), timeout=timeout) as stream:
        stream.settimeout(timeout)
        stream.sendall((json.dumps(request, ensure_ascii=False)+'\n').encode('utf-8'))
        data = bytearray()
        while not data.endswith(b'\n'):
            part = stream.recv(65536)
            if not part:
                break
            data.extend(part)
            if len(data) > 4*1024*1024:
                raise ValueError('Oversize local world response')
    if not data:
        raise RuntimeError('Local world control socket returned no data')
    return json.loads(data.decode('utf-8'))
