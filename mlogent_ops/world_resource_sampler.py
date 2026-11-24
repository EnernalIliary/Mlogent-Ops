"""Read bounded Linux CPU/memory counters for the running world cgroup."""
from pathlib import Path
import os
import time


class ResourceSampler:
    def __init__(self, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup')):
        self.proc, self.cgroups = Path(proc), Path(cgroups)
        self.previous = None

    def sample(self, pid, now=None):
        now = time.monotonic() if now is None else now
        entries = [line.split(':', 2) for line in (self.proc / str(pid) / 'cgroup').read_text().splitlines()]
        v2 = next((path for _, controllers, path in entries if not controllers), None)
        if v2 is not None:
            group = self.cgroups / v2.lstrip('/')
            quota, period = (group / 'cpu.max').read_text().split()
            budget = int(quota) / int(period) if quota != 'max' else os.cpu_count() or 1
            counters = dict(line.split() for line in (group / 'cpu.stat').read_text().splitlines())
            usage = int(counters['usage_usec']) * 1000
        else:
            path = next(path for _, controllers, path in entries if 'cpuacct' in controllers.split(','))
            candidates = [self.cgroups / mount / path.lstrip('/') for mount in ('cpu,cpuacct', 'cpuacct,cpu', 'cpuacct')]
            group = next(p for p in candidates if (p / 'cpuacct.usage').is_file())
            usage = int((group / 'cpuacct.usage').read_text())
            quota_group = group if (group / 'cpu.cfs_quota_us').is_file() else self.cgroups / 'cpu' / path.lstrip('/')
            quota, period = int((quota_group / 'cpu.cfs_quota_us').read_text()), int((quota_group / 'cpu.cfs_period_us').read_text())
            budget = quota / period if quota > 0 else os.cpu_count() or 1
        cpu = [int(value) for value in (self.proc / 'stat').read_text().splitlines()[0].split()[1:9]]
        total, idle = sum(cpu), cpu[3] + cpu[4]
        available = next(int(line.split()[1]) for line in (self.proc / 'meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        current = (pid, str(group), now, usage, total, idle)
        previous, self.previous = self.previous, current
        if previous is None or previous[:2] != current[:2]:
            return None
        elapsed, used, ticks, idle_ticks = now - previous[2], usage - previous[3], total - previous[4], idle - previous[5]
        if not .5 <= elapsed <= 10 or used < 0 or ticks <= 0 or idle_ticks < 0:
            return None
        return {'cpuRatio': used / (elapsed * 1e9 * budget), 'cpuBudgetCores': budget,
                'hostCpuRatio': max(0, min(1, 1 - idle_ticks / ticks)), 'availableKB': available}
