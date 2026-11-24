"""Execute AOI scheduling, geometry and fail-open behavior without a JVM."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_interest_policy import INSTALL_JS
from mlogent_ops.world_network_policy import install_script
from mlogent_ops.world_network_policy import experimental_config

HARNESS = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let now=20000,states=0,updates=0,resets=0,sent=[],packets=[],fail=false;
let swapKB=0,availableKB=400000,usedHeap=100;
let nativeBuildingBatches=0,nativeBuildingClock=now;
let nanosOffset=0,nextBuildingId=10000,streamInitNs=0,buffersCreated=0;const liveBuildings=new Map();
class Seq{
 constructor(a=[]){this.a=a;} get size(){return this.a.length;}
 get(i){return this.a[i];}add(v){this.a.push(v);}addAll(v){this.a.push(...v.a);}
 isEmpty(){return this.size===0;}
}
class IntSeq extends Seq{}
class Unit{
 constructor(id,x,y,hidden=false){Object.assign(this,{id,x,y,hidden,hitSize:10});}
 isSyncHidden(){return this.hidden;}
}
class Stream{constructor(){buffersCreated++;nanosOffset+=streamInitNs;this.n=0;this.positions=[];}size(){return this.n;}reset(){this.n=0;this.positions=[];}toByteArray(){return {bytes:this.n,positions:this.positions.slice()};}}
class Output{constructor(s){this.s=s;}writeInt(v){this.s.n+=4;this.s.positions.push(v);}writeShort(){this.s.n+=2;}}
const build=(pos,x)=>{const b={id:nextBuildingId++,x,y:0,team:1,hidden:false,block:{id:5,size:1},pos:()=>pos,inFogTo(viewer){return this.team!==viewer&&this.hidden;},writeSync:w=>w.s.n+=10};liveBuildings.set(pos,b);return b;};
let buildings=[build(1,0),build(2,1000)];
const mine=new Unit(1,1000,1000),near=new Unit(2,10,0),far=new Unit(3,1000,0),hidden=new Unit(4,0,0,true);
const entities=[mine,near,far,hidden,{id:5,x:9999,y:9999,isSyncHidden:()=>false}];
const receiver={con:{viewX:0,viewY:0,viewWidth:100,viewHeight:100,
 hashCode:()=>7,hasConnected:true,isConnected:()=>true,localEntities:new Seq()},dead:()=>false,unit:()=>mine,team:()=>1};
const original={snapshotSyncTime:0,writeStateSnapshot:()=>states++,
 writeCustomEntitySnapshot:(p,s)=>{if(fail)throw Error('serialization');sent.push(s.a.map(x=>x.id));},
 update:()=>{updates++;if(now-nativeBuildingClock>=6000){nativeBuildingBatches++;nativeBuildingClock=now;}},
 getClass:()=>({getDeclaredField:()=>({setAccessible(){},get:()=>({reset:()=>{resets++;nativeBuildingClock=now;}})})})};
const listeners={a:[original],indexOf(x){return this.a.indexOf(x);},set(i,x){this.a[i]=x;}};
const policy={},events=[];
const ctx={_mcpSnapshotPolicy:policy,sb:{append(){}},isFinite,
 JavaAdapter:function(t,o){return o;},
 java:{lang:{System:{currentTimeMillis:()=>now,nanoTime:()=>now*1000000+nanosOffset},Byte:{TYPE:0},reflect:{Array:{newInstance:()=>[]}},
 Runtime:{getRuntime:()=>({totalMemory:()=>usedHeap,freeMemory:()=>0,maxMemory:()=>1000})}},
 io:{ByteArrayOutputStream:Stream,DataOutputStream:Output,
 FileReader:class {constructor(p){this.p=p;}},
 BufferedReader:class {constructor(f){this.lines=[f.p.includes('status')?`VmSwap: ${swapKB} kB`:`MemAvailable: ${availableKB} kB`];}readLine(){return this.lines.shift()??null;}close(){}}}},
 Packages:{arc:{ApplicationListener:class{},struct:{Seq,IntSeq},util:{Time:{millis:()=>now},Log:{err(){}},io:{Writes:{get:o=>o}}}},
 mindustry:{core:{Version:{build:160}},net:{Administration:{Config:{snapshotInterval:{num:()=>250}}}},gen:{Unit,Call:{blockSnapshot:(...a)=>packets.push(a),entitySnapshot:(...a)=>packets.push(a),hiddenSnapshot:(...a)=>packets.push(a)}},
 world:{meta:{BlockFlag:{synced:1}}},game:{EventType:{WorldLoadEvent:'load'}}}},
 Core:{app:{getListeners:()=>listeners},settings:{getBool:()=>true}},Events:{on:(t,f)=>events.push(f)},
 Vars:{content:{block:()=>null},netServer:original,net:{server:()=>true},world:{width:()=>100,height:()=>100,build:pos=>liveBuildings.get(pos)||null},tilesize:8,
 state:{rules:{pvp:false,fog:true},isGame:()=>true,teams:{present:new Seq([{team:1}])}},indexer:{getFlagged:()=>new Seq(buildings)}},
 Groups:{player:{size:()=>1,index:()=>receiver},sync:{size:()=>entities.length,index:i=>entities[i]}}
};
vm.createContext(ctx);vm.runInContext(source,ctx);
const view=policy.view(receiver);assert.equal(view.w,150);
assert.equal(policy.inView(view,{x:80,y:0,hitSize:20}),true);
assert.equal(policy.inView(view,{x:86,y:0,hitSize:20}),false);
receiver.con.viewWidth=NaN;assert.equal(policy.view(receiver),null);receiver.con.viewWidth=100;
const selected=()=>{const hiddenIds=new IntSeq();return policy.selectEntities(receiver,view,false,ctx.Groups.sync,hiddenIds).a.map(x=>x.id);};
assert.deepEqual(Array.from(selected()),[1,2,5]);
ctx.Vars.state.rules.fog=false;
assert.deepEqual(Array.from(selected()),[1,2,4,5]);
ctx.Vars.state.rules.fog=true;
policy.interestUpdate();assert.equal(updates,1);assert.equal(resets,1);assert.equal(states,1);
assert.deepEqual(sent[0],[1,2,3,5]);assert.equal(policy.interestBuildingRecords,2);
now+=250;policy.interestUpdate();assert.deepEqual(sent[1],[1,2,5]);
now+=750;policy.interestUpdate();assert.deepEqual(sent[2],[1,2,3,5]);
const st=policy.interestStates.c7;
assert.equal(policy.buildingDue(st,'b1',5,true,now),false);
assert.equal(policy.buildingDue(st,'b1',5,true,26000),true);
assert.equal(policy.buildingDue(st,'b2',5,false,26000),false);
assert.equal(policy.buildingDue(st,'b2',5,false,32000),true);
assert.equal(policy.buildingDue(st,'b2',5,true,now),true); // enters viewport
assert.equal(policy.buildingDue(st,'b2',6,false,now),true); // replaced building
policy.interestBuildingLimit=1;policy.resetBuildingState(st);
const before=policy.interestBuildingRecords;
policy.writeBuildings(receiver,view,st,new Seq(buildings),now);
assert.equal(policy.interestBuildingRecords-before,1);
ctx.Vars.state.rules.pvp=true;const ticks=policy.interestTicks;policy.interestUpdate();assert.equal(policy.interestTicks,ticks);
ctx.Vars.state.rules.pvp=false;policy.interestEnabled=false;policy.interestUpdate();assert.equal(policy.interestTicks,ticks);
policy.interestEnabled=true;fail=true;now+=250;policy.interestUpdate();
assert.equal(policy.interestEnabled,false);assert.match(policy.interestError,/serialization/);assert.equal(original.snapshotSyncTime,0);
assert.equal(listeners.a[0],original); // fallback removes the JS update wrapper, not just its flag
// Empty selected lists still produce an entity heartbeat.
fail=false;ctx.Groups.sync={size:()=>0,index:()=>null};policy.interestEnabled=true;now+=250;
policy.interestUpdate();assert.ok(packets.some(a=>a[1]===0));
events[0]();assert.equal(Object.keys(policy.interestStates).length,0);
assert.equal(policy.interestBuildingMode,'pending');assert.equal(policy.interestBuildings,null);
const eventCount=events.length;vm.runInContext(source,ctx);assert.equal(events.length,eventCount);assert.equal(listeners.a.length,1);
// Large synced-building sets delegate ONLY buildings to native, without copying
// or scanning their records and without resetting the native building timer.
const smallBuildings=buildings;
let forbiddenBuildingScans=0;
ctx.Vars.indexer.getFlagged=()=>({size:4040,get(){forbiddenBuildingScans++;throw Error('must not scan');}});
now+=250;const largeResets=resets,largeTicks=policy.interestTicks,largePackets=packets.length;
policy.interestUpdate();
assert.equal(policy.interestEnabled,true);assert.equal(policy.interestInstalled,true);
assert.equal(policy.interestUnitMode,'aoi');assert.equal(policy.interestBuildingMode,'native');
assert.equal(policy.interestBuildingCount,4040);assert.match(policy.interestBuildingReason,/4040.*3072/);
assert.equal(policy.interestBuildings.size,0);assert.equal(forbiddenBuildingScans,0);
assert.equal(resets,largeResets);assert.equal(policy.interestTicks,largeTicks+1);
assert.equal(packets.length,largePackets+1); // empty entity heartbeat, no custom building packets
assert.equal(Object.keys(policy.interestStates.c7.buildings).length,0);
const nativeBefore=nativeBuildingBatches;
for(let i=0;i<26;i++){now+=250;policy.interestUpdate();}
assert.equal(policy.interestEnabled,true);assert.equal(resets,largeResets);
assert.ok(nativeBuildingBatches>nativeBefore); // native six-second delivery remains live
// A later capacity reduction re-enables bounded building AOI without a reload.
ctx.Vars.indexer.getFlagged=()=>new Seq(smallBuildings);
now+=250;policy.interestUpdate();
assert.equal(policy.interestBuildingMode,'aoi');assert.equal(policy.interestBuildingReason,null);
assert.equal(resets,largeResets+1);assert.equal(policy.interestBuildingCount,2);
assert.equal(Object.keys(policy.interestStates.c7.buildings).length,2);
ctx.Core.settings.getBool=()=>false;now+=250;const disabledResets=resets;
policy.interestUpdate();assert.equal(policy.interestBuildingMode,'disabled');assert.equal(resets,disabledResets);
assert.equal(Object.keys(policy.interestStates.c7.buildings).length,0);
ctx.Core.settings.getBool=()=>true;
// Ordinary attack-map capacity fits, while per-turn records and bytes stay bounded.
const attackBuildings=Array.from({length:2038},(_,i)=>build(i,0));
ctx.Vars.indexer.getFlagged=()=>new Seq(attackBuildings);
policy.interestBuildingLimit=64;
now+=250;const attackRecords=policy.interestBuildingRecords;
policy.interestUpdate();
assert.equal(policy.interestEnabled,true);assert.equal(policy.interestBuildingMode,'aoi');
assert.equal(policy.interestBuildingCount,2038);assert.equal(policy.interestBuildingReason,null);
assert.equal(policy.interestBuildingRecords-attackRecords,64);
assert.equal(Object.keys(policy.interestStates.c7.buildings).length,64);
assert.equal(policy.interestBuildingByteLimit,16384);assert.equal(policy.interestMaxClientBuildingRecords,3072);
// Capacity is inclusive, and total sizes are summed across teams before copying.
ctx.Vars.state.teams.present=new Seq([{team:1},{team:2}]);
ctx.Vars.indexer.getFlagged=t=>new Seq(Array.from({length:t===1?1536:1536},(_,i)=>build(i+t*2000,0)));
now+=250;policy.prepareBuildings(now);assert.equal(policy.interestBuildingMode,'aoi');assert.equal(policy.interestBuildingCount,3072);
ctx.Vars.indexer.getFlagged=t=>({size:t===1?1536:1537});
now+=250;policy.prepareBuildings(now);assert.equal(policy.interestBuildingMode,'native');assert.equal(policy.interestBuildingCount,3073);
assert.equal(policy.interestBuildings.size,0);assert.equal(Object.keys(policy.interestStates.c7.buildings).length,0);
ctx.Vars.state.teams.present=new Seq([{team:1}]);ctx.Vars.indexer.getFlagged=()=>new Seq(smallBuildings);
// Hot upgrades add the new cache-reset hook even if an old world hook exists.
delete policy.interestIncrementalWorldCallbackInstalled;
const oldHooks=events.length;vm.runInContext(source,ctx);
assert.equal(events.length,oldHooks+1);
policy.interestBuildingMode='native';policy.interestBuildings=new Seq();
events[events.length-1]();assert.equal(policy.interestBuildingMode,'pending');assert.equal(policy.interestBuildings,null);
// Preflight refuses oversized groups without entering the entity scan.
ctx.Groups.sync={size:()=>1025,index:()=>{throw Error('must not scan');}};
now+=250;policy.interestUpdate();assert.equal(policy.interestEnabled,false);assert.match(policy.interestError,/entity bound/);
ctx.Groups.sync={size:()=>0,index:()=>null};
policy.interestEnabled=true;policy.interestLastUpdate=now;
receiver.con.viewWidth=700;receiver.con.viewHeight=700;
now+=250;const beforeFull=policy.interestTicks;policy.interestUpdate();
assert.equal(policy.interestTicks,beforeFull+1);assert.equal(policy.interestEnabled,true);assert.equal(policy.interestFullViewFallbacks,1);
original.snapshotSyncTime=1234;now+=250;policy.interestUpdate();
assert.equal(original.snapshotSyncTime,1234); // never force native full snapshots every frame
receiver.con.viewWidth=100;receiver.con.viewHeight=100;
policy.interestDeadlineNs=now*1000000-1;assert.throws(()=>policy.checkBudget(),/budget/);policy.interestDeadlineNs=0;
policy.interestMemoryCheckAt=0;swapKB=65537;assert.throws(()=>policy.runtimeGuard(now),/swap/);swapKB=0;
policy.interestMemoryCheckAt=0;availableKB=90000;assert.throws(()=>policy.runtimeGuard(now),/available host memory/);availableKB=400000;
policy.interestMemoryCheckAt=0;usedHeap=900;assert.throws(()=>policy.runtimeGuard(now),/heap pressure/);usedHeap=100;
policy.interestLastUpdate=now-751;policy.interestUpdate();assert.equal(policy.interestEnabled,false);assert.match(policy.interestError,/gap/);
const many=new Seq(Array.from({length:3073},(_,i)=>build(i,0)));
assert.throws(()=>policy.writeBuildings(receiver,view,{buildings:{},cursor:0},many,now),/building bound/);
// One slow native batch trips the next cooperative check; later batches are skipped.
const hundred=Array.from({length:100},(_,i)=>new Unit(i+10,0,0));
ctx.Groups.sync={size:()=>hundred.length,index:i=>hundred[i]};
let slowBatches=0;original.writeCustomEntitySnapshot=()=>{slowBatches++;now+=10;};
policy.interestEnabled=true;policy.interestLastUpdate=now;policy.interestLastBase=0;policy.interestMemoryCheckAt=0;
now+=250;policy.interestUpdate();assert.equal(slowBatches,1);
assert.equal(policy.interestEnabled,false);assert.match(policy.interestError,/budget/);
// OS probes are accounted separately from added AOI work.
original.writeCustomEntitySnapshot=()=>{};
policy.runtimeGuard=()=>{now+=10;};
policy.interestEnabled=true;policy.interestLastUpdate=now;policy.interestLastBase=0;
now+=250;policy.interestUpdate();
assert.equal(policy.interestEnabled,true);assert.equal(policy.interestGuardLastMs,10);
ctx._mcpSnapshotPolicy={};assert.doesNotThrow(()=>listeners.a[0].update());ctx._mcpSnapshotPolicy=policy;
console.log('geometry, visibility, cadence, building budgets, PvP, fail-open, group bounds, full-view bypass, time and memory guards passed');
"""


