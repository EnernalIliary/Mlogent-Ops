"""Automatic idle status, badge, chat/action recovery and callback lifetime."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_afk_policy import INSTALL_JS

class AfkPolicyTests(unittest.TestCase):
    def test_automatic_idle_badge_interactions_recovery_and_reinstall(self):
        script=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=10000;const players=[],filters=[],ticks=[],events={},sent=[],removed=[];
const p={interestEnabled:true,adaptiveClients:{},interestStates:{},resetBuildingState:s=>s.reset=true};
const player=id=>({name:'player'+id,locale:'en',uuid:()=> 'uuid'+id,con:{hashCode:()=>id,hasConnected:true,isConnected:()=>true},sendMessage:m=>sent.push(m)});
players.push(player(1),player(2));
const ctx={_mcpSnapshotPolicy:p,JavaAdapter:function(type,object){return object;},
java:{lang:{System:{currentTimeMillis:()=>now}}},
Packages:{arc:{func:{Cons:{}},util:{CommandHandler$CommandRunner:{}}},mindustry:{net:{Administration$ActionFilter:{}},
game:{EventType:{Trigger:{update:'update'},WorldLoadEvent:'load',PlayerChatEvent:'chat',PlayerLeave:'leave'}}}},
Vars:{state:{rules:{pvp:false}},netServer:{admins:{actionFilters:{insert:(idx,f)=>filters.splice(idx,0,f)}},clientCommands:{removeCommand:name=>removed.push(name),register(){}}}},
Groups:{player:{size:()=>players.length,index:i=>players[i]}},
Events:{run:(e,f)=>ticks.push(f),on:(e,f)=>(events[e]??=[]).push(f)}};
vm.createContext(ctx);const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
vm.runInContext(source,ctx);p.afkEnabled=true;p.afkTick(now);
ctx.p={packet:'unrelated'};ctx.root={packet:'unrelated'};
assert.equal(p.afkStates.c1.mode,'active');assert.equal(p.afkModeVersion,2);
now+=179000;filters[0].allow({type:'mining',player:players[0]});
filters[0].allow({type:'placeBlock',player:players[1]});
now+=1000;p.afkTick(now);
assert.equal(p.afkStates.c1.mode,'afk');assert.equal(p.afkStates.c2.mode,'active');
assert.equal(players[0].name,'[yellow][AFK][] player1');
assert.equal(p.afkBadge(players[0]),'[yellow][AFK][] ');
assert.equal(p.afkCadence(players[0],now).interval,1000);
assert.equal(p.afkSupplementDue(players[0],now),true);now+=100;assert.equal(p.afkSupplementDue(players[0],now),false);
assert.equal(p.afkSupplementDue(players[1],now),true);
const entered=sent.length;p.afkTick(now);assert.equal(sent.length,entered);
// Chat restores the original name and flushes delivery state, without bypassing bandwidth.
p.adaptiveClients.c1={level:3,lastEntity:123};p.interestStates.c1={reactorState:{}};
events.chat[0].get({player:players[0],message:'anything'});
assert.equal(p.afkStates.c1.mode,'active');assert.equal(players[0].name,'player1');
assert.equal(p.adaptiveClients.c1.level,3);assert.equal(p.adaptiveClients.c1.nextEntity,0);
assert.equal(p.interestStates.c1.reset,true);assert.equal(p.interestStates.c1.reactorState.reset,true);
assert.equal(p.afkCadence(players[0],now),null);
for(const type of ['placeBlock','breakBlock','configure','control','buildSelect','commandUnits','commandBuilding']){
 now+=180000;p.afkTick(now);assert.equal(p.afkStates.c1.mode,'afk');
 assert.equal(filters[0].allow({type,player:players[0]}),true);
 assert.equal(p.afkStates.c1.mode,'active');assert.equal(p.afkBadge(players[0]),'');
}
// A permission denial after the observer still counts as attempted interaction.
now+=180000;p.afkTick(now);filters.push({allow:()=>false});
assert.equal(filters.every(f=>f.allow({type:'placeBlock',player:players[0]})),false);
assert.equal(p.afkStates.c1.mode,'active');filters.pop();
// Commands also count as chat; unrelated players cannot clear each other's state.
now+=180000;p.afkTick(now);events.chat[0].get({player:players[1],message:'/help'});
assert.equal(p.afkStates.c1.mode,'afk');assert.equal(p.afkStates.c2.mode,'active');
events.chat[0].get({player:players[0],message:'/push question'});assert.equal(p.afkStates.c1.mode,'active');
// Old modal callbacks do nothing, and reinstall creates no menu or duplicate listeners.
now+=180000;p.afkTick(now);p.afkAnswer(players[0],0);assert.equal(p.afkStates.c1.mode,'afk');
vm.runInContext(source,ctx);p.afkEnabled=true;
assert.equal(filters.length,1);assert.equal(ticks.length,1);assert.equal(events.chat.length,1);assert.equal(events.load.length,1);
assert.ok(removed.includes('afkverify'));
events.leave[0].get({player:players[1]});assert.equal(p.afkStates.c2,undefined);assert.equal(players[1].name,'player2');
events.load[0]();assert.equal(Object.keys(p.afkStates).length,0);assert.equal(players[0].name,'player1');
p.afkTick(now);now+=180000;p.afkTick(now);p.afkEnabled=false;p.afkTick(now);
assert.equal(Object.keys(p.afkStates).length,0);assert.equal(players[0].name,'player1');
p.afkEnabled=true;ctx.Vars.state.rules.pvp=true;p.afkTick(now);assert.equal(Object.keys(p.afkStates).length,0);
'''
        result=subprocess.run(['node','-e',script],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
