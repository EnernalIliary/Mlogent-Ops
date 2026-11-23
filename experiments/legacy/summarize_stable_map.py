import datetime as dt
import json
from pathlib import Path

folder=Path('/var/log/mlogent-world-traffic')
summary=json.loads((folder/'latest-stable-map-trial.json').read_text())
if summary['failure'] or len(summary['phases'])!=4:
    raise RuntimeError('No complete valid four-phase attempt: '+str(summary.get('failure')))
raw=[json.loads(line) for line in Path(summary['raw']).read_text().splitlines()]
traffic=[json.loads(line) for line in (folder/'samples.jsonl').read_text().splitlines()]
epoch=lambda value:dt.datetime.fromisoformat(value).timestamp()
out=[]
for phase in summary['phases']:
    begin,end=phase['begin'],phase['end'];b,e=epoch(begin['time_utc']),epoch(end['time_utc'])
    rs=[r for r in raw if r['event']=='sample' and r['attempt']==phase['attempt'] and r['phase']==phase['phase'] and b<=epoch(r['time_utc'])<=e]
    windows=[r for r in traffic if epoch(r['time_utc'])<=e and epoch(r['time_utc'])-r['seconds']>=b]
    seconds=sum(r['seconds'] for r in windows)
    if seconds<20:raise RuntimeError('Insufficient full traffic windows')
    pressures=[r['pressure'] for r in rs];first,last=pressures[0],pressures[-1]
    if first['start_ticks']!=last['start_ticks']:raise RuntimeError('JVM changed')
    result=dict(phase=phase['phase'],units=sorted({r['snapshot']['units'] for r in rs}),
        synced_buildings=sorted({r['snapshot']['syncedBuildings'] for r in rs}),
        total_buildings_min=min(r['snapshot']['buildings'] for r in rs),
        total_buildings_max=max(r['snapshot']['buildings'] for r in rs),
        traffic_seconds=seconds,udp_bytes=sum(r['bytes']['udp_out'] for r in windows),
        peak_100ms_udp_kbps=max(r['peak_100ms_bps']['udp_out'] for r in windows)/1000,
        peak_1s_udp_kbps=max(r['peak_1s_bps']['udp_out'] for r in windows)/1000,
        view_widths=sorted({r['snapshot']['view']['w'] for r in rs}),
        view_x_range=[min(r['snapshot']['view']['x'] for r in rs),max(r['snapshot']['view']['x'] for r in rs)],
        modes=sorted({r['snapshot']['unitMode'] for r in rs}),
        spawner_always_disabled=all(r['snapshot']['spawnerEnabled'] is False for r in rs),
        cpu_cores=(last['process_cpu_ns']-first['process_cpu_ns'])/1e9/(last['monotonic']-first['monotonic']),
        host_min_available_mib=min(p['host_available_bytes'] for p in pressures)/1024**2,
        max_selection=end['snapshot']['maxSelection'],bucket_rounds=end['snapshot']['bucketRounds'])
    result['udp_out_kbps']=result['udp_bytes']*8/seconds/1000
    out.append(result)
native=[r for r in out if r['phase'].startswith('native-')]
baseline=sum(r['udp_bytes'] for r in native)*8/sum(r['traffic_seconds'] for r in native)/1000
for result in out:
    result['udp_reduction_vs_bracketed_native_pct']=(1-result['udp_out_kbps']/baseline)*100
result=dict(phases=out,native_weighted_udp_kbps=baseline,
    native_before_after_drift_pct=(native[-1]['udp_out_kbps']/native[0]['udp_out_kbps']-1)*100,
    attempts=summary['attempts'],restored=summary['restored'],raw=summary['raw'])
(folder/'latest-stable-map-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
