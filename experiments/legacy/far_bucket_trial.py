"""Bounded live comparison; invoked manually, never a production startup hook."""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/opt/mlogent-releases/v1.10.0-worldsleep-20261122/tools')
import world_client as w
import world_sleep_client as sleeper
from world_interest_policy import INSTALL_JS
from world_interest_diagnostics import INSTALL_JS as DIAGNOSTICS, pressure_snapshot

LOG = Path('/var/log/mlogent-world-traffic')
TOKEN = 'far-bucket-20261123-test1'


def js(code):
    result = w.call({'op': 'js', 'code': code}, hs=w.handshake(), timeout=15)
    if not result.get('ok'):
        raise RuntimeError(str(result))
    lines = result.get('lines', [])
    return json.loads(lines[-1][lines[-1].index('{'):]) if lines else None


def encoded(text):
    return base64.b64encode(text.encode()).decode()


def notice(text):
    return "p.testNotice('%s');" % encoded(text)


CLEANUP = """
var p=this._mcpSnapshotPolicy;
if(p&&p.staggerTrialToken==='TOKEN'&&p.staggerTrialCleanup)p.staggerTrialCleanup('试验结束，已恢复原版同步，可正常操作。');
sb.append(JSON.stringify({cleaned:true,enabled:p.interestEnabled,stagger:p.interestStaggerEnabled,budget:p.interestBudgetMs,farBuckets:p.interestFarBucketsEnabled}));
""".replace('TOKEN', TOKEN)

SNAPSHOT = """
var p=this._mcpSnapshotPolicy,who=Groups.player.size()?Groups.player.index(0):null;
sb.append(JSON.stringify({players:Groups.player.size(),playerId:who?who.id:null,map:String(Vars.state.map.name()),pvp:Vars.state.rules.pvp,
units:Groups.unit.size(),enabled:p.interestEnabled,installed:p.interestInstalled,stagger:p.interestStaggerEnabled,
unitMode:p.interestUnitMode,buildingMode:p.interestBuildingMode,buildingCount:p.interestBuildingCount,
farBuckets:p.interestFarBucketsEnabled,bucketRounds:p.interestFarBucketRounds,maxSelection:p.interestEntityMaxSelection,phaseTicks:p.interestPhaseTicks,ticks:p.interestTicks,dispatches:p.interestDispatchTicks,
totalMs:p.interestTotalMs,maxCycleMs:p.interestMaxMs,maxDispatchMs:p.interestDispatchMaxMs,
buildingRecords:p.interestBuildingRecords,entityRecords:p.interestEntityRecords,
memory:p.interestMemorySample,error:p.interestError,maxGapMs:p.staggerTrialMaxGap,
view:who?{x:who.con.viewX,y:who.con.viewY,w:who.con.viewWidth,h:who.con.viewHeight}:null,
pid:p.interestDiagnosticPid,tid:p.interestDiagnosticTid,
diagnostics:p.interestDiagnostics?p.interestDiagnostics.records:[]}));
"""


