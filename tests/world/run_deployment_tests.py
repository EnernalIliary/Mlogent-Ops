"""Keep the deployed Unicode banner below the native discovery byte limit."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class DeploymentTests(unittest.TestCase):
    def test_native_icon_banner_is_real_utf8_without_question_mark_replacement(self):
        profile=json.loads((ROOT/'deploy/snapshot-profile.example.json').read_text(encoding='utf-8'))
        message=profile['runningDescription']
        self.assertIn('\u9644\u5c5e\u670d',message)
        self.assertIn('\ue809',message);self.assertIn('\uf308',message)
        self.assertNotIn('?',message);self.assertNotIn(':star:',message);self.assertNotIn(':github:',message)
        self.assertIn('\n',message);self.assertLessEqual(len(message.encode('utf-8')),100)
        self.assertTrue(message.endswith('EnernalIliary/Mlogent'))

    def test_eight_player_profile_and_standalone_service_entrypoint(self):
        profile=json.loads((ROOT/'deploy/snapshot-profile.example.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['playerLimit'],8)
        service=(ROOT/'deploy/mlogent-world-traffic.service').read_text(encoding='utf-8')
        self.assertIn('WorkingDirectory=/opt/mlogent-ops',service)
        self.assertIn('-m mlogent_ops.world_traffic',service)
        self.assertNotIn('/tools/world_traffic.py',service)


if __name__=='__main__':unittest.main()
