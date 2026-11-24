"""Following distinct teammate plans prompts verification; only failure kicks."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_poly_verification import INSTALL_JS


class PolyVerificationTests(unittest.TestCase):
    def test_following_challenge_pass_failure_limits_and_cleanup(self):
        harness=r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=10000,failMenu=false;const menus=[],filters=[],ticks=[],loads=[],kicks=[],shown=[];
const player=(id,team=1)=>({team:()=>team,con:{hashCode:()=>id,hasConnected:true,isConnected:()=>true},
 sendMessage(){},kick:(reason,duration)=>kicks.push({id,reason,duration})});
const players=[player(1),player(2),player(3,2)];
const p={afkStates:{}},ctx={_mcpSnapshotPolicy:p,JavaAdapter:function(t,o){return o;},
 java:{lang:{System:{currentTimeMillis:()=>now},String:{},Class:{forName:()=>0},reflect:{Array:{newInstance:(t,n)=>new Array(n)}}}},
 Packages:{arc:{math:{Mathf:{random:(a,b)=>a}}},mindustry:{net:{Administration$ActionFilter:{}},
 ui:{Menus$MenuListener:{},Menus:{registerMenu:o=>{menus.push(o);return menus.length-1;}}},
 gen:{Call:{menu:(...a)=>{if(failMenu)throw Error('menu delivery');
 const match=a[3].match(/(\d+) \+ (\d+) = \?/);assert.ok(match);
 const expected=Number(match[1])+Number(match[2]);
 assert.equal(a[4][0].filter(x=>Number(x)===expected).length,1);
 assert.ok(a[4][0].every(x=>/^-?\d+$/.test(x)));shown.push(a);}}},
 game:{EventType:{Trigger:{update:'update'},WorldLoadEvent:'load'}}}},
 Vars:{netServer:{admins:{addActionFilter:f=>filters.push(f)}}},
 Groups:{player:{size:()=>players.length,index:i=>players[i]}},Events:{run:(e,f)=>ticks.push(f),on:(e,f)=>loads.push(f)}};
vm.createContext(ctx);const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
vm.runInContext(source,ctx);p.polyEnabled=true;
ctx.p={packet:'KickCallPacket'};ctx.root={packet:'KickCallPacket'};
const action=(who,pos,config=null)=>({type:'placeBlock',player:players[who],tile:{pos:()=>pos},block:{id:5},rotation:0,config});
const request=(who,pos,config=null)=>{assert.equal(filters[0].allow(action(who,pos,config)),true);};
request(0,1,'config');for(let i=0;i<20;i++)request(1,1);
assert.equal(p.polyStates.c2.hits.length,1);assert.equal(shown.length,0);assert.equal(kicks.length,0);
// Different team does not follow this team's owner.
request(2,1);assert.equal(p.polyStates.c3.hits.length,0);
for(let pos=2;pos<=5;pos++){request(0,pos,'config');request(1,pos);}
assert.equal(shown.length,1);assert.equal(p.polyStates.c2.mode,'pending');
assert.equal(p.polyStates.c1.mode,'watch');assert.equal(kicks.length,0);
assert.equal(p.polyStates.c2.hits.filter(h=>h.missingConfig).length,5);
// The initiator's click cannot answer the follower's challenge.
menus[0].get(players[0],0);assert.equal(p.polyStates.c2.mode,'pending');
const actualPrompt=shown.at(-1)[3].match(/(\d+) \+ (\d+) = \?/);
const actualAnswer=Number(actualPrompt[1])+Number(actualPrompt[2]);
const actualOption=shown.at(-1)[4][0].findIndex(x=>Number(x)===actualAnswer);
menus[0].get(players[1],actualOption);assert.equal(p.polyStates.c2.mode,'watch');
assert.equal(p.polyStats.passed,1);assert.equal(kicks.length,0);
for(let pos=10;pos<20;pos++){request(0,pos);request(1,pos);}
assert.equal(shown.length,1); // five-minute successful verification grace
now+=300001;
for(let pos=20;pos<25;pos++){request(0,pos);request(1,pos);}
now+=29999;p.polyTick(now);assert.equal(kicks.length,0);
now+=1;p.polyTick(now);assert.equal(kicks.length,1);assert.equal(kicks[0].id,2);assert.equal(kicks[0].duration,0);
menus[0].get(players[1],0);p.polyTick(now);assert.equal(kicks.length,1); // no duplicate kick
// Reset and exercise explicit wrong-answer and close handling.
for(const option of [99,-1]){
 loads[0]();now+=1000;for(let pos=30;pos<35;pos++){request(0,pos);request(1,pos);}
 menus[0].get(players[1],option);assert.equal(p.polyStates.c2.mode,'kicked');
}
assert.equal(kicks.length,3);
// Sparse overlap across more than 60 seconds does not accumulate to a prompt.
loads[0]();now+=1000;request(0,40);request(1,40);now+=61000;
for(let pos=41;pos<45;pos++){request(0,pos);request(1,pos);}
assert.equal(p.polyStates.c2.hits.length,4);assert.equal(p.polyStates.c2.mode,'watch');
// Failed menu delivery never kicks and does not start a deadline.
failMenu=true;request(0,45);request(1,45);assert.equal(p.polyStates.c2.mode,'watch');
now+=31000;p.polyTick(now);assert.equal(kicks.length,3);assert.equal(p.polyStats.menuErrors,1);failMenu=false;
// Raw repeated placement observations do not retain pooled action objects.
loads[0]();for(let pos=0;pos<10000;pos++)request(0,pos);
assert.ok(p.polySlots.length<=2048);assert.ok(Object.keys(p.polyTargets).length<=2048);
assert.ok(Object.keys(p.polySlotIndex).length<=2048);
// Expired slots can be reused without accumulating duplicate slot entries.
now+=61000;p.polyTick(now);for(let pos=0;pos<10000;pos++)request(0,pos);
assert.ok(p.polySlots.length<=2048);assert.ok(Object.keys(p.polySlotIndex).length<=2048);
players[0].con.isConnected=()=>false;players.splice(1,1);p.polyTick(now);
assert.equal(p.polyStates.c2,undefined);
loads[0]();assert.equal(Object.keys(p.polyTargets).length,0);
vm.runInContext(source,ctx);assert.equal(filters.length,1);assert.equal(ticks.length,1);assert.equal(menus.length,1);assert.equal(loads.length,1);
"""
        result=subprocess.run(['node','-e',harness],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':
    unittest.main()