def main(cleanup=False):
    state = sleeper.request({'op': 'supervisor_status'}, timeout=10)
    if state.get('sleepState') != 'running':
        print(json.dumps({'skipped': 'world not running'}), flush=True)
        return
    if cleanup:
        print(json.dumps(js(CLEANUP), ensure_ascii=False), flush=True)
        return
    initial = js(SNAPSHOT)
    if initial['players'] != 1 or initial['pvp']:
        raise RuntimeError('Trial requires one player and non-PvP world')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')
    raw = LOG / ('far-bucket-trial-' + stamp + '.jsonl')
    results = []

    def log(event, **values):
        item = dict(time_utc=dt.datetime.now(dt.timezone.utc).isoformat(), event=event, **values)
        with raw.open('a') as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
        if event != 'sample':
            with (LOG / 'experiments.jsonl').open('a') as stream:
                stream.write(json.dumps(item, ensure_ascii=False) + '\n')
            print(json.dumps({k:v for k,v in item.items() if k not in ('snapshot','initial')}, ensure_ascii=False), flush=True)
        return item

    try:
        install = INSTALL_JS.replace('policy.interestEnabled=true;', 'policy.interestEnabled=false;', 1)
        js(install + "\nthis._mcpSnapshotPolicy.restoreOriginal();sb.append(JSON.stringify({installed:true}));")
        js(DIAGNOSTICS + "\nsb.append(JSON.stringify({observer:true}));")
        setup = """
var p=this._mcpSnapshotPolicy;
p.staggerTrialToken='TOKEN';p.staggerTrialExpires=java.lang.System.currentTimeMillis()+210000;
p.staggerTrialPlayer=PLAYER;p.staggerTrialMaxGap=0;p.staggerTrialLast=0;
p.testNotice=function(b64){for(var i=0;i<Groups.player.size();i++){var player=Groups.player.index(i);
if(player.id===p.staggerTrialPlayer)player.sendMessage(new java.lang.String(java.util.Base64.getDecoder().decode(b64),'UTF-8'));}};
var savedCheck=p.checkBudget,savedUpdate=p.interestUpdate,savedRestore=p.restoreOriginal,savedBudget=p.interestBudgetMs;
p.staggerTrialCleanup=function(message){
 p.testNotice('FINISH');
 p.testNoticeArmed=false;p.checkBudget=savedCheck;p.interestUpdate=savedUpdate;p.restoreOriginal=savedRestore;
 p.interestBudgetMs=savedBudget;p.interestStaggerEnabled=false;p.interestFarBucketsEnabled=false;
 if(p.disableInterestDiagnostics)p.disableInterestDiagnostics();savedRestore.call(p);
 p.staggerTrialCleanup=null;
};
p.restoreOriginal=function(){savedRestore.call(p);if(p.testNoticeArmed){p.testNoticeArmed=false;p.testNotice('FALLBACK');}};
p.checkBudget=function(){};p.interestBudgetMs=20;
p.interestUpdate=function(){
 var t=java.lang.System.currentTimeMillis();
 if(t>p.staggerTrialExpires){p.staggerTrialCleanup('expired');return;}
 if(p.staggerTrialLast)p.staggerTrialMaxGap=Math.max(p.staggerTrialMaxGap,t-p.staggerTrialLast);
 p.staggerTrialLast=t;p.interestLastUpdate=0;savedUpdate.call(p);
};
// Warm management/reflection helpers while AOI is disabled.
for(var n=0;n<12;n++){p.interestDiagnosticBegin(java.lang.System.currentTimeMillis(),true);p.interestDiagnosticEnd(null);}
sb.append(JSON.stringify({ready:true,pid:p.interestDiagnosticPid,tid:p.interestDiagnosticTid}));
""".replace('TOKEN', TOKEN).replace('PLAYER', str(initial['playerId']))
        setup = setup.replace('FINISH', encoded('全部测试结束，已恢复原版同步，可正常操作。'))
        setup = setup.replace('FALLBACK', encoded('本段测试触发保护，已回退原版同步；请保持静置，正在记录原因。'))
        info = js(setup)
        log('far_bucket_trial_prepared', initial=initial, observer=info)
        for phase, stagger in [('C-stagger-concentrated-far', False), ('C-stagger-four-far-buckets', True)]:
            label = 'C组+错峰，远处单位四批轮转' if stagger else 'C组+错峰，远处单位集中补发（对照）'
            code = """
var p=this._mcpSnapshotPolicy;
p.interestStates={};p.interestLastBase=0;p.interestPhaseOrigin=null;p.interestPhaseNext=null;
p.interestPhaseTicks={state:0,entities:0,buildings:0};p.interestDispatchTicks=0;
p.interestFarBucketRounds=[0,0,0,0];p.interestEntityMaxSelection=0;
p.interestTicks=0;p.interestTotalMs=0;p.interestMaxMs=0;p.interestDispatchMaxMs=0;
p.interestCycleIndex=-1;p.interestCycleWorkMs=0;p.interestEntityRecords=0;p.interestBuildingRecords=0;
p.staggerTrialMaxGap=0;p.staggerTrialLast=0;p.interestError=null;
p.interestMemoryCheckAt=0;p.interestHostLowSince=null;
p.interestStaggerEnabled=true;p.interestFarBucketsEnabled=STAGGER;p.testNoticeArmed=true;
var listeners=Core.app.getListeners(),slot=listeners.indexOf(p.interestOriginal,true);
if(slot>=0)listeners.set(slot,p.interestWrapper);
p.interestEnabled=true;p.interestInstalled=true;
NOTICE
sb.append(JSON.stringify({started:true,stagger:p.interestStaggerEnabled}));
""".replace('STAGGER', str(stagger).lower()).replace('NOTICE', notice('开始测试：'+label+'。本段约70秒，请保持当前地图和视角静置。计时回退暂时关闭，内存保护保留。'))
            js(code)
            log('in_game_test_prompt_sent', phase=phase, label=label)
            started = time.monotonic()
            measured = None
            samples = []
            while time.monotonic()-started < 70:
                snap = js(SNAPSHOT)
                pressure = pressure_snapshot(info['pid'], tid=info['tid'])
                log('sample', phase=phase, elapsed=time.monotonic()-started, snapshot=snap, pressure=pressure)
                samples.append(snap)
                if not snap['enabled']:
                    raise RuntimeError('Guard fallback: '+str(snap['error']))
                if snap['players'] != 1 or snap['playerId'] != initial['playerId'] or snap['map'] != initial['map'] or snap['pvp']:
                    raise RuntimeError('Participant or world changed')
                if measured is None and time.monotonic()-started >= 20:
                    measured = log('measurement_begin', phase=phase, snapshot=snap)
                time.sleep(1)
            final = log('measurement_end', phase=phase, snapshot=samples[-1])
            results.append(dict(phase=phase, begin=measured, end=final))
            js("var p=this._mcpSnapshotPolicy;p.testNoticeArmed=false;p.restoreOriginal();"+
               notice('本段结束，已恢复原版同步；请继续静置，正在切换对照。')+"sb.append(JSON.stringify({phaseEnded:true}));")
    finally:
        restored = js(CLEANUP)
        log('far_bucket_trial_restored', restored=restored)
        summary = dict(raw=str(raw), phases=results, restored=restored)
        (LOG/'latest-far-bucket-trial.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cleanup', action='store_true')
    main(parser.parse_args().cleanup)
