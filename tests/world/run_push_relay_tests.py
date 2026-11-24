"""Private Agent inbox delivery must survive retries without group broadcasting."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops import world_push_relay as relay, world_push_inbox as inbox

class RelayTests(unittest.TestCase):
    def test_native_request_reaches_bounded_agent_inbox_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/('a'*32+'.json'); target=root/'inbox.data'
            row={'reply_id':'a'*32,'created_ms':100000,'player':'player','message':'private request','tick':12}
            source.write_text(json.dumps(row))
            with patch.object(inbox,'INBOX',target):
                self.assertEqual(relay.collect_native_push(root,now=101),1)
                inbox.remember(relay.AGENT_CHANNEL,[row])
            data=json.loads(target.read_text())
            self.assertEqual(data['group'],relay.AGENT_CHANNEL)
            self.assertEqual(len(data['rows']),1)
            self.assertEqual(data['rows'][0]['reply_id'],'a'*32)
            self.assertEqual(data['rows'][0]['text'],'private request')
            self.assertFalse(source.exists())

    def test_failed_inbox_write_keeps_request_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/('a'*32+'.json')
            source.write_text(json.dumps({'reply_id':'a'*32,'created_ms':100000,'message':'request'}))
            def fail(*args):raise OSError('disk unavailable')
            with self.assertRaises(OSError):relay.collect_native_push(folder,deliver=fail,now=101)
            self.assertTrue(source.exists())

    def test_stale_and_malformed_requests_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/('a'*32+'.json');b=Path(folder)/('b'*32+'.json')
            a.write_text(json.dumps({'reply_id':'a'*32,'created_ms':0,'message':'expired'}))
            b.write_text('{broken')
            def fail(*args):raise AssertionError('Must not deliver stale records')
            self.assertEqual(relay.collect_native_push(folder,deliver=fail,now=1000),0)
            self.assertTrue(a.with_suffix('.expired').exists())
            self.assertTrue(b.with_suffix('.invalid').exists())

if __name__=='__main__':unittest.main()
