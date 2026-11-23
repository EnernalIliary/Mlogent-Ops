"""Verify the local daemon client without a real Mlogent or world process."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_api import call, handshake


class WorldApiTests(unittest.TestCase):
    def test_existing_local_control_socket_and_unicode_round_trip(self):
        with socket.socket() as server, tempfile.TemporaryDirectory() as directory:
            server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(3)
            root=Path(directory);(root/'out/_world').mkdir(parents=True)
            (root/'out/_world/daemon.json').write_text(json.dumps({'apiPort':server.getsockname()[1]}))
            requests=[]
            def serve():
                with server.accept()[0] as stream:
                    data=b''
                    while not data.endswith(b'\n'):data+=stream.recv(4096)
                    requests.append(json.loads(data))
                    stream.sendall((json.dumps({'ok':True,'lines':['测试']})+'\n').encode())
            worker=threading.Thread(target=serve);worker.start()
            with patch.dict(os.environ,{'MLOGENT_ROOT':str(root)}):
                result=call({'op':'js','code':'read-only probe'},timeout=2)
            worker.join(3)
            self.assertEqual(result['lines'],['测试']);self.assertEqual(requests[0]['op'],'js')

    def test_missing_existing_world_never_tries_to_start_or_wake_one(self):
        with tempfile.TemporaryDirectory() as directory, patch('socket.create_connection') as connect:
            with self.assertRaises(FileNotFoundError):call({'op':'ping'},root=directory)
            connect.assert_not_called()

    def test_invalid_control_port_is_rejected_before_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'out/_world').mkdir(parents=True)
            (root/'out/_world/daemon.json').write_text('{"apiPort":70000}')
            with self.assertRaises(ValueError):handshake(root)


if __name__=='__main__':unittest.main()
