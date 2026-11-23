"""One bounded, player-guided C + stagger run; not a startup setting."""
import argparse
import datetime as dt
import json
from pathlib import Path
import time

import stagger_trial as trial
from stagger_trial import js, encoded, SNAPSHOT, LOG
from world_interest_diagnostics import INSTALL_JS as DIAGNOSTICS, pressure_snapshot

TOKEN = 'C-stagger-interactive-20261123-1950'
CLEANUP = """
var p=this._mcpSnapshotPolicy;
if(p&&p.interactiveStaggerToken==='TOKEN'&&p.interactiveStaggerCleanup)p.interactiveStaggerCleanup();
sb.append(JSON.stringify({enabled:p.interestEnabled,stagger:p.interestStaggerEnabled,
budget:p.interestBudgetMs,diagnostics:p.interestDiagnosticsEnabled,
nativeListener:Core.app.getListeners().indexOf(p.interestOriginal,true)>=0,error:p.interestError}));
""".replace('TOKEN', TOKEN)


def main(cleanup=False):
    state = trial.sleeper.request({'op': 'supervisor_status'}, timeout=10)
    if state.get('sleepState') != 'running':
        print(json.dumps({'skipped': 'world not running'}), flush=True)
        return
    if cleanup:
        print(json.dumps(js(CLEANUP)), flush=True)
        return
    first = js(SNAPSHOT)
    if first['players'] != 1 or first['pvp']:
        raise RuntimeError('Requires one player in non-PvP world')
    if first['enabled']:
        raise RuntimeError('Another interest experiment is already active')
    raw = LOG / ('C-stagger-interactive-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')+'.jsonl')
    results = []

    def log(event, **fields):
        record = dict(time_utc=dt.datetime.now(dt.timezone.utc).isoformat(), event=event, **fields)
        with raw.open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False)+'\n')
        if event != 'sample':
            with (LOG/'experiments.jsonl').open('a') as stream:
                stream.write(json.dumps(record, ensure_ascii=False)+'\n')
            print(json.dumps({k:v for k,v in record.items() if k != 'snapshot'},ensure_ascii=False),flush=True)
        return record

    try:
        js(DIAGNOSTICS+"\nsb.append(JSON.stringify({diagnostics:true}));")
        code = """
var p=this._mcpSnapshotPolicy;
var savedCheck=p.checkBudget,savedUpdate=p.interestUpdate,savedRestore=p.restoreOriginal,
 savedBudget=p.interestBudgetMs,savedGroup=p.experimentGroup;
p.interactiveStaggerToken='TOKEN';p.interactiveStaggerPlayer=PLAYER;
p.interactiveStaggerExpires=java.lang.System.currentTimeMillis()+170000;
p.interactiveStaggerLast=0;p.staggerTrialMaxGap=0;
p.interactiveNotice=function(b64){for(var i=0;i<Groups.player.size();i++){
 var player=Groups.player.index(i);if(player.id===p.interactiveStaggerPlayer)
 player.sendMessage(new java.lang.String(java.util.Base64.getDecoder().decode(b64),'UTF-8'));}};
p.interactiveStaggerCleanup=function(){
 p.interactiveNotice('FINISH');p.interactiveStaggerArmed=false;
 p.checkBudget=savedCheck;p.interestUpdate=savedUpdate;p.restoreOriginal=savedRestore;
 p.interestBudgetMs=savedBudget;p.interestStaggerEnabled=false;p.experimentGroup=savedGroup;
 if(p.disableInterestDiagnostics)p.disableInterestDiagnostics();savedRestore.call(p);
 p.interactiveStaggerCleanup=null;
};
p.restoreOriginal=function(){savedRestore.call(p);if(p.interactiveStaggerArmed){
 p.interactiveStaggerArmed=false;p.interactiveNotice('FALLBACK');}};
p.checkBudget=function(){};p.interestBudgetMs=20;
p.interestUpdate=function(){
 var t=java.lang.System.currentTimeMillis();
 if(t>p.interactiveStaggerExpires){p.interactiveStaggerCleanup();return;}
 if(p.interactiveStaggerLast)p.staggerTrialMaxGap=Math.max(p.staggerTrialMaxGap,t-p.interactiveStaggerLast);
 p.interactiveStaggerLast=t;p.interestLastUpdate=0;savedUpdate.call(p);
};
for(var n=0;n<12;n++){p.interestDiagnosticBegin(java.lang.System.currentTimeMillis(),true);p.interestDiagnosticEnd(null);}
p.interestStates={};p.interestLastBase=0;p.interestPhaseOrigin=null;p.interestPhaseNext=null;
p.interestPhaseTicks={state:0,entities:0,buildings:0};p.interestTicks=0;p.interestDispatchTicks=0;
p.interestTotalMs=0;p.interestMaxMs=0;p.interestDispatchMaxMs=0;p.interestCycleIndex=-1;p.interestCycleWorkMs=0;
p.interestBuildingRecords=0;p.interestEntityRecords=0;p.interestError=null;p.interestMemoryCheckAt=0;
p.interestStaggerEnabled=true;p.interestEnabled=true;p.interestInstalled=true;
p.interactiveStaggerArmed=true;p.experimentGroup='C-stagger-interactive';
var listeners=Core.app.getListeners(),slot=listeners.indexOf(p.interestOriginal,true);
if(slot>=0)listeners.set(slot,p.interestWrapper);else throw new Error('Native listener missing');
sb.append(JSON.stringify({started:true,pid:p.interestDiagnosticPid,tid:p.interestDiagnosticTid}));
""".replace('TOKEN', TOKEN).replace('PLAYER', str(first['playerId']))
        code=code.replace('FINISH',encoded('C组+错峰联动测试结束，已恢复原版同步，可正常操作。'))
        code=code.replace('FALLBACK',encoded('C组+错峰触发保护，已回退原版同步；正在记录原因。'))
        info=js(code)
        log('interactive_C_stagger_started', observer=info)
        stages=[('camera','C组+错峰已开启。第一段40秒：请保持小视野，连续切换镜头，留意建筑和单位是否延迟。'),
                ('full-view','第二段40秒：请缩放到全图并观察。超过60%全图阈值时，单位/状态按设计交还原版，建筑仍分频。'),
                ('controlled-unit','第三段40秒：请恢复小视野并控制单位，移动和转向，留意修正或卡顿；控制单位仍150毫秒补发。')]
        for phase,message in stages:
            js("var p=this._mcpSnapshotPolicy;p.interactiveNotice('"+encoded(message)+"');sb.append(JSON.stringify({sent:true}));")
            log('in_game_test_prompt_sent',phase=phase,message=message)
            started=time.monotonic()
            samples=[]
            while time.monotonic()-started<40:
                snapshot=js(SNAPSHOT)
                pressure=pressure_snapshot(info['pid'],tid=info['tid'])
                record=log('sample',phase=phase,elapsed=time.monotonic()-started,snapshot=snapshot,pressure=pressure)
                samples.append(record)
                if not snapshot['enabled']:
                    raise RuntimeError('Protection fallback: '+str(snapshot['error']))
                if (snapshot['players']!=1 or snapshot['playerId']!=first['playerId'] or
                    snapshot['map']!=first['map'] or snapshot['pvp']):
                    raise RuntimeError('Participant or world changed')
                time.sleep(1)
            log('interactive_phase_end',phase=phase,snapshot=samples[-1]['snapshot'])
            results.append(dict(phase=phase,begin=samples[0],end=samples[-1]))
    finally:
        restored=js(CLEANUP)
        log('interactive_C_stagger_restored',restored=restored)
        (LOG/'latest-C-stagger-interactive.json').write_text(json.dumps(dict(raw=str(raw),phases=results,restored=restored),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cleanup',action='store_true')
    main(parser.parse_args().cleanup)
