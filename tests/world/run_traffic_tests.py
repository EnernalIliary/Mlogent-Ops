"""Verify pressure metrics and graceful failure without touching host settings."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_traffic import resources, classify, peak_rates
from mlogent_ops.world_flight_recorder import FlightRecorder


class TrafficTests(unittest.TestCase):
    def test_normal_samples_never_reach_disk_and_expire_in_memory(self):
        with tempfile.TemporaryDirectory() as d:
            recorder = FlightRecorder(Path(d)/'incidents')
            for t in range(1000):
                recorder.add({'kind': 'traffic', 't': t}, t)
            self.assertLessEqual(len(recorder.ring), 91)
            self.assertGreater(recorder.discarded, 900)
            self.assertFalse((Path(d)/'incidents').exists())

    def test_fallback_keeps_only_90_seconds_before_and_30_after(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            recorder = FlightRecorder(d)
            for t in range(101):
                recorder.add({'t': t}, t)
            self.assertTrue(recorder.trigger({'id': 'one'}, 100))
            self.assertFalse(recorder.trigger({'id': 'one'}, 105))
            for t in range(101, 141):
                recorder.add({'t': t}, t)
            self.assertIsNone(recorder.active)
            files = list(Path(d).glob('fallback-*.jsonl'))
            self.assertEqual(len(files), 1)
            records = [json.loads(line) for line in files[0].read_text().splitlines()]
            times = [r['t'] for r in records if 't' in r]
            self.assertEqual((min(times), max(times)), (10, 129))
            self.assertEqual(records[-1]['kind'], 'capture-end')
            # A collector restart must not overwrite/replay an existing case.
            self.assertFalse(FlightRecorder(d).trigger({'id': 'one'}, 145))

    def test_additional_events_cannot_extend_window_and_case_count_is_bounded(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            recorder = FlightRecorder(d, max_cases=2)
            recorder.trigger({'id': 'first'}, 100)
            recorder.trigger({'id': 'second'}, 125)
            recorder.advance(130)
            self.assertIsNone(recorder.active)
            recorder.trigger({'id': 'third'}, 140);recorder.advance(170)
            for path in Path(d).glob('fallback-*.jsonl'):os.utime(path,(1,1))
            recorder.trigger({'id': 'fourth'}, 180);recorder.advance(210)
            self.assertEqual(len(list(Path(d).glob('fallback-*.jsonl'))), 2)

    def test_peak_bucket_units_and_empty_intervals(self):
        bins = {0: {'udp_out': 1000}, 3: {'udp_out': 2000, 'tcp_in': 50}}
        keys = ('udp_out', 'tcp_in', 'udp_in')
        self.assertEqual(peak_rates(bins, keys, .1),
                         {'udp_out': 160000., 'tcp_in': 4000., 'udp_in': 0.})
        self.assertEqual(peak_rates(bins, keys, 1)['udp_out'], 16000.)
        self.assertEqual(peak_rates({}, keys, .1), dict.fromkeys(keys, 0.))

    def test_resource_units_and_cumulative_faults(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'meminfo').write_text('MemAvailable: 200000 kB\nSwapTotal: 2000 kB\nSwapFree: 1500 kB\n')
            (root / 'memory.usage_in_bytes').write_text('5000')
            (root / 'memory.memsw.usage_in_bytes').write_text('8000')
            (root / 'memory.stat').write_text('pgmajfault 10\ntotal_pgmajfault 11\n')
            r = resources(root, root)
            self.assertEqual(r['host_available_bytes'], 200000 * 1024)
            self.assertEqual(r['host_swap_bytes'], 500 * 1024)
            self.assertEqual(r['world_swap_bytes'], 3000)
            self.assertEqual(r['world_major_faults'], 11)
            self.assertNotIn('collection_error', r)

    def test_metrics_unavailable_does_not_stop_traffic_logger(self):
        with tempfile.TemporaryDirectory() as d:
            r = resources(Path(d), Path(d))
            self.assertEqual(r['collection_error'], 'FileNotFoundError')

    def test_game_port_and_fragment_classification(self):
        p = bytearray(42)
        p[12:14] = bytes.fromhex('0800')
        p[14] = 69
        p[16:18] = (28).to_bytes(2, 'big')
        p[23] = 17
        p[34:36] = (6567).to_bytes(2, 'big')
        self.assertEqual(classify(p, 6567), ('udp', 28))
        self.assertIsNone(classify(p, 1234))
        p[20:22] = (1).to_bytes(2, 'big')
        self.assertIsNone(classify(p, 6567))


if __name__ == '__main__':
    unittest.main()