class InterestPolicyTests(unittest.TestCase):
    def test_afk_receiver_one_second_overrides_adaptive_without_affecting_other(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
const second={...receiver,con:{...receiver.con,hashCode:()=>8}};
ctx.Groups.player={size:()=>2,index:i=>[receiver,second][i]};
const deliveries=[];original.writeCustomEntitySnapshot=(r,s)=>deliveries.push({key:r.con.hashCode(),at:now});
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.interestStaggerEnabled=true;policy.interestEntityIntervalMs=200;
policy.interestPerPlayerFullView=true;
const idle={nextEntity:now,interval:1000,lastEntity:0};
policy.afkCadence=r=>r===receiver?idle:null;
const start=now;
for(let t=0;t<3000;t+=50){now=start+t;policy.interestUpdate();}
assert.equal(deliveries.filter(x=>x.key===7).length,3);
assert.equal(deliveries.filter(x=>x.key===8).length,15);
policy.afkCadence=()=>null;
const count=deliveries.filter(x=>x.key===7).length;
for(let t=0;t<1000;t+=50){now=start+3000+t;policy.interestUpdate();}
assert.equal(deliveries.filter(x=>x.key===7).length-count,5);
"""
        result=subprocess.run(['node','-e',harness],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_resource_boost_has_real_100ms_dispatch_opportunities(self):
        from mlogent_ops.world_adaptive_policy import INSTALL_JS as ADAPTIVE_JS
        harness=HARNESS.split('vm.createContext(ctx);')[0]+r'''
receiver.con.address='a';let deliveries=[];
original.writeCustomEntitySnapshot=(r,s)=>deliveries.push(now);
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.interestStaggerEnabled=true;policy.interestEntityIntervalMs=200;
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
policy.adaptiveEnabled=true;policy.adaptiveFeedback({a:50000},now);
policy.adaptiveResource.tier=0;policy.adaptiveResource.at=now;
const start=now;for(let t=0;t<1000;t+=10){now=start+t;policy.interestUpdate();}
assert.equal(deliveries.length,10);
for(let i=1;i<deliveries.length;i++)assert.equal(deliveries[i]-deliveries[i-1],100);
assert.equal(policy.interestEnabled,true);
'''
        result=subprocess.run(['node','-e',harness],input=json.dumps(INSTALL_JS+ADAPTIVE_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_adaptive_receivers_dispatch_independently_and_stale_restores(self):
        from mlogent_ops.world_adaptive_policy import INSTALL_JS as ADAPTIVE_JS
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
const second={...receiver,con:{...receiver.con,address:'b',hashCode:()=>8}};
receiver.con.address='a';ctx.Groups.player={size:()=>2,index:i=>[receiver,second][i]};
let deliveries=[];original.writeCustomEntitySnapshot=(r,s)=>deliveries.push({key:r.con.hashCode(),at:now});
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.interestStaggerEnabled=true;policy.interestEntityIntervalMs=200;
policy.interestPerPlayerFullView=true;policy.adaptiveEnabled=true;
policy.adaptiveFeedback({a:200000,b:50000},now);
policy.adaptiveClients.c7.level=3;
const start=now;
for(let t=0;t<2000;t+=50){now=start+t;policy.interestUpdate();}
const busy=deliveries.filter(x=>x.key===7),light=deliveries.filter(x=>x.key===8);
assert.ok(busy.length>=4&&busy.length<=5);assert.ok(light.length>=9&&light.length<=10);
for(let i=1;i<busy.length;i++)assert.ok(busy[i].at-busy[i-1].at>=400);
assert.equal(policy.interestEnabled,true);
// Monitoring outage restores base cadence rather than extending indefinitely.
policy.adaptiveFeedbackAt=now-11000;assert.equal(policy.adaptiveCadence(receiver,now,false),null);
events[0]();assert.equal(Object.keys(policy.adaptiveClients).length,0);
assert.equal(policy.adaptiveResource.tier,1);assert.equal(policy.adaptiveResource.at,0);
"""
        result = subprocess.run(['node','-e',harness],input=json.dumps(INSTALL_JS+ADAPTIVE_JS),
                                capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_enemy_buildings_outside_interest_stop_and_reenter_refresh(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.interestEnemyBuildingsInViewOnly=true;
const ownFar=build(31,1000),enemyFar=build(32,1000),enemyNear=build(33,0);
enemyFar.team=2;enemyNear.team=2;buildings=[ownFar,enemyFar,enemyNear];
const state={},list=new Seq(buildings);let team=1;receiver.team=()=>team;
const send=()=>policy.writeBuildings(receiver,policy.view(receiver),state,list,now);
send();assert.deepEqual(packets.flatMap(p=>p[2].positions),[31,33]);
assert.equal(state.buildings.b32,undefined);assert.ok(policy.interestBuildingOutsideSkipped>0);
receiver.con.viewX=1000;now+=250;send();
assert.deepEqual(packets.at(-1)[2].positions,[31,32]);
assert.equal(state.buildings.b33.outsideInterest,true);
receiver.con.viewX=0;now+=250;send();assert.deepEqual(packets.at(-1)[2].positions,[33]);
// Different receiving team gets its own complete initial states.
team=2;now+=250;send();assert.deepEqual(packets.at(-1)[2].positions,[32,33]);
assert.equal(state.buildings.b31,undefined);
// Fog wins even inside the camera; reveal schedules immediate refresh.
team=1;enemyNear.hidden=true;now+=250;send();
assert.ok(!packets.at(-1)[2].positions.includes(33));
enemyNear.hidden=false;now+=250;send();assert.deepEqual(packets.at(-1)[2].positions,[33]);
// An invalid camera falls back to full delivery instead of dropping data.
receiver.con.viewWidth=NaN;now+=12500;send();
assert.ok(packets.at(-1)[2].positions.includes(32));receiver.con.viewWidth=100;
// Enemy priority reactors also obey the camera gate, own reactors retain it.
policy.isLowHeatReactor=()=>true;
const priority={reactorPriority:true};now+=1000;
policy.writeBuildings(receiver,policy.view(receiver),priority,list,now);
assert.deepEqual(packets.at(-1)[2].positions,[31,33]);
// No enemy offscreen serialization even when fog is disabled.
ctx.Vars.state.rules.fog=false;
enemyFar.writeSync=()=>{throw Error('offscreen enemy serialized');};now+=1000;
policy.writeBuildings(receiver,policy.view(receiver),priority,list,now);
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_dedup_packets_preserve_bytes_counts_reveal_priority_and_failure(self):
        from mlogent_ops.world_building_observer import INSTALL_JS as OBSERVER_JS
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
ctx.java.util={Arrays:{copyOfRange:(a,s,e)=>a.slice(s,e),
 equals:(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i])}};
Stream.prototype.reset=function(){this.n=0;this.bytes=[];};
Stream.prototype.write=function(a,s,n){this.bytes.push(...a.slice(s,s+n));this.n+=n;};
Stream.prototype.toByteArray=function(){return this.bytes.slice();};
Output.prototype.writeInt=function(v){this.s.write([0,0,0,v],0,4);};
Output.prototype.writeShort=function(v){this.s.write([0,v],0,2);};
buildings=[build(11,0),build(12,10)];
for(const b of buildings)b.writeSync=w=>w.s.write(new Array(10).fill(b.marker||0),0,10);
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.buildingObservationEnabled=true;policy.buildingDedupEnabled=true;
const state={},view=policy.view(receiver),list=new Seq(buildings);
const send=()=>policy.writeBuildings(receiver,view,state,list,now);
send();assert.equal(packets.length,1);assert.equal(packets[0][1],2);
const originalBytes=packets[0][2].slice();
now+=6000;send();assert.equal(packets.length,1);assert.equal(policy.buildingObservation.skippedRecords,2);
buildings[1].marker=9;now+=6000;send();
assert.equal(packets.length,2);assert.equal(packets[1][1],1);
assert.deepEqual(packets[1][2],originalBytes.slice(16,22).concat(new Array(10).fill(9)));
// Full refresh is measured from the last real send, not skipped checks.
now+=12000;send();assert.equal(packets.length,3);assert.equal(packets[2][1],1);
assert.deepEqual(packets[2][2],originalBytes.slice(0,16));
buildings[0].team=2;buildings[0].hidden=true;now+=6000;send();
buildings[0].hidden=false;now+=300;send();
assert.ok(packets.at(-1)[2].slice(0,16).every((v,i)=>v===originalBytes[i]));
// Priority reactor traffic never suppresses an identical record.
policy.isLowHeatReactor=()=>true;
const priority={reactorPriority:true};now+=1000;
policy.writeBuildings(receiver,view,priority,list,now);const before=packets.length;
now+=500;policy.writeBuildings(receiver,view,priority,list,now);
assert.equal(packets.length,before+1);assert.equal(packets.at(-1)[1],2);
// A failed send invalidates optimistic baselines; a retry sends everything.
ctx.Packages.mindustry.gen.Call.blockSnapshot=()=>{throw Error('network send');};
now+=500;assert.throws(()=>policy.writeBuildings(receiver,view,priority,list,now),/network send/);
assert.equal(policy.buildingObservation.cacheBytes,0);
ctx.Packages.mindustry.gen.Call.blockSnapshot=(...a)=>packets.push(a);
policy.resetBuildingState(priority);priority.reactorPriority=true;
now+=500;policy.writeBuildings(receiver,view,priority,list,now);
assert.equal(packets.at(-1)[1],2);
// If comparison fails after an earlier record was marked for omission, the
// complete original packet still goes out and only dedup is disabled.
policy.isLowHeatReactor=()=>false;const ordinary={};now+=1000;
policy.writeBuildings(receiver,view,ordinary,list,now);
let copies=0;ctx.java.util.Arrays.copyOfRange=(a,s,e)=>{
 if(++copies===2)throw Error('comparison failure');return a.slice(s,e);};
now+=6000;policy.writeBuildings(receiver,view,ordinary,list,now);
assert.equal(packets.at(-1)[1],2);assert.equal(packets.at(-1)[2].length,32);
assert.equal(policy.buildingDedupEnabled,false);assert.equal(policy.interestEnabled,true);
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS+OBSERVER_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_building_observer_uses_sent_records_without_changing_packets(self):
        from mlogent_ops.world_building_observer import INSTALL_JS as OBSERVER_JS
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
ctx.java.util={Arrays:{copyOfRange:(a,s,e)=>a.slice(s,e),
 equals:(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i])}};
Stream.prototype.toByteArray=function(){const a=new Array(this.n).fill(0);a[a.length-1]=this.marker||0;return a;};
buildings=[buildings[0]];let serializations=0;
buildings[0].writeSync=w=>{serializations++;w.s.n+=10;w.s.marker=buildings[0].marker||0;};
vm.createContext(ctx);vm.runInContext(source,ctx);
policy.buildingObservationEnabled=true;
const state={};const view=policy.view(receiver);
policy.writeBuildings(receiver,view,state,new Seq(buildings),now);
now+=6000;policy.writeBuildings(receiver,view,state,new Seq(buildings),now);
assert.equal(policy.buildingObservation.samples,2);assert.equal(policy.buildingObservation.repeated,1);
buildings[0].marker=1;now+=6000;
policy.writeBuildings(receiver,view,state,new Seq(buildings),now);
assert.equal(policy.buildingObservation.repeated,1);assert.equal(policy.buildingObservation.comparable,2);
assert.equal(packets.length,3);assert.equal(serializations,3);
assert.ok(packets.every(a=>a[1]===1&&a[2].length===16));
// Fog-hidden buildings are never serialized or observed.
buildings[0].team=2;buildings[0].hidden=true;now+=6000;
policy.writeBuildings(receiver,view,state,new Seq(buildings),now);
assert.equal(packets.length,3);assert.equal(policy.buildingObservation.samples,3);
// A sampling failure cannot prevent native send or disable synchronization.
buildings[0].hidden=false;ctx.java.util.Arrays.copyOfRange=()=>{throw Error('observer only');};
now+=6000;policy.writeBuildings(receiver,view,state,new Seq(buildings),now);
assert.equal(packets.length,4);assert.equal(policy.interestEnabled,true);
assert.equal(policy.buildingObservationEnabled,false);
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS+OBSERVER_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_mixed_players_keep_independent_cadence_visibility_and_transitions(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
policy.interestReactorEnabled=false;
const controlled=new Unit(101,1000,0);
const wide={con:{...receiver.con,viewWidth:700,viewHeight:700,hashCode:()=>8},
 dead:()=>false,unit:()=>controlled,team:()=>1};
let players=[receiver,wide];ctx.Groups.player={size:()=>players.length,index:i=>players[i]};
const distant=Array.from({length:12},(_,i)=>new Unit(i+20,1000,0));
const group=[mine,near,hidden,controlled,...distant];
ctx.Groups.sync={size:()=>group.length,index:i=>group[i]};
const deliveries=[];original.writeCustomEntitySnapshot=(player,units)=>{
 deliveries.push({key:player.con.hashCode(),at:now,ids:units.a.map(u=>u.id)});
};
const start=now;
for(let t=0;t<1200;t+=25){now=start+t;policy.interestUpdate();assert.equal(policy.interestEnabled,true);}
const narrow=deliveries.filter(d=>d.key===7),full=deliveries.filter(d=>d.key===8);
assert.deepEqual(narrow.map(d=>d.at-start),[50,250,450,650,850,1050]);
assert.deepEqual(full.map(d=>d.at-start),[100,400,700,1000]);
assert.equal(policy.interestUnitMode,'mixed-per-player');
assert.equal(policy.interestAOIPlayers,1);assert.equal(policy.interestFullViewPlayers,1);
assert.equal(policy.interestStates.c7.entityMode,'aoi');
assert.equal(policy.interestStates.c8.entityMode,'full-view');
assert.equal(policy.interestStates.c7.farNextBucket,0);
assert.equal(policy.interestStates.c8.farNextBucket,undefined);
assert.equal(policy.interestFullViewEntityTicks,4);
assert.deepEqual(JSON.parse(JSON.stringify(policy.interestPhaseTicks)),{state:4,entities:6,buildings:4});
for(const unit of distant){
 assert.equal(narrow.filter(d=>d.ids.includes(unit.id)).length,1);
 assert.equal(full.filter(d=>d.ids.includes(unit.id)).length,4);
}
for(const d of deliveries){
 assert.ok(d.ids.includes(mine.id));assert.ok(d.ids.includes(controlled.id));
 assert.ok(!d.ids.includes(hidden.id));
}
assert.equal(policy.interestStates.c7.entityBatches,6);
assert.equal(policy.interestStates.c8.entityBatches,4);
assert.equal(policy.interestBuildingRecords,4); // both clients retain building delivery
assert.equal(listeners.a[0],policy.interestWrapper);
assert.ok(original.snapshotSyncTime<=now); // native global branch is suppressed, not duplicated
// A wide client's invalid camera remains safe without bypassing the narrow client.
wide.con.viewWidth=NaN;now=start+1200;policy.interestUpdate();
assert.equal(policy.interestUnitMode,'mixed-per-player');
// Repeated camera transitions do not restart shared phases or replay missed slots.
wide.con.viewWidth=100;wide.con.viewHeight=100;
now=start+1250;policy.interestUpdate();
assert.equal(policy.interestUnitMode,'aoi');assert.equal(policy.interestAOIPlayers,2);
assert.equal(policy.interestStates.c8.entityMode,'aoi');
assert.equal(deliveries.filter(d=>d.key===8).at(-1).at,start+1250);
receiver.con.viewWidth=700;receiver.con.viewHeight=700;
now=start+1300;policy.interestUpdate();
assert.equal(policy.interestUnitMode,'mixed-per-player');
assert.equal(policy.interestStates.c7.entityMode,'full-view');
assert.equal(deliveries.filter(d=>d.key===7).at(-1).at,start+1300);
const after=deliveries.length;policy.interestUpdate();assert.equal(deliveries.length,after);
// All-wide clients keep the shared custom scheduler and native fog checks.
wide.con.viewWidth=700;wide.con.viewHeight=700;now=start+1450;policy.interestUpdate();
assert.equal(policy.interestUnitMode,'full-view-per-player');
assert.equal(policy.interestAOIPlayers,0);assert.equal(policy.interestFullViewPlayers,2);
players=[wide];now=start+1500;policy.interestUpdate();now=start+1600;policy.interestUpdate();
assert.equal(policy.interestStates.c7,undefined); // departed clients do not retain caches
// Missing camera is handled per player; PvP and manual disable still use native update.
assert.equal(policy.interestEnabled,true);
ctx.Vars.state.rules.pvp=true;const count=deliveries.length;
now=start+1700;policy.interestUpdate();assert.equal(deliveries.length,count);
assert.equal(policy.interestUnitMode,'native');
ctx.Vars.state.rules.pvp=false;
ctx.Groups.sync={size:()=>0,index:()=>null};const packetCount=packets.length;
now=start+1900;policy.interestUpdate();
assert.ok(packets.slice(packetCount).some(a=>a[0]===wide.con&&a[1]===0));
// Per-player scheduling keeps the same serialization fail-safe and listener restore.
ctx.Groups.sync={size:()=>group.length,index:i=>group[i]};
original.writeCustomEntitySnapshot=()=>{throw Error('per-player serialization');};
now=start+2200;policy.interestUpdate();
assert.equal(policy.interestEnabled,false);assert.equal(listeners.a[0],original);
assert.match(policy.interestError,/per-player serialization/);
console.log('mixed-player 200/300ms cadence, six far buckets, fog, building delivery, camera transitions and disconnect cleanup passed');
"""
        result = subprocess.run(['node', '-e', harness],
                                input=json.dumps(INSTALL_JS + experimental_config().split('p.interestPid=')[0]),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_cold_impact_reactor_priority_500ms_threshold_fog_and_full_view(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
policy.interestStaggerEnabled=true;policy.interestReactorEnabled=true;
const cold=build(1001,9999),hot=build(1002,9999);cold.block={id:7,size:3};hot.block={id:7,size:3};
cold.warmup=.69;hot.warmup=.7;
ctx.Vars.content.block=()=>({id:7});ctx.Packages.mindustry.world.meta.BlockFlag.reactor=2;
const normal=[...buildings,cold,hot];ctx.Vars.indexer.getFlagged=(team,flag)=>new Seq(flag===2?[cold,hot]:normal);
const times=[];ctx.Packages.mindustry.gen.Call.blockSnapshot=(...args)=>{
 packets.push(args);if(args[2].positions.includes(cold.pos()))times.push(now);
};
const start=now;
for(let t=0;t<2000;t+=25){now=start+t;policy.interestUpdate();assert.equal(policy.interestEnabled,true);}
assert.deepEqual(times.map(t=>t-start),[125,625,1125,1625]);
assert.equal(policy.interestReactorCount,2);assert.equal(policy.interestReactorRecords,4);
assert.equal(policy.interestReactorMaxAgeMs,500);
cold.warmup=.7;now=start+2125;policy.interestUpdate();assert.equal(times.length,5);
now=start+2625;policy.interestUpdate();assert.equal(times.length,5);
cold.warmup=.1;now=start+3125;policy.interestUpdate();assert.equal(times.length,6);
cold.team=2;cold.hidden=true;receiver.con.viewWidth=700;receiver.con.viewHeight=700;
now=start+3625;policy.interestUpdate();now=start+3750;policy.interestUpdate();
assert.equal(policy.interestUnitMode,'native-full-view');assert.equal(times.length,6);
cold.hidden=false;now=start+4250;policy.interestUpdate();assert.equal(times.length,7);
console.log('500ms cold reactor lane, strict 70% threshold, final transition, fog and full-view handling passed');
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_200ms_near_300ms_other_phases_six_far_buckets_and_all_controlled_units(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
policy.interestStaggerEnabled=true;policy.interestEntityIntervalMs=200;
policy.interestFarBucketsEnabled=true;policy.interestFarBucketCount=6;policy.interestFarBucketRounds=[0,0,0,0,0,0];
const distant=Array.from({length:12},(_,i)=>new Unit(i+20,1000,0));
const group=[mine,near,hidden,...distant];ctx.Groups.sync={size:()=>group.length,index:i=>group[i]};
const start=now;
for(let t=0;t<1200;t+=50){now=start+t;policy.interestUpdate();assert.equal(policy.interestEnabled,true);}
assert.deepEqual(JSON.parse(JSON.stringify(policy.interestPhaseTicks)),{state:4,entities:6,buildings:4});
assert.deepEqual(Array.from(policy.interestFarBucketRounds),[1,1,1,1,1,1]);
for(const unit of distant)assert.equal(sent.filter(batch=>batch.includes(unit.id)).length,1);
assert.equal(sent.filter(batch=>batch.includes(near.id)).length,6);
// Another player's controlled unit remains full-rate outside this receiver's view.
const controlled=new Unit(101,1000,0);group.push(controlled);
const owner={con:{hasConnected:true,isConnected:()=>true},dead:()=>false,unit:()=>controlled};
ctx.Groups.player={size:()=>2,index:i=>i===0?receiver:owner};
for(let bucket=0;bucket<6;bucket++){
 const chosen=policy.selectEntities(receiver,policy.view(receiver),false,ctx.Groups.sync,new IntSeq(),bucket);
 assert.ok(chosen.a.includes(controlled));
}
// With a working supplement, this same unit must not be duplicated by primary packets.
policy.controlledEnabled=true;policy.supplement=function(){};
for(let bucket=0;bucket<6;bucket++){
 const chosen=policy.selectEntities(receiver,policy.view(receiver),false,ctx.Groups.sync,new IntSeq(),bucket);
 assert.ok(!chosen.a.includes(controlled));assert.ok(!chosen.a.includes(mine));
 assert.ok(chosen.a.includes(near));
}
policy.controlledEnabled=false;
assert.ok(policy.selectEntities(receiver,policy.view(receiver),false,ctx.Groups.sync,new IntSeq(),0).a.includes(controlled));
controlled.hidden=true;const hiddenIds=new IntSeq();
assert.ok(!policy.selectEntities(receiver,policy.view(receiver),false,ctx.Groups.sync,hiddenIds,0).a.includes(controlled));
assert.ok(hiddenIds.a.includes(controlled.id));
// Admission and the optimization guard both permit twelve players.
ctx.Groups.player={size:()=>12,index:()=>receiver};assert.equal(policy.preflight(),true);
ctx.Groups.player={size:()=>13,index:()=>receiver};assert.throws(()=>policy.preflight(),/player bound/);
console.log('200ms near entities, independent 300ms state/buildings, 1200ms far coverage, global controlled units and twelve-player bounds passed');
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_relaxed_profile_ignores_isolated_stalls_but_records_sustained_fallback(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source.policy,ctx);
const metric=policy.readMetric;
policy.readMetric=(path,key)=>key==='Pid'?123:metric(path,key);
vm.runInContext(source.config,ctx);
assert.equal(policy.interestStaggerEnabled,true);assert.equal(policy.interestFarBucketsEnabled,true);
assert.equal(policy.interestUpdateGapMs,5000);assert.equal(policy.interestBudgetMs,20);
original.writeStateSnapshot=()=>{states++;now+=120;};
for(let i=0;i<2;i++){now+=300;policy.interestUpdate();assert.equal(policy.interestEnabled,true);}
assert.equal(policy.interestSlowCount,2);assert.equal(policy.interestLastFallbackEvent,null);
original.writeStateSnapshot=()=>states++;now+=300;policy.interestUpdate();
assert.equal(policy.interestSlowCount,0); // a completed healthy dispatch resets the streak
original.writeStateSnapshot=()=>{states++;now+=120;};
for(let i=0;i<3;i++){now+=300;policy.interestUpdate();}
assert.equal(policy.interestEnabled,false);assert.equal(listeners.a[0],original);
assert.match(policy.interestError,/100 ms.*3 consecutive/);
assert.equal(policy.interestLastFallbackEvent.kind,'aoi-safety-fallback');
assert.equal(policy.interestLastFallbackEvent.pid,123);
// Manual restore and expected full-view delegation do not create incidents.
const last=policy.interestLastFallbackEvent;policy.restoreOriginal();
assert.equal(policy.interestLastFallbackEvent,last);
// Relaxed memory floors retain a timed soft floor and an immediate emergency floor.
availableKB=90*1024;policy.interestMemoryCheckAt=0;
for(let i=0;i<10;i++){now+=1000;assert.doesNotThrow(()=>policy.runtimeGuard(now));}
now+=1000;assert.throws(()=>policy.runtimeGuard(now),/below 96 MiB for 10000 ms/);
availableKB=63*1024;now+=1000;assert.throws(()=>policy.runtimeGuard(now),/64 MiB emergency/);
availableKB=400000;swapKB=100*1024;now+=1000;assert.doesNotThrow(()=>policy.runtimeGuard(now));
swapKB=129*1024;now+=1000;assert.throws(()=>policy.runtimeGuard(now),/128 MiB/);
swapKB=0;usedHeap=940;now+=1000;assert.throws(()=>policy.runtimeGuard(now),/heap pressure/);
console.log('isolated-stall tolerance, healthy reset, sustained fallback event, native restore and relaxed memory guards passed');
"""
        result = subprocess.run(['node', '-e', harness],
                                input=json.dumps({'policy': INSTALL_JS, 'config': experimental_config()}),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_far_buckets_cover_all_units_and_preserve_near_fog_and_native_paths(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
assert.equal(policy.interestFarBucketsEnabled,false);
policy.interestFarBucketsEnabled=true;policy.interestStaggerEnabled=true;
const distant=Array.from({length:16},(_,i)=>new Unit(i+20,1000,0));
const negative=new Unit(-5,1000,0),border=new Unit(80,80,0);
const group=[mine,near,hidden,border,...distant,negative,{id:90,x:9999,y:9999,isSyncHidden:()=>false}];
ctx.Groups.sync={size:()=>group.length,index:i=>group[i]};
const start=now;
for(let t=0;t<1200;t+=100){now=start+t;policy.interestUpdate();assert.equal(policy.interestEnabled,true);}
assert.equal(sent.length,4);
const counts=new Map();
for(const batch of sent){
 for(const id of [mine.id,near.id,border.id,90])assert.ok(batch.includes(id));
 assert.ok(!batch.includes(hidden.id));
 for(const id of batch)counts.set(id,(counts.get(id)||0)+1);
}
for(const unit of [...distant,negative])assert.equal(counts.get(unit.id),1);
assert.deepEqual(Array.from(policy.interestFarBucketRounds),[1,1,1,1]);
// A camera jump refreshes newly near units on the next entity round regardless of bucket.
receiver.con.viewX=1000;now=start+1300;policy.interestUpdate();
for(const unit of distant)assert.ok(sent.at(-1).includes(unit.id));
// A hidden entity remains hidden even when it belongs to the active far bucket.
const ids=new IntSeq();const chosen=policy.selectEntities(receiver,policy.view(receiver),true,ctx.Groups.sync,ids,0);
assert.ok(ids.a.includes(hidden.id));assert.ok(!chosen.a.some(e=>e.id===hidden.id));
// Invalid camera reports preserve native visibility/full-selection semantics.
assert.equal(policy.selectEntities(receiver,null,false,ctx.Groups.sync,new IntSeq(),0).size,group.length-1);
// Long dispatch gaps advance one bucket only, never skip/replay multiple groups.
const previous=Array.from(policy.interestFarBucketRounds);
now+=5000;policy.interestSend(now);
assert.equal(policy.interestFarBucketRounds.reduce((a,b)=>a+b,0),previous.reduce((a,b)=>a+b,0)+1);
const after=sent.length;policy.interestSend(now);assert.equal(sent.length,after);
// Full-view and PvP still delegate entity synchronization to native.
policy.interestLastUpdate=0;receiver.con.viewWidth=700;receiver.con.viewHeight=700;
now+=300;const beforeNative=sent.length;policy.interestUpdate();assert.equal(sent.length,beforeNative);
assert.equal(policy.interestUnitMode,'native-full-view');
ctx.Vars.state.rules.pvp=true;now+=300;policy.interestUpdate();assert.equal(sent.length,beforeNative);
events[events.length-1]();assert.equal(Object.keys(policy.interestStates).length,0);
// New-world/new-receiver scheduling starts a fresh four-round rotation.
ctx.Vars.state.rules.pvp=false;receiver.con.viewWidth=100;receiver.con.viewHeight=100;
policy.interestLastUpdate=0;now+=300;policy.interestUpdate();now+=100;policy.interestUpdate();
assert.equal(policy.interestStates.c7.farNextBucket,1);
console.log('four-round far-unit coverage, stable IDs, negative IDs, camera entry, fog, native bypass and missed-slot handling passed');
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_staggered_phases_preserve_rate_and_skip_missed_slots(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.Packages.mindustry.net.Administration.Config.snapshotInterval.num=()=>300;
policy.interestStaggerEnabled=true;
const start=now,step=ms=>{now=start+ms;policy.interestUpdate();assert.equal(policy.interestEnabled,true);};
step(0);assert.equal(states,1);assert.equal(sent.length,0);
assert.equal(Object.keys(policy.interestStates).length,0); // state-only must not touch caches
step(99);assert.equal(sent.length,0);
step(100);assert.equal(sent.length,1);assert.equal(policy.interestBuildingRecords,0);
step(199);assert.equal(policy.interestBuildingRecords,0);
step(200);assert.equal(policy.interestBuildingRecords,2);
const cache=policy.interestStates.c7;
step(300);assert.equal(policy.interestStates.c7,cache);
for(let t=400;t<1200;t+=100)step(t);
assert.deepEqual(JSON.parse(JSON.stringify(policy.interestPhaseTicks)),{state:4,entities:4,buildings:4});
assert.equal(policy.interestTicks,4);assert.equal(policy.interestDispatchTicks,12);
// Overdue work dispatches at most once per phase and never replays a backlog.
now=start+5000;policy.interestSend(now);const dispatches=policy.interestDispatchTicks;
const counts=JSON.stringify(policy.interestPhaseTicks);
policy.interestSend(now);assert.equal(policy.interestDispatchTicks,dispatches);
assert.equal(JSON.stringify(policy.interestPhaseTicks),counts);
events[events.length-1]();assert.equal(policy.interestPhaseOrigin,null);
assert.equal(policy.interestPhaseNext,null);
// Full-view delegates state/entities to native; custom buildings still get one phase.
policy.interestLastUpdate=0;receiver.con.viewWidth=700;receiver.con.viewHeight=700;
const beforeStates=states,beforeEntities=sent.length,beforeBuildings=policy.interestPhaseTicks.buildings;
now+=300;policy.interestUpdate();now+=200;policy.interestUpdate();
assert.equal(states,beforeStates);assert.equal(sent.length,beforeEntities);
assert.equal(policy.interestPhaseTicks.buildings,beforeBuildings+1);
assert.equal(policy.interestUnitMode,'native-full-view');
receiver.con.viewWidth=100;receiver.con.viewHeight=100;
now+=100;policy.interestUpdate();assert.equal(policy.interestPhaseOrigin,now);
assert.equal(states,beforeStates+1);
console.log('staggered 0/100/200ms dispatch, unchanged phase rates, bounded catch-up and full-view transitions passed');
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_host_memory_guard_requires_persistence_with_emergency_floor(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
availableKB=120*1024;
policy.runtimeGuard(now);assert.equal(policy.interestMemorySample.hostState,'pending');
assert.equal(policy.interestMemorySample.hostLowForMs,0);
for(let i=0;i<4;i++){now+=1000;assert.doesNotThrow(()=>policy.runtimeGuard(now));}
now+=1000;assert.throws(()=>policy.runtimeGuard(now),/below 128 MiB for 5000 ms/);
assert.equal(policy.interestMemorySample.hostState,'sustained');
assert.equal(policy.interestMemorySample.hostAvailableKB,120*1024);
// A single observed recovery resets the consecutive-low timer, even below 160 MiB.
availableKB=140*1024;now+=1000;policy.runtimeGuard(now);
assert.equal(policy.interestHostLowSince,null);assert.equal(policy.interestMemorySample.hostState,'ok');
availableKB=120*1024;now+=1000;policy.runtimeGuard(now);
assert.equal(policy.interestMemorySample.hostLowForMs,0);
// Fast repeated calls neither resample nor count as extra seconds.
const observed=policy.interestMemorySample;
for(let i=0;i<5;i++){now+=10;policy.runtimeGuard(now);}
assert.equal(policy.interestMemorySample,observed);
// No pressure duration is inferred across a missed observation window.
now+=3000;policy.runtimeGuard(now);assert.equal(policy.interestMemorySample.hostLowForMs,0);
now-=5000;policy.runtimeGuard(now);assert.equal(policy.interestMemorySample.hostLowForMs,0);
// Exact soft-floor boundary is healthy; exact hard-floor boundary is pending.
availableKB=128*1024;now+=1000;policy.runtimeGuard(now);
assert.equal(policy.interestMemorySample.hostState,'ok');
availableKB=96*1024;now+=1000;policy.runtimeGuard(now);
assert.equal(policy.interestMemorySample.hostState,'pending');
availableKB=96*1024-1;now+=1000;
assert.throws(()=>policy.runtimeGuard(now),/96 MiB emergency/);
assert.equal(policy.interestMemorySample.hostState,'critical');
// Existing heap/swap protections are unchanged and do not wait for host pressure.
availableKB=400000;usedHeap=900;now+=1000;
assert.throws(()=>policy.runtimeGuard(now),/heap pressure/);usedHeap=100;swapKB=65537;now+=1000;
assert.throws(()=>policy.runtimeGuard(now),/swap/);
console.log('sustained host pressure, transient recovery, sampling cadence, clock gaps and emergency floor passed');
"""
        r = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        print(r.stdout.strip())

    def test_building_fog_filter_and_full_view_entity_bypass(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
const own=build(10,0);own.hidden=true;
const enemy=build(11,0);enemy.team=2;enemy.hidden=true;
enemy.writeSync=()=>{throw Error('invisible enemy must not be serialized');};
const edge=build(12,0);edge.team=2;let nativeVisibilityCalls=0;
edge.inFogTo=team=>{assert.equal(team,1);nativeVisibilityCalls++;return false;};
buildings=[own,enemy,edge];
receiver.con.viewWidth=700;receiver.con.viewHeight=700;
policy.interestUpdate();
assert.equal(policy.interestEnabled,true);assert.equal(policy.interestUnitMode,'native-full-view');
assert.equal(policy.interestBuildingEffectiveMode,'aoi');
assert.equal(states,0);assert.equal(sent.length,0); // adapter must not duplicate native entity/state packets
assert.equal(policy.interestBuildingRecords,2);assert.equal(policy.interestBuildingFogSkipped,1);
assert.equal(nativeVisibilityCalls,1);assert.equal(resets,1);
assert.deepEqual(packets.flatMap(a=>a[2]?.positions||[]),[10,12]);
const st=policy.interestStates.c7;assert.equal(st.buildings.b11,undefined);
enemy.hidden=false;enemy.writeSync=w=>w.s.n+=10;now+=250;
policy.interestUpdate();assert.equal(policy.interestBuildingRecords,3);
enemy.hidden=true;now+=250;policy.interestUpdate();
assert.equal(policy.interestBuildingRecords,3);assert.equal(st.buildings.b11.fogHidden,true);
enemy.hidden=false;now+=250;policy.interestUpdate();
assert.equal(policy.interestBuildingRecords,4);assert.equal(policy.interestBuildingRevealed,1);
assert.equal(st.buildings.b11.fogHidden,false); // refreshed before its old interval expires
// Full-view mode keeps the custom building filter and does not reset caches each frame.
const batchBefore=nativeBuildingBatches;
for(let i=0;i<26;i++){now+=250;policy.interestUpdate();}
assert.equal(nativeBuildingBatches,batchBefore);assert.equal(policy.interestStates.c7,st);
assert.equal(states,0);assert.equal(sent.length,0);
// With fog disabled, never call any visibility method, even on an enemy.
ctx.Vars.state.rules.fog=false;enemy.hidden=true;
for(const b of buildings)b.inFogTo=()=>{throw Error('fog-disabled path must skip fog checks');};
now+=12500;policy.writeBuildings(receiver,policy.view(receiver),st,new Seq(buildings),now);
assert.equal(policy.interestEnabled,true);
// Visibility is decided separately for each receiving team, including allies.
const a=build(20,0);a.team=1;a.hidden=true;
const b=build(21,0);b.team=2;b.hidden=true;
buildings=[a,b];ctx.Vars.state.rules.fog=true;
const other={...receiver,team:()=>2,con:{...receiver.con,hashCode:()=>8}};
ctx.Groups.player={size:()=>2,index:i=>[receiver,other][i]};
vm.runInContext(source,ctx);packets=[];now+=250;policy.interestUpdate();
assert.deepEqual(packets.filter(p=>p[0]===receiver.con).flatMap(p=>p[2]?.positions||[]),[20]);
assert.deepEqual(packets.filter(p=>p[0]===other.con).flatMap(p=>p[2]?.positions||[]),[21]);
console.log('per-team native building visibility, reveal refresh, fog-disabled fast path and full-view filtering passed');
"""
        r = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        print(r.stdout.strip())

    def test_incremental_building_work_is_bounded_and_resumable(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
const attack=Array.from({length:2038},(_,i)=>build(i,0));
let reads=0,tileReads=0;
const seq={size:attack.length,get(i){reads++;return attack[i];}};
ctx.Vars.world.build=pos=>{tileReads++;return liveBuildings.get(pos)||null;};
const state={};const view=policy.view(receiver);
for(let round=0;round<50;round++){
 reads=tileReads=0;const before=policy.interestBuildingRecords;
 policy.writeBuildings(receiver,view,state,seq,now);
 assert.ok(reads<=128);assert.ok(tileReads<=16);
 assert.ok(policy.interestBuildingRecords-before<=64);
 assert.ok(state.buildingCount<=3072);
}
const delivered=new Set(packets.flatMap(a=>a[2]?.positions||[]));
assert.equal(delivered.size,2038); // no unsent half-window is skipped or starved
assert.equal(state.buildingCount,2038);assert.equal(buffersCreated,1);
// A soft yield preserves the unprocessed candidate and remains a successful turn.
const yielding={};let slowReads=0;
const slow={size:3,get(i){slowReads++;nanosOffset+=1500000;return attack[i];}};
policy.writeBuildings(receiver,view,yielding,slow,now);
assert.equal(yielding.cursor,1);assert.equal(yielding.buildingCount,1);
assert.equal(policy.interestEnabled,true);assert.ok(policy.interestBuildingYields>0);
policy.writeBuildings(receiver,view,yielding,slow,now);
assert.equal(yielding.cursor,2);assert.equal(yielding.buildingCount,2);
assert.equal(buffersCreated,1);
// Initialization has its own timing and yields without losing the first item.
policy.interestBuildingBuffer=null;streamInitNs=2500000;
const initial={};const justOne=new Seq([attack[10]]);
policy.writeBuildings(receiver,view,initial,justOne,now);
assert.equal(initial.cursor,0);assert.equal(initial.buildingCount,0);
assert.ok(policy.interestBuildingTimings.initialize.lastMs>=2.5);
streamInitNs=0;policy.writeBuildings(receiver,view,initial,justOne,now);
assert.equal(initial.buildingCount,1);assert.equal(buffersCreated,2);
// Generational sweep retires removed entries, with no per-cache Java lookups.
const cleanup={};const four=Array.from({length:4},(_,i)=>build(5000+i,0));
policy.writeBuildings(receiver,view,cleanup,new Seq(four),now);
assert.equal(cleanup.buildingCount,4);
liveBuildings.delete(5000);const replacement=build(5001,0);
ctx.Vars.world.build=()=>{throw Error('cache sweep must not cross into Java');};
const remaining=new Seq([replacement,four[2],four[3]]);
policy.writeBuildings(receiver,view,cleanup,remaining,now);
policy.writeBuildings(receiver,view,cleanup,remaining,now);
assert.equal(cleanup.buildingCount,3);assert.equal(cleanup.buildings.b5001.id,replacement.id);
// Replacing a live building in-place resends immediately, including identical block types.
const nextReplacement=build(5001,0);const oldRecords=policy.interestBuildingRecords;
policy.writeBuildings(receiver,view,cleanup,new Seq([nextReplacement]),now);
assert.equal(policy.interestBuildingRecords,oldRecords+1);
assert.equal(cleanup.buildingCount,3);
policy.writeBuildings(receiver,view,cleanup,new Seq(),now);
assert.equal(cleanup.buildingCount,0);
// Ring eviction bounds memory without an O(N) key enumeration.
policy.interestMaxClientBuildingRecords=4;const bounded={};
policy.writeBuildings(receiver,view,bounded,new Seq(attack.slice(0,8)),now);
assert.equal(bounded.buildingCount,4);assert.equal(bounded.buildingKeys.length,4);
assert.equal(Object.keys(bounded.buildings).length,4);
policy.interestMaxClientBuildingRecords=3072;
// An indivisible slow native serialization still trips the hard guard and is measured.
const slowBuild=build(6000,0);slowBuild.writeSync=w=>{w.s.n+=10;nanosOffset+=10000000;};
policy.interestDeadlineNs=now*1000000+nanosOffset+8000000;
assert.throws(()=>policy.writeBuildings(receiver,view,{},new Seq([slowBuild]),now),/budget.*building-serialize/);
assert.ok(policy.interestBuildingTimings.serialize.lastMs>=10);
assert.ok(policy.interestBuildingTimings.total.lastMs>=10);
console.log('bounded scanning and cleanup, full delivery, soft yields, warm buffers, replacements, cache eviction and hard guards passed');
"""
        r = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        print(r.stdout.strip())

    def test_interest_policy(self):
        r = subprocess.run(['node', '-e', HARNESS], input=json.dumps(INSTALL_JS),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        print(r.stdout.strip())

    def test_B_installs_wrapper_but_delegates_native_updates(self):
        harness = HARNESS.split('vm.createContext(ctx);')[0] + r"""
vm.createContext(ctx);vm.runInContext(source,ctx);
assert.notEqual(listeners.a[0],original);
assert.equal(policy.interestInstalled,true);
assert.equal(policy.interestEnabled,false);
assert.equal(policy.experimentGroup,'B-wrapper-only');
for(let i=0;i<120;i++){now+=16;listeners.a[0].update();}
assert.equal(updates,120);
assert.equal(states,0);assert.equal(resets,0);
assert.equal(sent.length,0);assert.equal(packets.length,0);
assert.equal(policy.interestTicks,0);
console.log('B delegates every update to native sync without AOI work');
"""
        # Keep the core policy out of this adapter-isolation harness; it is
        # tested by run_network_policy_tests.py and unchanged between A and B.
        from mlogent_ops.world_network_policy import INTEREST_INSTALL_JS
        b = INTEREST_INSTALL_JS.replace('policy.interestEnabled=true;',
                                       'policy.interestEnabled=false;', 1)
        b += "\nthis._mcpSnapshotPolicy.experimentGroup='B-wrapper-only';"
        self.assertIn(b, install_script('wrapper'))
        r = subprocess.run(['node', '-e', harness], input=json.dumps(b),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
