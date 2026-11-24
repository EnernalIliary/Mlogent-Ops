"""Resource feedback is normalized to the world's assigned CPU budget."""
from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_resource_sampler import ResourceSampler

class SamplerTests(unittest.TestCase):
    def test_v2_quota_normalization_and_process_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);proc=root/'proc';group=root/'cgroup/world'
            (proc/'123').mkdir(parents=True);group.mkdir(parents=True)
            (proc/'123/cgroup').write_text('0::/world\n')
            (group/'cpu.max').write_text('100000 100000\n')
            (group/'cpu.stat').write_text('usage_usec 1000000\n')
            (proc/'stat').write_text('cpu 100 0 0 100 0 0 0 0\n')
            (proc/'meminfo').write_text('MemAvailable: 300000 kB\n')
            s=ResourceSampler(proc,root/'cgroup')
            self.assertIsNone(s.sample(123,1))
            (group/'cpu.stat').write_text('usage_usec 2000000\n')
            (proc/'stat').write_text('cpu 200 0 0 200 0 0 0 0\n')
            value=s.sample(123,3)
            self.assertEqual(value,{'cpuRatio':.5,'cpuBudgetCores':1,'hostCpuRatio':.5,'availableKB':300000})
            self.assertIsNone(s.sample(123,30))

    def test_v1_shared_cpu_controller_and_unlimited_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);proc=root/'proc';group=root/'cgroup/cpu,cpuacct/system.slice/world'
            (proc/'1').mkdir(parents=True);group.mkdir(parents=True)
            (proc/'1/cgroup').write_text('2:cpu,cpuacct:/system.slice/world\n')
            (group/'cpu.cfs_quota_us').write_text('50000')
            (group/'cpu.cfs_period_us').write_text('100000')
            (group/'cpuacct.usage').write_text('1000000000')
            (proc/'stat').write_text('cpu 100 0 0 100 0 0 0 0\n')
            (proc/'meminfo').write_text('MemAvailable: 200000 kB\n')
            sampler=ResourceSampler(proc,root/'cgroup')
            self.assertIsNone(sampler.sample(1,0))
            (group/'cpuacct.usage').write_text('1500000000')
            (proc/'stat').write_text('cpu 200 0 0 200 0 0 0 0\n')
            result=sampler.sample(1,2)
            self.assertEqual(result['cpuRatio'],.5)
            self.assertEqual(result['cpuBudgetCores'],.5)

if __name__=='__main__':unittest.main()
