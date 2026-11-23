"""Bounded A/B/C/A comparison; discard attempts crossing a unit-count change."""
import argparse
import datetime as dt
import json
import time

import far_bucket_trial as base
from far_bucket_trial import js, encoded, LOG
from world_interest_diagnostics import pressure_snapshot

TOKEN='stable-map-native-C-buckets-20261123'
SNAPSHOT="""
var p=this._mcpSnapshotPolicy,q=Groups.player.size()?Groups.player.index(0):null;
var synced=0,teams=Vars.state.teams.present;
for(var ti=0;ti<teams.size;ti++)synced+=Vars.indexer.getFlagged(teams.get(ti).team,Packages.mindustry.world.meta.BlockFlag.synced).size;
sb.append(JSON.stringify({players:Groups.player.size(),playerId:q?q.id:null,
map:String(Vars.state.map.name()),units:Groups.unit.size(),buildings:Groups.build.size(),syncedBuildings:synced,pvp:Vars.state.rules.pvp,
spawnerEnabled:Vars.world.build(376,363)?Vars.world.build(376,363).enabled:null,
nativeListener:Core.app.getListeners().indexOf(p.interestOriginal,true)>=0,
enabled:p.interestEnabled,stagger:p.interestStaggerEnabled,farBuckets:p.interestFarBucketsEnabled,
unitMode:p.interestUnitMode,fullView:q?p.fullView(q):null,
interval:Packages.mindustry.net.Administration.Config.snapshotInterval.num(),controlledInterval:p.controlledInterval,
view:q?{x:q.con.viewX,y:q.con.viewY,w:q.con.viewWidth,h:q.con.viewHeight}:null,
entityRecords:p.interestEntityRecords,buildingRecords:p.interestBuildingRecords,
maxSelection:p.interestEntityMaxSelection,bucketRounds:p.interestFarBucketRounds,
phaseTicks:p.interestPhaseTicks,error:p.interestError,pid:p.interestDiagnosticPid,tid:p.interestDiagnosticTid}));
"""
CLEANUP="""
var p=this._mcpSnapshotPolicy;
if(p.stableMapToken==='TOKEN'&&p.stableMapCleanup)p.stableMapCleanup();
sb.append(JSON.stringify({nativeListener:Core.app.getListeners().indexOf(p.interestOriginal,true)>=0,
enabled:p.interestEnabled,stagger:p.interestStaggerEnabled,farBuckets:p.interestFarBucketsEnabled,
budget:p.interestBudgetMs,diagnostics:p.interestDiagnosticsEnabled,error:p.interestError}));
""".replace('TOKEN',TOKEN)


class LoadChanged(Exception):
    pass


