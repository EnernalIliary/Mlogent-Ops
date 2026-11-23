"""Execute the installed policy with deterministic game/transport substitutes."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_network_policy import CORE_INSTALL_JS as INSTALL_JS
from mlogent_ops.world_network_policy import startup_script


HARNESS = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
let now=1000, paused=false, interval=200, sent=[], fail=false;
class Seq {
 constructor(){this.items=[];}
 get size(){return this.items.length;}
 add(v){this.items.push(v);}
 get(i){return this.items[i];}
 isEmpty(){return this.items.length===0;}
}
class IntSet {constructor(){this.ids=new Set();}add(id){if(this.ids.has(id))return false;this.ids.add(id);return true;}}
const events=[];
const unit=(id,hidden=false)=>({id,dead:false,isAdded:()=>true,isSyncHidden:t=>hidden&&t==='enemy'});
const a=unit(1), b=unit(2,true);
const player=(name,u,team)=>({name,con:{hasConnected:true,isConnected:()=>true},dead:()=>false,unit:()=>u,team:()=>team});
const owners=[player('a',a,'ally'),player('b',b,'ally'),player('enemy',a,'enemy')];
const ctx={
 sb:{append(){}},java:{lang:{Integer:Number,System:{currentTimeMillis:()=>now}}},
 Packages:{arc:{struct:{Seq,IntSet},util:{Log:{info(){},err(){}}}},mindustry:{
  net:{Administration:{Config:{snapshotInterval:{num:()=>interval,set:x=>{interval=Number(x);}}}}},
  game:{EventType:{WorldLoadEvent:'load',Trigger:{update:'update'}}}}},
 Events:{on:(t,fn)=>events.push(fn),run:(t,fn)=>events.push(fn)},
 Groups:{player:{size:()=>owners.length,index:i=>owners[i]}},
 Vars:{state:{rules:{pvp:false},isGame:()=>true,isPaused:()=>paused},netServer:{
  writeCustomEntitySnapshot:(p,units)=>{if(fail)throw Error('transport failure');sent.push([p.name,units.items.map(x=>x.id)]);}}}
};
vm.createContext(ctx);vm.runInContext(source,ctx);
const p=ctx._mcpSnapshotPolicy;
assert.equal(interval,300);
assert.equal(p.controlledInterval,100);
ctx.Vars.state.rules.pvp=true;p.apply();assert.equal(interval,200);
assert.equal(p.controlledInterval,100);
ctx.Vars.state.rules.pvp=false;p.apply();assert.equal(interval,300);
assert.equal(p.controlledInterval,100);
p.supplement();
assert.deepEqual(sent,[['a',[1,2]],['b',[1,2]],['enemy',[1]]]);
assert.equal(p.controlledEntities,5); // shared unit deduplicated, hidden enemy excluded
sent=[];now+=50;p.supplement();assert.equal(sent.length,0);
now+=50;p.supplement();assert.equal(sent.length,3);
sent=[];paused=true;now+=100;p.supplement();assert.equal(sent.length,0);paused=false;
p.controlledEnabled=false;now+=100;p.supplement();assert.equal(sent.length,0);p.controlledEnabled=true;
owners[0].con.hasConnected=false;owners[1].dead=()=>true;
now+=100;p.supplement();assert.deepEqual(sent,[['b',[1]],['enemy',[1]]]);
sent=[];owners[2].unit=()=>null;now+=300;p.supplement();assert.equal(sent.length,0);
owners[2].unit=()=>a;fail=true;now+=300;p.supplement();
assert.equal(p.controlledEnabled,false);assert.match(p.controlledError,/transport failure/);
const count=events.length;vm.runInContext(source,ctx);assert.equal(events.length,count);
assert.equal(p.controlledEnabled,false); // reinstall never overrides operator disable/error
// In AOI mode ALL controlled units retain the supplement outside the camera.
p.interestEnabled=true;p.view=()=>({});p.inView=(v,u)=>false;
owners[0].con.hasConnected=true;
const check=new Seq();check.add(a);check.add(b);
assert.deepEqual(p.visibleUnits(owners[0],check).items,[a,b]);
assert.deepEqual(p.visibleUnits(owners[2],check).items,[a]); // fog-hidden enemy remains excluded
assert.equal(p.controlledOutsideView,true);
p.interestEnabled=false;
assert.deepEqual(p.visibleUnits(owners[0],check).items,[a,b]);
// A missing/partially loaded policy must never escape an update callback.
ctx._mcpSnapshotPolicy={};for(const event of events)assert.doesNotThrow(()=>event());
ctx._mcpSnapshotPolicy=p;
const savedSupplement=p.supplement;
p.supplement=()=>{throw Error('callback regression');};
events[events.length-1]();assert.equal(p.controlledEnabled,false);
assert.match(p.controlledError,/callback regression/);p.supplement=savedSupplement;
console.log('cadence, selection, deduplication, visibility, pause, disable, error and reinstall checks passed');
"""


class NetworkPolicyTests(unittest.TestCase):
    def test_owned_profile_survives_wake_and_bad_profile_preserves_environment_default(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'MLOG_WORLD_VIEWPORT_SYNC': 'wrapper'}):
            path = Path(directory)/'profile.json'
            path.write_text(json.dumps({'mode':'experimental','eventPath':'/owned/out/fallback.json'}))
            source = startup_script(path)
            self.assertIn('C-stagger-buckets-experimental', source)
            self.assertIn('/owned/out/fallback.json', source)
            self.assertIn('interestHostHoldMs=10000', source)
            path.write_text('{broken')
            self.assertIn('B-wrapper-only', startup_script(path))
            path.write_text(json.dumps({'mode':'native'}))
            self.assertIn('A-native', startup_script(path))

    def test_policy_behavior(self):
        self.assertIsNotNone(shutil.which('node'), 'Node.js is required for policy tests')
        result = subprocess.run(['node', '-e', HARNESS], input=json.dumps(INSTALL_JS),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
