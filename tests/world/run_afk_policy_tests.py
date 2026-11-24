"""Request-only AFK challenge, timeout, recovery and callback lifetime tests."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_afk_policy import INSTALL_JS


class AfkPolicyTests(unittest.TestCase):
    def test_challenge_requests_timeout_recovery_and_reinstall(self):
        script = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=10000,menuFail=false;const players=[],menus=[],filters=[],ticks=[],loads=[],sent=[];
const p={interestEnabled:true,adaptiveClients:{},interestStates:{},resetBuildingState:s=>{s.reset=true;}};
const player=id=>({con:{hashCode:()=>id,hasConnected:true,isConnected:()=>true},sendMessage:m=>sent.push(m)});
players.push(player(1),player(2));
const ctx={_mcpSnapshotPolicy:p,JavaAdapter:function(type,o){return o;},
 java:{lang:{System:{currentTimeMillis:()=>now},String:{},Class:{forName:()=>0},reflect:{Array:{newInstance:(t,n)=>new Array(n)}}}},
 Packages:{arc:{math:{Mathf:{random:(a,b)=>a}},util:{CommandHandler$CommandRunner:{}}},mindustry:{
  net:{Administration$ActionFilter:{}},ui:{Menus$MenuListener:{},Menus:{registerMenu:m=>{menus.push(m);return menus.length-1;}}},
  gen:{Call:{menu:(...a)=>{if(menuFail)throw Error('menu send failed');}}},
  game:{EventType:{Trigger:{update:'update'},WorldLoadEvent:'load'}}}},
 Vars:{state:{rules:{pvp:false}},netServer:{admins:{addActionFilter:f=>filters.push(f)},clientCommands:{removeCommand(){},register(){}}}},
 Groups:{player:{size:()=>players.length,index:i=>players[i]}},Events:{run:(e,f)=>ticks.push(f),on:(e,f)=>loads.push(f)}};
vm.createContext(ctx);const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
vm.runInContext(source,ctx);p.afkEnabled=true;p.afkTick(now);
ctx.p={packet:'KickCallPacket'};ctx.root={packet:'KickCallPacket'};
assert.equal(p.afkStates.c1.mode,'active');
now+=179000;
// Periodic network/mining activity is explicitly not one of the tracked types.
assert.equal(filters[0].allow({type:'mining',player:players[0]}),true);
p.afkTick(now);assert.equal(p.afkStates.c1.mode,'active');
filters[0].allow({type:'placeBlock',player:players[1]});
now+=1000;p.afkTick(now);assert.equal(p.afkStates.c1.mode,'pending');assert.equal(p.afkStates.c2.mode,'active');
assert.equal(p.afkCadence(players[0],now),null); // 30-second answer grace
filters[0].allow({type:'control',player:players[0]});
assert.equal(p.afkStates.c1.mode,'pending');
now+=30000;p.afkTick(now);assert.equal(p.afkStates.c1.mode,'afk');
assert.equal(p.afkCadence(players[0],now).interval,1000);
assert.equal(p.afkSupplementDue(players[0],now),true);now+=100;assert.equal(p.afkSupplementDue(players[0],now),false);
assert.equal(p.afkSupplementDue(players[1],now),true);
// A late confirmation restores normal sync without reopening the menu.
p.adaptiveClients.c1={level:3};p.interestStates.c1={};
menus[0].get(players[0],0);assert.equal(p.afkStates.c1.mode,'active');
assert.equal(p.adaptiveClients.c1.level,0);assert.equal(p.interestStates.c1.reset,true);
menus[0].get(players[0],1);assert.equal(p.afkStates.c1.mode,'active'); // stale response ignored
now+=180000;p.afkTick(now);menus[0].get(players[0],1);assert.equal(p.afkStates.c1.mode,'afk');
now+=5000;p.afkAsk(players[0],now);assert.equal(p.afkCadence(players[0],now).interval,1000);
p.adaptiveClients.c1={level:3};p.interestStates.c1={};
menus[0].get(players[0],0);
assert.equal(p.afkStates.c1.mode,'active');assert.equal(p.afkCadence(players[0],now),null);
assert.equal(p.adaptiveClients.c1.level,0);assert.equal(p.interestStates.c1.reset,true);
// Another player's answer cannot complete this player's challenge.
now+=180000;p.afkTick(now);
menus[0].get(players[1],-1);assert.equal(p.afkStates.c1.mode,'pending');
menus[0].get(players[0],-1);assert.equal(p.afkStates.c1.reason,'closed');
now+=5000;p.afkAsk(players[0],now);menus[0].get(players[0],99);assert.equal(p.afkStates.c1.mode,'pending');
menus[0].get(players[0],0);assert.equal(p.afkStates.c1.mode,'active');
// Menu delivery errors never newly penalize an active player.
menus[0].get(players[1],99);p.afkStates.c2.mode='active';p.afkStates.c2.limited=false;
menuFail=true;now+=5000;p.afkAsk(players[1],now);assert.equal(p.afkStates.c2.mode,'active');
menuFail=false;players.pop();p.afkTick(now);assert.equal(p.afkStates.c2,undefined);
// World load, disable and PvP remove restrictions.
loads[0]();assert.equal(Object.keys(p.afkStates).length,0);
p.afkTick(now);ctx.Vars.state.rules.pvp=true;p.afkTick(now);assert.equal(Object.keys(p.afkStates).length,0);
vm.runInContext(source,ctx);assert.equal(menus.length,1);assert.equal(filters.length,1);assert.equal(ticks.length,1);assert.equal(loads.length,1);
"""
        result=subprocess.run(['node','-e',script],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':
    unittest.main()