def main(cleanup=False):
    supervisor=base.sleeper.request({'op':'supervisor_status'},timeout=10)
    if supervisor.get('sleepState')!='running':
        print(json.dumps({'skipped':'world not running'}),flush=True);return
    if cleanup:
        print(json.dumps(js(CLEANUP)),flush=True);return
    initial=js(SNAPSHOT)
    if initial['players']!=1 or initial['pvp'] or initial['enabled'] or initial['fullView']:
        raise RuntimeError('Requires one idle player, native mode and small viewport')
    path=LOG/('stable-map-trial-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')+'.jsonl')
    results=[];attempts=[];failure=None

    def log(event,**fields):
        item=dict(time_utc=dt.datetime.now(dt.timezone.utc).isoformat(),event=event,**fields)
        with path.open('a') as stream:stream.write(json.dumps(item,ensure_ascii=False)+'\n')
        if event!='sample':
            with (LOG/'experiments.jsonl').open('a') as stream:stream.write(json.dumps(item,ensure_ascii=False)+'\n')
            print(json.dumps({k:v for k,v in item.items() if k not in ('snapshot','pressure')},ensure_ascii=False),flush=True)
        return item

    def notice(message):
        js("var p=this._mcpSnapshotPolicy;p.stableMapNotice('"+encoded(message)+"');sb.append(JSON.stringify({sent:true}));")

    def validate(snapshot,reference):
        if (snapshot['players']!=1 or snapshot['playerId']!=reference['playerId'] or
            snapshot['map']!=reference['map'] or snapshot['pvp']):
            raise RuntimeError('Player or world changed')
        if snapshot['spawnerEnabled'] is not False:
            raise RuntimeError('Spawn processor is no longer disabled')
        if snapshot['units']!=reference['units'] or snapshot['syncedBuildings']!=reference['syncedBuildings']:
            raise LoadChanged('Unit/synced-building count changed: '+json.dumps(snapshot))
        a,b=snapshot['view'],reference['view']
        if (abs(a['w']-b['w'])>b['w']*.05 or abs(a['h']-b['h'])>b['h']*.05 or
            abs(a['x']-b['x'])>b['w']*.1 or abs(a['y']-b['y'])>b['h']*.1):
            raise RuntimeError('Viewport changed beyond idle tolerance')

    try:
        setup="""
var p=this._mcpSnapshotPolicy;
var savedCheck=p.checkBudget,savedUpdate=p.interestUpdate,savedRestore=p.restoreOriginal,
savedBudget=p.interestBudgetMs;
if(p.disableInterestDiagnostics)p.disableInterestDiagnostics();
p.stableMapToken='TOKEN';p.stableMapPlayer=PLAYER;
p.stableMapExpires=java.lang.System.currentTimeMillis()+465000;
p.stableMapNotice=function(b64){for(var i=0;i<Groups.player.size();i++){
var q=Groups.player.index(i);if(q.id===p.stableMapPlayer)
q.sendMessage(new java.lang.String(java.util.Base64.getDecoder().decode(b64),'UTF-8'));}};
p.stableMapCleanup=function(){
p.stableMapNotice('FINISH');p.stableMapArmed=false;
p.checkBudget=savedCheck;p.interestUpdate=savedUpdate;p.restoreOriginal=savedRestore;
p.interestBudgetMs=savedBudget;p.interestStaggerEnabled=false;p.interestFarBucketsEnabled=false;
savedRestore.call(p);p.stableMapCleanup=null;
};
p.restoreOriginal=function(){savedRestore.call(p);if(p.stableMapArmed){
p.stableMapArmed=false;p.stableMapNotice('FALLBACK');}};
p.checkBudget=function(){};p.interestBudgetMs=20;
p.interestUpdate=function(){
if(java.lang.System.currentTimeMillis()>p.stableMapExpires){p.stableMapCleanup();return;}
p.interestLastUpdate=0;savedUpdate.call(p);
};
sb.append(JSON.stringify({prepared:true}));
""".replace('TOKEN',TOKEN).replace('PLAYER',str(initial['playerId']))
        setup=setup.replace('FINISH',encoded('静置对照已结束，当前恢复原版300毫秒同步，可正常操作。'))
        setup=setup.replace('FALLBACK',encoded('静置对照触发保护，已恢复原版同步，本轮停止。'))
        js(setup)
        notice('刷兵世处已停用。10秒后开始四段静置对照，总计约三分半；请保持小视野，不移动镜头或操作单位。结束会另行通知。')
        time.sleep(10)
        for attempt in range(1,3):
            reference=js(SNAPSHOT)
            log('stable_map_attempt_start',attempt=attempt,units=reference['units'],buildings=reference['buildings'])
            results=[]
            try:
                for phase,enabled,buckets,label in [
                    ('native-before',False,False,'原版同步300毫秒（前对照）'),
                    ('C-stagger',True,False,'C组+错峰'),
                    ('C-stagger-buckets',True,True,'C组+错峰+远处单位四批轮转'),
                    ('native-after',False,False,'原版同步300毫秒（后对照）')]:
                    js("""
var p=this._mcpSnapshotPolicy;p.stableMapArmed=false;p.restoreOriginal();
p.interestStaggerEnabled=ENABLED;p.interestFarBucketsEnabled=BUCKETS;
p.interestStates={};p.interestLastBase=0;p.interestPhaseOrigin=null;p.interestPhaseNext=null;
p.interestPhaseTicks={state:0,entities:0,buildings:0};p.interestFarBucketRounds=[0,0,0,0];
p.interestEntityMaxSelection=0;p.interestEntityRecords=0;p.interestBuildingRecords=0;
p.interestError=null;p.interestMemoryCheckAt=0;p.interestHostLowSince=null;
if(ENABLED){var listeners=Core.app.getListeners(),slot=listeners.indexOf(p.interestOriginal,true);
if(slot<0)throw new Error('Native listener missing');listeners.set(slot,p.interestWrapper);
p.interestEnabled=true;p.interestInstalled=true;p.stableMapArmed=true;}
sb.append(JSON.stringify({switched:true}));
""".replace('ENABLED',str(enabled).lower()).replace('BUCKETS',str(buckets).lower()))
                    notice('静置对照：'+label+'，本段50秒。请保持镜头和操作不变；刷兵会自动使本轮作废。')
                    log('in_game_test_prompt_sent',attempt=attempt,phase=phase,label=label)
                    start=time.monotonic();begin=None;last=None
                    while time.monotonic()-start<50:
                        snap=js(SNAPSHOT);validate(snap,reference)
                        if enabled and not snap['enabled']:raise RuntimeError('AOI protection fallback: '+str(snap['error']))
                        if not enabled and not snap['nativeListener']:raise RuntimeError('Native listener changed')
                        if snap['interval']!=300:raise RuntimeError('Base interval changed')
                        last=log('sample',attempt=attempt,phase=phase,snapshot=snap,
                                 pressure=pressure_snapshot(initial['pid'],tid=initial['tid']))
                        if begin is None and time.monotonic()-start>=10:
                            begin=log('measurement_begin',attempt=attempt,phase=phase,snapshot=snap)
                        time.sleep(2)
                    end=log('measurement_end',attempt=attempt,phase=phase,snapshot=last['snapshot'])
                    results.append(dict(phase=phase,attempt=attempt,begin=begin,end=end))
                attempts.append(dict(attempt=attempt,valid=True,units=reference['units']))
                log('stable_map_attempt_complete',attempt=attempt,units=reference['units'])
                break
            except LoadChanged as exc:
                attempts.append(dict(attempt=attempt,valid=False,reason=str(exc)))
                log('stable_map_attempt_discarded',attempt=attempt,reason=str(exc))
                results=[]
                js("var p=this._mcpSnapshotPolicy;p.stableMapArmed=false;p.restoreOriginal();sb.append(JSON.stringify({native:true}));")
                if attempt==2:raise
                notice('检测到刷兵或建筑数量变化，本轮数据作废。恢复原版，等数量稳定10秒后重新开始一次。')
                stable=js(SNAPSHOT);since=time.monotonic();deadline=since+35
                while time.monotonic()-since<10:
                    time.sleep(2);snap=js(SNAPSHOT)
                    if (snap['units'],snap['syncedBuildings'])!=(stable['units'],stable['syncedBuildings']):stable=snap;since=time.monotonic()
                    if time.monotonic()>deadline:raise RuntimeError('Load did not stabilize')
    except Exception as exc:
        failure=str(exc);log('stable_map_trial_failed',reason=failure)
        raise
    finally:
        restored=js(CLEANUP)
        log('stable_map_restored',restored=restored)
        (LOG/'latest-stable-map-trial.json').write_text(json.dumps(dict(raw=str(path),phases=results,attempts=attempts,failure=failure,restored=restored),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cleanup',action='store_true')
    main(parser.parse_args().cleanup)
