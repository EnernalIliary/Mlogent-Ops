import datetime as dt
import json
from pathlib import Path
import statistics

folder=Path('/var/log/mlogent-world-traffic')
summary=json.loads((folder/'latest-stagger-trial.json').read_text())
raw=[json.loads(s) for s in Path(summary['raw']).read_text().splitlines()]
traffic=[json.loads(s) for s in (folder/'samples.jsonl').read_text().splitlines()]
epoch=lambda s: dt.datetime.fromisoformat(s).timestamp()
out=[]
for phase in summary['phases']:
    begin,end=phase['begin'],phase['end']
    b,e=epoch(begin['time_utc']),epoch(end['time_utc'])
    bs,es=begin['snapshot'],end['snapshot']
    samples=[r for r in raw if r.get('phase')==phase['phase'] and r['event']=='sample' and b<=epoch(r['time_utc'])<=e]
    windows=[r for r in traffic if epoch(r['time_utc'])<=e and epoch(r['time_utc'])-r['seconds']>=b]
    traces={t['sequence']:t for r in samples for t in r['snapshot'].get('diagnostics',[])
            if t['sequence']>max((v['sequence'] for v in bs['diagnostics']),default=0)}
    records=list(traces.values())
    elapsed=e-b
    cycles=es['ticks']-bs['ticks']
    def percentile(values,frac):
        ordered=sorted(values)
        return ordered[min(len(ordered)-1,int((len(ordered)-1)*frac))] if ordered else None
    duration=sum(r['seconds'] for r in windows)
    udp=sum(r['bytes']['udp_out'] for r in windows)*8/duration if duration else None
    total=sum(r['bytes']['udp_out']+r['bytes']['tcp_out'] for r in windows)*8/duration if duration else None
    pressures=[r['pressure'] for r in samples]
    cpu=None
    if len(pressures)>1:
        a,z=pressures[0],pressures[-1]
        cpu=(z['process_cpu_ns']-a['process_cpu_ns'])/1e9/(z['monotonic']-a['monotonic'])
    result=dict(phase=phase['phase'],seconds=elapsed,units=sorted({r['snapshot']['units'] for r in samples}),
        traffic_windows=len(windows),traffic_seconds=duration,udp_out_kbps=udp/1000 if udp is not None else None,
        total_out_kbps=total/1000 if total is not None else None,
        max_100ms_udp_kbps=max((r['peak_100ms_bps']['udp_out']/1000 for r in windows),default=None),
        max_1s_udp_kbps=max((r['peak_1s_bps']['udp_out']/1000 for r in windows),default=None),
        phase_rates={k:(es['phaseTicks'][k]-bs['phaseTicks'][k])/elapsed for k in bs['phaseTicks']},
        avg_work_ms_per_cycle=(es['totalMs']-bs['totalMs'])/cycles if cycles else None,
        max_cycle_including_warmup_ms=es['maxCycleMs'],max_dispatch_including_warmup_ms=es['maxDispatchMs'],
        trace_max_added_ms=max((r['addedWallMs'] for r in records),default=None),
        trace_p95_added_ms=percentile([r['addedWallMs'] for r in records],.95),
        trace_count=len(records),trace_gc_count=sum(r['gcCountDelta'] or 0 for r in records),
        cpu_cores=cpu,max_callback_gap_ms=es['maxGapMs'],
        min_host_available_mib=min((r['snapshot']['memory']['hostAvailableKB']/1024 for r in samples),default=None),
        max_jvm_swap_mib=max((r['snapshot']['memory']['jvmSwapKB']/1024 for r in samples),default=None),
        views=len({json.dumps(r['snapshot']['view'],sort_keys=True) for r in samples}),
        error=es['error'])
    out.append(result)
result={'phases':out,'restored':summary['restored'],'raw':summary['raw']}
(folder/'latest-stagger-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
