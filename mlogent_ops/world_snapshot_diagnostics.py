#!/usr/bin/env python3
"""Local, unhosted v160 JVM A/B probes; never controls the live world.

Uses a fresh process/workdir for each phase. No game ports or player messages.
The unhosted probe isolates adapter/bridge overhead; it does not model map load.
Optional psutil adds process RSS/CPU metrics. JVM heap options match the VPS.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import time
import sys

from .world_network_policy import install_script

ROOT = Path(__file__).resolve().parents[1]

METRICS_JS = r"""
var probeMemoryPools=[],probePoolIterator=java.lang.management.ManagementFactory.getMemoryPoolMXBeans().iterator();
while(probePoolIterator.hasNext()){
 var probePool=probePoolIterator.next(),probeUsage=probePool.getUsage();
 probeMemoryPools.push({name:String(probePool.getName()),used:probeUsage.getUsed(),committed:probeUsage.getCommitted()});
}
var probeRuntime=java.lang.Runtime.getRuntime();
sb.append(JSON.stringify({heapUsed:probeRuntime.totalMemory()-probeRuntime.freeMemory(),
 heapCommitted:probeRuntime.totalMemory(),heapMax:probeRuntime.maxMemory(),pools:probeMemoryPools,
 classes:java.lang.management.ManagementFactory.getClassLoadingMXBean().getLoadedClassCount()}));
"""

MINIMAL_WRAPPER_JS = r"""
(function(){
 var probeOriginalServer=Vars.netServer,probeListeners=Core.app.getListeners();
 var probeListenerSlot=probeListeners.indexOf(probeOriginalServer,true);
 if(probeListenerSlot<0)throw new Error('Native listener not found');
 var probeAdapter=new JavaAdapter(Packages.arc.ApplicationListener,{
  update:function(){probeOriginalServer.update();}
 });
 probeListeners.set(probeListenerSlot,probeAdapter);sb.append('minimal wrapper installed');
})();
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mlogent-root', default=os.environ.get('MLOGENT_ROOT'),
                        help='Mlogent checkout supplying the isolated JVM process/channel utilities')
    parser.add_argument('--java', default=str(ROOT / 'out/jre21/jdk-21.0.5+11-jre/bin/java.exe'))
    parser.add_argument('--jar', default=str(ROOT / 'out/_server160.jar'))
    parser.add_argument('--seconds', type=float, default=20)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--phase', choices=['all', 'A', 'B-minimal', 'B-full', 'long-noop'], default='all')
    parser.add_argument('--jvm-options', default='-Xms128m -Xmx384m -XX:+UseSerialGC -XX:ActiveProcessorCount=2 -XX:NativeMemoryTracking=summary')
    parser.add_argument('--scenario', choices=['unhosted-idle', 'simulated-hosted-idle'], default='unhosted-idle')
    parser.add_argument('--runtime', type=Path, help='Sanitized plugin/libs/script fixture directory; no account data')
    parser.add_argument('--inline-limit', type=int, default=2048, help='Max inline UTF-8 source bytes; use a large value to reproduce old transport')
    args = parser.parse_args()
    if args.seconds <= 0 or args.interval <= 0:
        parser.error('Positive seconds and interval required')
    if not args.mlogent_root:
        parser.error('Set MLOGENT_ROOT or --mlogent-root for isolated JVM probes')
    sys.path.insert(0, str(Path(args.mlogent_root).resolve() / 'tools'))
    from world_process import WorldProcess
    from world_channel import WorldChannel
    try:
        import psutil
    except ImportError:
        psutil = None
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    output = ROOT / 'out/diagnostics' / ('snapshot-' + stamp)
    output.mkdir(parents=True, exist_ok=False)
    phases = ['A', 'B-minimal', 'B-full'] if args.phase == 'all' else [args.phase]
    with (output / 'samples.jsonl').open('w', encoding='utf-8') as record:
        for phase in phases:
            work = output / phase
            if args.runtime:
                for relative in ('libs', 'config/mods', 'config/scripts'):
                    source = args.runtime / relative
                    if source.exists():
                        shutil.copytree(source, work / relative)
            previous = os.environ.get('JAVA_TOOL_OPTIONS')
            os.environ['JAVA_TOOL_OPTIONS'] = args.jvm_options
            try:
                process = WorldProcess(args.java, args.jar, data_dir=str(work), log_path=str(work / 'server.log'))
            finally:
                if previous is None:
                    os.environ.pop('JAVA_TOOL_OPTIONS', None)
                else:
                    os.environ['JAVA_TOOL_OPTIONS'] = previous
            try:
                channel = WorldChannel(process, inline_limit=args.inline_limit)
                channel.wait_for('Server loaded.', 60)
                if args.scenario == 'simulated-hosted-idle':
                    from mlogent.simulation.scripts import load_js
                    channel.js(load_js(64) + r"""
var probeServerFlag=Vars.net.getClass().getDeclaredField('server');
probeServerFlag.setAccessible(true);probeServerFlag.setBoolean(Vars.net,true);
Vars.state.rules.canGameOver=false;
Vars.state.set(Packages.mindustry.core.GameState.State.paused);
sb.append('simulated server flag, no bound sockets');
""", 15)
                before_policy = json.loads(channel.js(METRICS_JS, 15)[0])
                record.write(json.dumps({'phase': phase, 'stage': 'before-policy', 'jvm': before_policy}) + '\n')
                print(json.dumps({'phase': phase, 'stage': 'before-policy',
                                  'heapUsed': before_policy['heapUsed'],
                                  'heapCommitted': before_policy['heapCommitted']}), flush=True)
                install_started = time.monotonic()
                channel.js(install_script('wrapper' if phase == 'B-full' else None), 15)
                if phase == 'B-minimal':
                    channel.js(MINIMAL_WRAPPER_JS, 15)
                elif phase == 'long-noop':
                    # Same console transport size as B, with no adapter or work.
                    padding = 'x' * len(install_script('wrapper'))
                    channel.js('/*' + padding + "*/sb.append('long noop');", 15)
                print(json.dumps({'phase': phase, 'installSeconds': round(time.monotonic() - install_started, 3)}), flush=True)
                native = psutil.Process(process.proc.pid) if psutil else None
                started = time.monotonic()
                while True:
                    before = time.monotonic()
                    row = {'phase': phase, 'scenario': args.scenario, 'jvmOptions': args.jvm_options, 'inlineLimit': args.inline_limit,
                           'seconds': round(before - started, 3),
                           'jvm': json.loads(channel.js(METRICS_JS, 15)[0])}
                    row['querySeconds'] = round(time.monotonic() - before, 3)
                    if native:
                        row['process'] = {'rss': native.memory_info().rss,
                                          'threads': native.num_threads(),
                                          'cpuSeconds': sum(native.cpu_times()[:2])}
                    record.write(json.dumps(row) + '\n')
                    record.flush()
                    print(json.dumps({'phase': phase, 'seconds': row['seconds'],
                                      'heapUsed': row['jvm']['heapUsed'],
                                      'heapCommitted': row['jvm']['heapCommitted'],
                                      'metaspace': next(p['used'] for p in row['jvm']['pools'] if p['name'] == 'Metaspace'),
                                      'process': row.get('process'), 'querySeconds': row['querySeconds']}), flush=True)
                    if time.monotonic() - started >= args.seconds:
                        break
                    time.sleep(min(args.interval, max(0, args.seconds - (time.monotonic() - started))))
            finally:
                process.close(force=True)
    print('OUTPUT ' + str(output), flush=True)


if __name__ == '__main__':
    main()
