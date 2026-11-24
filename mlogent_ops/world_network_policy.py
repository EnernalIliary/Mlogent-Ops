"""Map-aware snapshot cadence; keeps the stock client wire protocol."""

CORE_INSTALL_JS = r"""
(function(){
 var mcpSnapshotRoot=this;
 var policy=this._mcpSnapshotPolicy;
 var fresh=!policy;
 if(fresh){policy={lastCheck:0};this._mcpSnapshotPolicy=policy;}
 policy.apply=function(){
  if(!Vars.state.isGame())return;
  var target=Vars.state.rules.pvp?200:300;
  policy.controlledInterval=100;
  var config=Packages.mindustry.net.Administration.Config.snapshotInterval;
  if(config.num()!==target){
   config.set(new java.lang.Integer(String(target)));
   Packages.arc.util.Log.info('Snapshot policy: '+target+' ms (pvp='+Vars.state.rules.pvp+')');
  }
 };
 if(!policy.baseCallbacksInstalled){
  Events.on(Packages.mindustry.game.EventType.WorldLoadEvent,function(){
   var current=mcpSnapshotRoot._mcpSnapshotPolicy;
   if(current&&typeof current.apply==='function'){
    try{current.apply();}catch(error){Packages.arc.util.Log.err('Snapshot map policy failed: '+error);}
   }
  });
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var current=mcpSnapshotRoot._mcpSnapshotPolicy;
   if(!current||typeof current.apply!=='function')return;
   var now=java.lang.System.currentTimeMillis();
   if(now-current.lastCheck>=1000){
    current.lastCheck=now;
    try{current.apply();}catch(error){Packages.arc.util.Log.err('Snapshot cadence policy failed: '+error);}
   }
  });
  policy.baseCallbacksInstalled=true;
 }
 if(!policy.controlledInstalled){
  policy.controlledInstalled=true;
  policy.controlledEnabled=true;
  policy.controlledInterval=100;
  policy.lastControlled=0;
  policy.controlledBatches=0;
  policy.controlledEntities=0;
  policy.controlledError=null;
 }
 policy.controlledOutsideView=true;
 policy.visibleUnits=function(receiver,units){
   var visible=new Packages.arc.struct.Seq();
   for(var i=0;i<units.size;i++){
    var unit=units.get(i);
    // Player-controlled units keep the 100-ms supplement outside every camera.
    // Native fog visibility still takes priority over delivery cadence.
    if(!unit.isSyncHidden(receiver.team()))visible.add(unit);
   }
   return visible;
  };
 if(!policy.supplement||policy.controlledVersion!==4){
  policy.controlledVersion=4;
  policy.supplement=function(){
   if(!policy.controlledEnabled||!Vars.state.isGame()||Vars.state.isPaused())return;
   // Native fallback already sends these entities. Never add a second lane.
   if(Vars.state.rules.pvp||(policy.interestInstalled!==undefined&&!policy.interestEnabled)||policy.interestUnitMode==='native-full-view')return;
   var now=java.lang.System.currentTimeMillis();
   var effective=policy.controlledInterval;
   if(typeof policy.adaptiveControlledInterval==='function')effective=policy.adaptiveControlledInterval(now);
   policy.controlledEffectiveInterval=effective;
   if(!policy.controlledNext||policy.controlledScheduleInterval!==effective){
    policy.controlledNext=policy.lastControlled?policy.lastControlled+effective:now;
    policy.controlledScheduleInterval=effective;
   }
   if(now<policy.controlledNext)return;
   policy.controlledNext+=effective*(Math.floor(Math.max(0,now-policy.controlledNext)/effective)+1);
   policy.lastControlled=now;
   try{
    var units=new Packages.arc.struct.Seq();
    var ids=new Packages.arc.struct.IntSet();
    var players=Groups.player;
    for(var i=0;i<players.size();i++){
     var owner=players.index(i);
     if(!owner.con||!owner.con.hasConnected||!owner.con.isConnected()||owner.dead())continue;
     var unit=owner.unit();
     // BlockUnitc is an internal building-control proxy. Its transient tile is
     // not serialized; sending it as an entity creates a client-side proxy
     // with no tile, crashing MinimapRenderer when it calls icon().
     if(unit!=null&&!(unit instanceof Packages.mindustry.gen.BlockUnitc)&&unit.isAdded()&&!unit.dead&&ids.add(unit.id))units.add(unit);
    }
    if(units.isEmpty())return;
    for(var j=0;j<players.size();j++){
     var receiver=players.index(j);
     if(!receiver.con||!receiver.con.hasConnected||!receiver.con.isConnected())continue;
     if(typeof policy.afkSupplementDue==='function'&&!policy.afkSupplementDue(receiver,now))continue;
     var visible=policy.visibleUnits(receiver,units);
     if(visible.isEmpty())continue;
     Vars.netServer.writeCustomEntitySnapshot(receiver,visible);
     policy.controlledBatches++;
     policy.controlledEntities+=visible.size;
    }
   }catch(error){
    policy.controlledEnabled=false;
    policy.controlledError=String(error);
    Packages.arc.util.Log.err('Controlled snapshot supplement disabled: '+error);
   }
  };
 }
 if(!policy.controlledCallbackInstalled){
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var current=mcpSnapshotRoot._mcpSnapshotPolicy;
   if(!current||typeof current.supplement!=='function')return;
   try{current.supplement();}catch(error){
    current.controlledEnabled=false;current.controlledError=String(error);
    Packages.arc.util.Log.err('Controlled snapshot callback disabled: '+error);
   }
  });
  policy.controlledCallbackInstalled=true;
 }
 policy.apply();sb.append('installed');
})();
"""

