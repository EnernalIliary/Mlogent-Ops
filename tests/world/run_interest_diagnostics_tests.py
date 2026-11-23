"""Deterministic AOI observer and Linux-counter parsing tests; no live world."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_interest_diagnostics import INSTALL_JS, pressure_snapshot, pressure_delta
from mlogent_ops.world_interest_policy import INSTALL_JS as POLICY_JS
from run_interest_policy_tests import HARNESS


class DiagnosticsTests(unittest.TestCase):
    def test_linux_counters_units_and_process_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / '123'
            process.mkdir()
            fields = ['S'] + ['0'] * 19
            for i, value in {7: '100', 9: '5', 11: '200', 12: '30', 19: '987'}.items():
                fields[i] = value
            (process / 'stat').write_text('123 (java worker) ' + ' '.join(fields))
            (process / 'status').write_text('VmRSS: 1000 kB\nVmSwap: 20 kB\n')
            (process / 'schedstat').write_text('10000000 3000000 10')
            (root / 'cpu.stat').write_text('nr_periods 20\nnr_throttled 3\nthrottled_time 9000000\n')
            (root / 'meminfo').write_text('MemAvailable: 200000 kB\n')
            sample = pressure_snapshot(123, root, root, clock_ticks=100)
            self.assertNotIn('collection_errors', sample)
            self.assertEqual(sample['process_cpu_ns'], 2300000000)
            self.assertEqual(sample['start_ticks'], 987)
            self.assertEqual(sample['major_faults'], 5)
            self.assertEqual(sample['swap_bytes'], 20 * 1024)
            self.assertEqual(sample['scheduler_wait_ns'], 3000000)
            self.assertEqual(sample['scheduler_scope'], 'leader')
            (process / 'task/124').mkdir(parents=True)
            (process / 'task/124/schedstat').write_text('5000 6000 7')
            thread = pressure_snapshot(123, root, root, clock_ticks=100, tid=124)
            self.assertEqual(thread['scheduler_wait_ns'], 6000)
            self.assertEqual(thread['scheduler_scope'], 'game_thread')
            self.assertEqual(sample['cgroup_throttled_ns'], 9000000)
            (root / 'cpu.stat').write_text('nr_throttled 4\nthrottled_usec 12000\n')
            self.assertEqual(pressure_snapshot(123, root, root, 100)['cgroup_throttled_ns'], 12000000)

    def test_counter_delta_rejects_pid_reuse_and_counter_resets(self):
        before = dict(pid=1, start_ticks=20, monotonic=10, process_cpu_ns=1000000000,
                      major_faults=5, cgroup_nr_throttled=10)
        after = dict(before, monotonic=12, process_cpu_ns=1500000000,
                     major_faults=8, cgroup_nr_throttled=1)
        delta = pressure_delta(before, after)
        self.assertEqual(delta['cpu_cores'], .25)
        self.assertEqual(delta['major_faults'], 3)
        self.assertNotIn('cgroup_nr_throttled', delta)
        self.assertTrue(pressure_delta(before, dict(after, start_ticks=30))['process_changed'])

    def test_missing_metrics_are_reported_not_fallback_zeros(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = pressure_snapshot(123, Path(directory), Path(directory), 100)
            self.assertIn('process_stat', sample['collection_errors'])
            self.assertIn('cpu_cgroup', sample['collection_errors'])
            self.assertNotIn('major_faults', sample)

    def test_jvm_observer_hooks_and_guard_failures(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source.policy,ctx);
assert.equal(policy.interestDiagnosticsEnabled,false);
let cpuNs=0,gcCount=0,gcMs=0,loaded=100,compiled=10,supported=true,cpuFailure=false,unsupportedGc=false;
const advance=(wall,cpu)=>{nanosOffset+=wall*1000000;cpuNs+=cpu*1000000;};
const thread={isCurrentThreadCpuTimeSupported:()=>supported,isThreadCpuTimeEnabled:()=>true,
 setThreadCpuTimeEnabled(){},getCurrentThreadCpuTime(){if(cpuFailure)throw Error('cpu observer failed');return cpuNs;}};
ctx.Packages.java={lang:{management:{ManagementFactory:{getThreadMXBean:()=>thread,
 getGarbageCollectorMXBeans:()=>({toArray:()=>[{
 getCollectionCount:()=>unsupportedGc?-1:gcCount,getCollectionTime:()=>unsupportedGc?-1:gcMs}]}),
 getClassLoadingMXBean:()=>({getTotalLoadedClassCount:()=>loaded}),
 getCompilationMXBean:()=>({isCompilationTimeMonitoringSupported:()=>true,getTotalCompilationTime:()=>compiled}),
 getRuntimeMXBean:()=>({getName:()=>'123@host'})}}}};
ctx.java.lang.management=ctx.Packages.java.lang.management;
ctx.java.lang.Boolean={TYPE:'boolean',valueOf:v=>v};ctx.java.lang.Integer={TYPE:'int',valueOf:v=>v};
ctx.java.lang.Class={forName:iface=>({getMethod:name=>({invoke:(target,...args)=>
 iface==='java.lang.management.ManagementFactory'?ctx.java.lang.management.ManagementFactory[name]():target[name](...args)})})};
vm.runInContext(source.diagnostics,ctx);
assert.equal(policy.interestDiagnosticPid,123);assert.equal(policy.interestDiagnosticsEnabled,true);
policy.interestDiagnostics.warmupTraces=2;policy.interestLastBase=0;
policy.interestDiagnosticBegin(now);
advance(1,.4);policy.interestDiagnosticMark('preflight');
advance(2,1);policy.interestDiagnosticMark('native-update');
advance(5,3);policy.interestDiagnosticMark('state');
advance(4,1);gcCount++;gcMs+=2;loaded+=3;compiled++;
policy.interestDiagnosticEnd(null);
let r=policy.interestDiagnostics.records.at(-1);
assert.equal(r.phase,'warmup');assert.equal(r.wallMs,12);assert.equal(r.addedWallMs,6);
assert.equal(r.threadCpuMs,5.4);assert.ok(Math.abs(r.addedCpuMs-2)<.000001);
assert.equal(r.gcCountDelta,1);assert.equal(r.gcTimeMsDelta,2);assert.equal(r.classesLoadedDelta,3);
assert.equal(r.compileTimeMsDelta,1);assert.equal(r.error,null);
policy.interestDiagnostics.limit=3;
for(let i=0;i<5;i++){policy.interestDiagnosticBegin(now);advance(1,.5);policy.interestDiagnosticEnd(null);}
assert.equal(policy.interestDiagnostics.records.length,3);
assert.equal(policy.interestDiagnostics.records.at(-1).phase,'measured');
// Production hook records success and hard fallback without altering the hard guard.
original.update=()=>{updates++;advance(3,1);};
original.writeStateSnapshot=()=>{states++;advance(3,1);};
original.writeCustomEntitySnapshot=()=>advance(1,1);
now+=250;policy.interestLastBase=0;policy.interestUpdate();
assert.equal(policy.interestEnabled,true);r=policy.interestDiagnostics.records.at(-1);
assert.equal(r.nativeWallMs,3);assert.ok(r.addedWallMs>=4);assert.equal(r.error,null);
// A native update can cross the due boundary after the initial observer check.
policy.interestLastBase=now;now+=249;
original.update=()=>{now+=2;};
policy.interestUpdate();r=policy.interestDiagnostics.records.at(-1);
assert.equal(r.scope,'send-only');assert.equal(r.error,null);
// Every actual staggered phase is observable even within the previous base interval.
policy.interestStaggerEnabled=true;policy.interestPhaseOrigin=null;
policy.interestLastUpdate=0;policy.interestUpdate();
const sequences=policy.interestDiagnostics.sequence;
now+=84;policy.interestUpdate();
assert.equal(policy.interestDiagnostics.sequence,sequences+1);
assert.equal(policy.interestDiagnostics.records.at(-1).scope,'send-only');
policy.interestStaggerEnabled=false;
original.update=()=>{updates++;advance(3,1);};
original.writeStateSnapshot=()=>{advance(29,1);gcCount++;gcMs+=7;};
now+=250;policy.interestUpdate();
assert.equal(policy.interestEnabled,false);r=policy.interestDiagnostics.records.at(-1);
assert.match(r.error,/budget/);assert.equal(r.stages.state.wallMs,29);
assert.equal(r.gcTimeMsDelta,7);assert.ok(r.nonCpuWallMs>=28);
// Split building timings distinguish encoding, copying and network dispatch.
policy.interestDeadlineNs=0;policy.interestBuildingSoftBudgetMs=50;
ctx.java.io.ByteArrayOutputStream.prototype.toByteArray=function(){advance(3,.1);return {bytes:this.n};};
ctx.Packages.mindustry.gen.Call.blockSnapshot=()=>advance(4,.2);
const building=build(2000,0);building.writeSync=w=>{w.s.n+=10;advance(2,1);};
policy.writeBuildings(receiver,policy.view(receiver),{},new Seq([building]),now);
assert.equal(policy.interestBuildingTimings.encode.lastMs,2);
assert.equal(policy.interestBuildingTimings.copy.lastMs,3);
assert.equal(policy.interestBuildingTimings.send.lastMs,4);
const cpuGetter=thread.getCurrentThreadCpuTime;
thread.getCurrentThreadCpuTime=()=>{advance(.1,.05);return cpuNs;};
policy.interestLastBase=0;policy.interestDiagnosticBegin(now);
policy.interestDeadlineNs=now*1000000+nanosOffset+5000000;
const oldDeadline=policy.interestDeadlineNs;policy.interestDiagnosticMark('state');
assert.ok(policy.interestDeadlineNs>oldDeadline);policy.interestDiagnosticEnd(null);
assert.ok(policy.interestDiagnostics.records.at(-1).observerWallMs>0);
policy.interestDeadlineNs=0;thread.getCurrentThreadCpuTime=cpuGetter;
// Missing CPU/GC support remains null, rather than looking like zero cost.
supported=false;unsupportedGc=true;vm.runInContext(source.diagnostics,ctx);
policy.interestLastBase=0;policy.interestDiagnosticBegin(now);advance(1,0);policy.interestDiagnosticEnd(null);
r=policy.interestDiagnostics.records.at(-1);assert.equal(r.threadCpuMs,null);assert.equal(r.gcCountDelta,null);
// A management API failure disables only optional diagnostics, never the game policy.
supported=true;unsupportedGc=false;vm.runInContext(source.diagnostics,ctx);cpuFailure=true;
policy.interestEnabled=true;policy.interestLastBase=0;policy.interestLastUpdate=0;policy.interestError=null;
original.writeStateSnapshot=()=>{};original.writeCustomEntitySnapshot=()=>{};
policy.interestBuildingSoftBudgetMs=2;policy.interestUpdate();
assert.equal(policy.interestDiagnosticsEnabled,false);assert.match(policy.interestDiagnostics.error,/observer failed/);
assert.equal(policy.interestEnabled,true);assert.equal(policy.interestError,null);
policy.disableInterestDiagnostics();assert.equal(policy.interestDiagnosticsEnabled,false);
console.log('opt-in observer, warmup labels, bounded records, CPU/GC attribution, split serialization and fail-open monitoring passed');
"""
        result = subprocess.run(['node', '-e', harness],
                                input=json.dumps({'policy': POLICY_JS, 'diagnostics': INSTALL_JS}),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
