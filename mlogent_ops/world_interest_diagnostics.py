"""Opt-in AOI timing hooks and passive Linux pressure sampling.

Neither the sampler nor importing this module wakes or changes a game world.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import time


def pressure_snapshot(pid, proc_root=Path('/proc'),
                      cpu_group=Path('/sys/fs/cgroup/cpu,cpuacct/system.slice/mlogent-world.service'),
                      clock_ticks=None, tid=None):
    result = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'monotonic': time.monotonic(), 'pid': int(pid)}
    errors = {}
    process = proc_root / str(int(pid))
    try:
        text = (process / 'stat').read_text()
        fields = text[text.rindex(')') + 2:].split()
        ticks = clock_ticks or os.sysconf('SC_CLK_TCK')
        result.update(start_ticks=int(fields[19]), minor_faults=int(fields[7]),
                      major_faults=int(fields[9]),
                      process_cpu_ns=int((int(fields[11]) + int(fields[12])) * 1e9 / ticks))
    except (OSError, ValueError, IndexError, AttributeError) as exc:
        errors['process_stat'] = type(exc).__name__
    try:
        values = {line.split(':')[0]: int(line.split()[1]) * 1024
                  for line in (process / 'status').read_text().splitlines()
                  if line.split(':')[0] in ('VmRSS', 'VmSwap')}
        result.update({{'VmRSS': 'rss_bytes', 'VmSwap': 'swap_bytes'}[k]: v
                       for k, v in values.items()})
    except (OSError, ValueError, IndexError) as exc:
        errors['process_status'] = type(exc).__name__
    try:
        scheduler = process / 'task' / str(int(tid)) / 'schedstat' if tid else process / 'schedstat'
        fields = scheduler.read_text().split()
        result.update(scheduler_runtime_ns=int(fields[0]), scheduler_wait_ns=int(fields[1]),
                      scheduler_tid=int(tid or pid), scheduler_scope='game_thread' if tid else 'leader')
    except (OSError, ValueError, IndexError) as exc:
        errors['scheduler'] = type(exc).__name__
    try:
        values = dict(line.split() for line in (cpu_group / 'cpu.stat').read_text().splitlines())
        for key in ('nr_periods', 'nr_throttled'):
            if key in values:
                result['cgroup_' + key] = int(values[key])
        if 'throttled_time' in values:
            result['cgroup_throttled_ns'] = int(values['throttled_time'])
        elif 'throttled_usec' in values:
            result['cgroup_throttled_ns'] = int(values['throttled_usec']) * 1000
    except (OSError, ValueError) as exc:
        errors['cpu_cgroup'] = type(exc).__name__
    try:
        for line in (proc_root / 'meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                result['host_available_bytes'] = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError) as exc:
        errors['host_memory'] = type(exc).__name__
    if errors:
        result['collection_errors'] = errors
    return result


COUNTERS = ('minor_faults', 'major_faults', 'process_cpu_ns', 'scheduler_runtime_ns',
            'scheduler_wait_ns', 'cgroup_nr_periods', 'cgroup_nr_throttled', 'cgroup_throttled_ns')


def pressure_delta(before, after):
    elapsed = after['monotonic'] - before['monotonic']
    result = {'seconds': elapsed}
    if (before.get('pid'), before.get('start_ticks')) != (after.get('pid'), after.get('start_ticks')):
        result['process_changed'] = True
        return result
    for key in COUNTERS:
        if key in before and key in after and after[key] >= before[key]:
            result[key] = after[key] - before[key]
    if elapsed > 0 and 'process_cpu_ns' in result:
        result['cpu_cores'] = result['process_cpu_ns'] / 1e9 / elapsed
    return result


INSTALL_JS = r"""
(function(){
 var p=this._mcpSnapshotPolicy;
 if(!p)throw new Error('Snapshot policy is not installed');
 // ScriptAgent hides some package aliases, and JDK 21 does not export the
 // concrete sun.management implementations. Invoke cached public-interface
 // Methods instead of reflecting on the concrete bean class through Rhino.
 var factory=java.lang.Class.forName('java.lang.management.ManagementFactory');
 function obtain(name){return factory.getMethod(name).invoke(null);}
 function exposed(bean,name,names){
  var type=java.lang.Class.forName(name),result={};
  for(var i=0;i<names.length;i++)(function(key,method){
   result[key]=function(){return method.invoke(bean);};
  })(names[i],type.getMethod(names[i]));
  return result;
 }
 var threadBean=obtain('getThreadMXBean');
 var thread=exposed(threadBean,'java.lang.management.ThreadMXBean',
  ['isCurrentThreadCpuTimeSupported','isThreadCpuTimeEnabled','getCurrentThreadCpuTime']);
 var setCpu=java.lang.Class.forName('java.lang.management.ThreadMXBean').getMethod('setThreadCpuTimeEnabled',java.lang.Boolean.TYPE);
 thread.setThreadCpuTimeEnabled=function(enabled){setCpu.invoke(threadBean,java.lang.Boolean.valueOf(enabled));};
 var gc=[],gcList=obtain('getGarbageCollectorMXBeans'),list=java.lang.Class.forName('java.util.List');
 var gcArray=list.getMethod('toArray').invoke(gcList);
 for(var i=0;i<gcArray.length;i++)gc.push(exposed(gcArray[i],
  'java.lang.management.GarbageCollectorMXBean',['getCollectionCount','getCollectionTime']));
 var classes=exposed(obtain('getClassLoadingMXBean'),'java.lang.management.ClassLoadingMXBean',['getTotalLoadedClassCount']);
 var compilerBean=obtain('getCompilationMXBean');
 var compiler=compilerBean?exposed(compilerBean,'java.lang.management.CompilationMXBean',
  ['isCompilationTimeMonitoringSupported','getTotalCompilationTime']):null;
 var runtime=exposed(obtain('getRuntimeMXBean'),'java.lang.management.RuntimeMXBean',['getName']);
 var cpuSupported=thread.isCurrentThreadCpuTimeSupported(),enabledCpuHere=false;
 if(cpuSupported&&!thread.isThreadCpuTimeEnabled()){thread.setThreadCpuTimeEnabled(true);enabledCpuHere=true;}
 p.interestDiagnosticPid=parseInt(String(runtime.getName()).split('@')[0],10);
 p.interestDiagnosticTid=null;
 try{var reader=new java.io.BufferedReader(new java.io.FileReader('/proc/thread-self/stat'));
  try{var tid=parseInt(String(reader.readLine()),10);if(isFinite(tid)&&tid>0)p.interestDiagnosticTid=tid;}
  finally{reader.close();}}catch(e){}
 p.interestDiagnostics={enabled:true,warmupTraces:10,sequence:0,limit:64,records:[],error:null};
 p.interestDiagnosticActive=null;
 function cpu(){var v=cpuSupported?Number(thread.getCurrentThreadCpuTime()):-1;return v>=0?v:null;}
 function beans(){
  var count=0,ms=0,countValid=false,timeValid=false;
  for(var i=0;i<gc.length;i++){var b=gc[i],c=Number(b.getCollectionCount()),t=Number(b.getCollectionTime());
   if(c>=0){count+=c;countValid=true;}if(t>=0){ms+=t;timeValid=true;}}
  return {gcCount:countValid?count:null,gcMs:timeValid?ms:null,classes:Number(classes.getTotalLoadedClassCount()),
   compileMs:compiler&&compiler.isCompilationTimeMonitoringSupported()?Number(compiler.getTotalCompilationTime()):null};
 }
 p.interestDiagnosticBegin=function(now,force){
  var d=p.interestDiagnostics;if(!d||!d.enabled)return;
  try{
   // Observe due snapshot rounds only, rather than polling management beans at 60 Hz.
   if(!force&&now-p.interestLastBase<Packages.mindustry.net.Administration.Config.snapshotInterval.num())return;
   var setup=Number(java.lang.System.nanoTime()),metrics=beans(),c=cpu(),t=Number(java.lang.System.nanoTime());
   p.interestDiagnosticActive={started:t,last:t,cpuStarted:c,cpuLast:c,before:metrics,
    stage:force?'snapshot-control':'memory-guard',scope:force?'send-only':'update',stages:{},observerNs:0,observerCpuNs:0,setupNs:t-setup,sequence:++d.sequence,
    phase:d.sequence<=d.warmupTraces?'warmup':'measured'};
  }catch(e){d.error=String(e);d.enabled=false;p.interestDiagnosticsEnabled=false;}
 };
 p.interestDiagnosticMark=function(stage){
  var a=p.interestDiagnosticActive;if(!a)return;
  try{
   var start=Number(java.lang.System.nanoTime()),c=cpu(),key=a.stage;
   var s=a.stages[key]||(a.stages[key]={wallMs:0,cpuMs:c===null?null:0});
   s.wallMs+=(start-a.last)/1000000;
   if(c!==null&&a.cpuLast!==null)s.cpuMs+=(c-a.cpuLast)/1000000;
   a.stage=stage;a.cpuLast=cpu();a.last=Number(java.lang.System.nanoTime());
   if(c!==null&&a.cpuLast!==null)a.observerCpuNs+=Math.max(0,a.cpuLast-c);
   var overhead=a.last-start;a.observerNs+=overhead;
   // Do not charge optional observer bookkeeping against the AOI work budget.
   if(p.interestDeadlineNs)p.interestDeadlineNs+=overhead;
  }catch(e){p.interestDiagnostics.error=String(e);p.interestDiagnostics.enabled=false;p.interestDiagnosticsEnabled=false;p.interestDiagnosticActive=null;}
 };
 p.interestDiagnosticEnd=function(error){
  var a=p.interestDiagnosticActive;if(!a)return;
  try{
   p.interestDiagnosticMark('end');if(!p.interestDiagnosticActive)return;
   var end=a.last,c=a.cpuLast,after=beans(),nativePart=a.stages['native-update'],guard=a.stages['memory-guard'];
   var finishObserver=Number(java.lang.System.nanoTime())-end;
   var wall=(end-a.started-a.observerNs)/1000000;
   var cpuMs=c!==null&&a.cpuStarted!==null?Math.max(0,(c-a.cpuStarted-a.observerCpuNs)/1000000):null;
   var record={sequence:a.sequence,phase:a.phase,scope:a.scope,wallMs:wall,threadCpuMs:cpuMs,
    nonCpuWallMs:cpuMs===null?null:Math.max(0,wall-cpuMs),
    cpuMeasurementOverhangMs:cpuMs===null?null:Math.max(0,cpuMs-wall),
    nativeWallMs:nativePart?nativePart.wallMs:0,guardWallMs:guard?guard.wallMs:0,
    gcCountDelta:after.gcCount!==null&&a.before.gcCount!==null?after.gcCount-a.before.gcCount:null,
    gcTimeMsDelta:after.gcMs!==null&&a.before.gcMs!==null?after.gcMs-a.before.gcMs:null,
    classesLoadedDelta:after.classes-a.before.classes,
    compileTimeMsDelta:after.compileMs!==null&&a.before.compileMs!==null?after.compileMs-a.before.compileMs:null,
    observerWallMs:(a.observerNs+a.setupNs+finishObserver)/1000000,
    memorySample:p.interestMemorySample||null,error:error||null,errorStage:p.interestStage,stages:a.stages};
   record.addedWallMs=Math.max(0,wall-record.nativeWallMs-record.guardWallMs);
   record.addedCpuMs=cpuMs===null?null:Math.max(0,cpuMs-(nativePart&&nativePart.cpuMs!==null?nativePart.cpuMs:0)-(guard&&guard.cpuMs!==null?guard.cpuMs:0));
   var records=p.interestDiagnostics.records;records.push(record);
   if(records.length>p.interestDiagnostics.limit)records.shift();
  }catch(e){p.interestDiagnostics.error=String(e);p.interestDiagnostics.enabled=false;p.interestDiagnosticsEnabled=false;}
  finally{p.interestDiagnosticActive=null;}
 };
 p.disableInterestDiagnostics=function(){
  p.interestDiagnosticsEnabled=false;p.interestDiagnostics.enabled=false;p.interestDiagnosticActive=null;
  if(enabledCpuHere){try{thread.setThreadCpuTimeEnabled(false);}catch(e){p.interestDiagnostics.error=String(e);}}
 };
 p.interestDiagnosticsEnabled=true;
 sb.append('diagnostics installed');
})();
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--tid', type=int, help='Native game-thread ID reported by the opt-in JVM hooks')
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.pid <= 0 or args.seconds <= 0 or args.interval < .1:
        parser.error('Positive PID/duration and interval >=0.1 are required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.seconds
    previous = None
    with args.output.open('a', encoding='utf-8') as output:
        while time.monotonic() < deadline:
            sample = pressure_snapshot(args.pid, tid=args.tid)
            if previous:
                sample['delta'] = pressure_delta(previous, sample)
            output.write(json.dumps(sample) + '\n')
            output.flush()
            previous = sample
            time.sleep(min(args.interval, max(0, deadline - time.monotonic())))


if __name__ == '__main__':
    main()