from .world_interest_policy import INSTALL_JS as INTEREST_INSTALL_JS
from .world_preview_policy import INSTALL_JS as PREVIEW_INSTALL_JS
from .world_building_observer import INSTALL_JS as BUILDING_OBSERVER_JS
from .world_adaptive_policy import INSTALL_JS as ADAPTIVE_INSTALL_JS
from .world_afk_policy import INSTALL_JS as AFK_INSTALL_JS
from .world_poly_verification import INSTALL_JS as POLY_INSTALL_JS
from .world_notices import INSTALL_JS as NOTICES_INSTALL_JS
import os
import json
from pathlib import Path

def experimental_config(event_path=None):
    """Explicit opt-in profile; production/native and existing C tests stay unchanged."""
    return """
var p=this._mcpSnapshotPolicy;
p.interestStaggerEnabled=true;p.interestFarBucketsEnabled=true;
p.interestPerPlayerFullView=true;
p.interestEntityIntervalMs=200;p.interestFarBucketCount=6;p.interestFarBucketRounds=[0,0,0,0,0,0];
p.interestMaxPlayers=12;
p.interestReactorEnabled=true;p.interestReactorIntervalMs=500;p.interestReactorHeatThreshold=0.7;
p.interestRelaxedGuards=true;p.interestBudgetMs=20;
p.interestHardWorkMs=100;p.interestSlowLimit=3;p.interestSlowCount=0;
p.interestUpdateGapMs=5000;p.interestHeapMaxRatio=0.93;p.interestSwapMaxKB=131072;
p.interestHostSoftMinKB=98304;p.interestHostHardMinKB=65536;p.interestHostHoldMs=10000;
p.interestHostLowSince=null;
p.interestPid=p.readMetric('/proc/self/status','Pid');
p.interestTid=p.readMetric('/proc/thread-self/status','Pid');
p.interestEventPath=EVENT_PATH;
""".replace('EVENT_PATH', json.dumps(event_path))

# Opt-in only: large-map camera transitions still require performance validation.
DISABLE_INTEREST_JS = r"""
if(this._mcpSnapshotPolicy){
 this._mcpSnapshotPolicy.interestEnabled=false;
 if(typeof this._mcpSnapshotPolicy.restoreOriginal==='function')this._mcpSnapshotPolicy.restoreOriginal();
}
sb.append('viewport sync disabled');
"""
def install_script(mode, event_path=None):
    core = CORE_INSTALL_JS.replace("policy.apply();sb.append('installed');", "policy.apply();")
    if mode == 'wrapper':
        # B control: install the identical adapter, but never run AOI selection,
        # memory guards, camera-dependent cadence or custom snapshot scheduling.
        interest = INTEREST_INSTALL_JS.replace('policy.interestEnabled=true;',
                                               'policy.interestEnabled=false;', 1)
        group = 'B-wrapper-only'
    elif mode == 'experimental':
        path = event_path or os.environ.get('MLOG_WORLD_FALLBACK_EVENT')
        interest = INTEREST_INSTALL_JS + '\n' + experimental_config(path)
        group = 'C-stagger-buckets-experimental'
    elif mode == '1':
        interest, group = INTEREST_INSTALL_JS, 'C-interest-enabled'
    else:
        interest, group = DISABLE_INTEREST_JS, 'A-native'
    return core + PREVIEW_INSTALL_JS + BUILDING_OBSERVER_JS + ADAPTIVE_INSTALL_JS + AFK_INSTALL_JS + POLY_INSTALL_JS + NOTICES_INSTALL_JS + interest + "\nthis._mcpSnapshotPolicy.experimentGroup='" + group + "';"


def startup_script(profile_path=None):
    # A small owned profile permits a hot change now and the same policy on the
    # next wake without restarting an occupied supervisor/JVM just for its env.
    root = os.environ.get('MLOGENT_ROOT')
    path = Path(profile_path) if profile_path else (Path(root)/'out/_world/snapshot-profile.json' if root else None)
    try:
        if path is None:
            return install_script(os.environ.get('MLOG_WORLD_VIEWPORT_SYNC'))
        profile = json.loads(path.read_text(encoding='utf-8'))
        mode = profile.get('mode')
        if mode in ('native', 'wrapper', '1', 'experimental'):
            event = profile.get('eventPath')
            script = install_script(mode, event if isinstance(event, str) else None)
            if profile.get('buildingObservation') is True:
                script += '\nthis._mcpSnapshotPolicy.buildingObservationEnabled=true;'
            if profile.get('buildingDedup') is True and mode == 'experimental':
                script += ('\nthis._mcpSnapshotPolicy.buildingObservationEnabled=true;'
                           'this._mcpSnapshotPolicy.buildingDedupEnabled=true;'
                           'this._mcpSnapshotPolicy.buildingObservation.mode="dedup";')
            if profile.get('enemyBuildingsInViewOnly') is True and mode == 'experimental':
                script += '\nthis._mcpSnapshotPolicy.interestEnemyBuildingsInViewOnly=true;'
            if profile.get('adaptiveBandwidth') is True and mode == 'experimental':
                script += '\nthis._mcpSnapshotPolicy.adaptiveEnabled=true;'
            if profile.get('afkVerification') is True and mode == 'experimental':
                script += '\nthis._mcpSnapshotPolicy.afkEnabled=true;'
            if profile.get('polyVerification') is True:
                script += '\nthis._mcpSnapshotPolicy.polyEnabled=true;'
            if profile.get('rotatingNotices') is True:
                script += '\nthis._mlogentNotices.enabled=true;'
            return script
    except (OSError, ValueError, AttributeError):
        pass
    return install_script(os.environ.get('MLOG_WORLD_VIEWPORT_SYNC'))


INSTALL_JS = startup_script()
