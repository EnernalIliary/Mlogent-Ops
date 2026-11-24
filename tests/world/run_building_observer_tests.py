"""Exercise byte comparisons, identity, rate/memory bounds and fail-open sampling."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_building_observer import INSTALL_JS
from mlogent_ops.world_network_policy import startup_script
import tempfile


class BuildingObserverTests(unittest.TestCase):
    def test_profile_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'profile.json'
            path.write_text(json.dumps({'mode':'experimental'}))
            self.assertNotIn('buildingObservationEnabled=true;', startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','buildingObservation':True}))
            self.assertIn('buildingObservationEnabled=true;', startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','buildingDedup':True}))
            self.assertIn('buildingDedupEnabled=true;', startup_script(path))
            path.write_text(json.dumps({'mode':'native','buildingDedup':True}))
            self.assertNotIn('buildingDedupEnabled=true;', startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','enemyBuildingsInViewOnly':True}))
            self.assertIn('interestEnemyBuildingsInViewOnly=true;', startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','adaptiveBandwidth':True}))
            self.assertIn('adaptiveEnabled=true;',startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','afkVerification':True}))
            self.assertIn('afkEnabled=true;',startup_script(path))
            path.write_text(json.dumps({'mode':'native','polyVerification':True}))
            self.assertIn('polyEnabled=true;',startup_script(path))
            path.write_text(json.dumps({'mode':'experimental','rotatingNotices':True}))
            self.assertIn('_mlogentNotices.enabled=true;',startup_script(path))

    def test_dedup_refresh_force_identity_and_unsampled_changes(self):
        harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=10000;
const p={},ctx={_mcpSnapshotPolicy:p,java:{lang:{System:{nanoTime:()=>now*1e6}},
 util:{Arrays:{copyOfRange:(a,s,e)=>a.slice(s,e),equals:(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i])}}}};
vm.createContext(ctx);vm.runInContext(JSON.parse(require('node:fs').readFileSync(0,'utf8')),ctx);
p.buildingObservationEnabled=true;p.buildingDedupEnabled=true;
const state={},b={id:1,block:{id:5}};
const sample=(bytes=[1],force=false,s=state,build=b)=>p.observeBuildingRecord(s,'b1',build,bytes,0,bytes.length,now,force);
assert.equal(sample(),false);now+=6000;assert.equal(sample(),true);
now+=6000;assert.equal(sample(),true);now+=6000;assert.equal(sample(),true);
now+=6000;assert.equal(sample(),false); // periodic full resend repairs a lost UDP packet
now+=1000;assert.equal(sample([1],true),false); // reveal / viewport entry / priority lane
now+=1000;assert.equal(sample([2]),false);assert.equal(sample([1]),false); // A -> B -> A
assert.equal(sample([1],false,{}),false); // new receiver
assert.equal(sample([1],false,state,{id:2,block:{id:5}}),false); // replacement
// Exhaust comparisons, then send an unobserved change. The old A baseline
// must not suppress a later return to A while the client still holds B.
now+=1000;for(let i=0;i<8;i++)sample();
assert.equal(sample([9]),false);now+=1000;assert.equal(sample(),false);
assert.equal(sample(new Array(2050).fill(9)),false);now+=1000;assert.equal(sample(),false);
p.resetBuildingObservation();now+=1000;assert.equal(sample(),false);
now-=5000;assert.equal(sample(),false); // clock rollback never suppresses refresh
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_bytes_bounds_and_fail_open(self):
        harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=10000,fail=false;
const p={},ctx={_mcpSnapshotPolicy:p,java:{lang:{System:{nanoTime:()=>now*1e6}},
 util:{Arrays:{copyOfRange:(a,s,e)=>{if(fail)throw Error('sample failure');return a.slice(s,e);},
 equals:(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i])}}}};
vm.createContext(ctx);vm.runInContext(JSON.parse(require('node:fs').readFileSync(0,'utf8')),ctx);
const state={},build={id:1,block:{id:5}};
const sample=(s=state,b=build,a=[8,1,2,9])=>p.observeBuildingRecord(s,'b1',b,a,1,a.length-1,now);
sample();assert.equal(p.buildingObservation.samples,0);
p.buildingObservationEnabled=true;
sample();sample();assert.equal(p.buildingObservation.repeated,1);
sample(state,build,[8,1,3,9]);assert.equal(p.buildingObservation.repeated,1);
sample({},build);sample(state,{id:2,block:{id:5}});
assert.equal(p.buildingObservation.comparable,2);
for(let i=0;i<20;i++)sample();assert.equal(p.buildingObservation.samples,8);
assert.ok(p.buildingObservation.rateLimited>0);
now+=1000;sample(state,build,new Array(2052).fill(0));assert.equal(p.buildingObservation.oversize,1);
for(let i=0;i<600;i++){now+=1000;sample({},build,new Array(2050).fill(1));}
assert.ok(p.buildingObservation.cacheBytes<=131072);
p.resetBuildingObservation();assert.equal(p.buildingObservation.cacheBytes,0);
now+=1000;sample();assert.ok(p.buildingObservation.cacheBytes>0);
fail=true;now+=1000;assert.doesNotThrow(()=>sample());
assert.equal(p.buildingObservationEnabled,false);assert.match(p.buildingObservation.error,/sample failure/);
"""
        result = subprocess.run(['node', '-e', harness], input=json.dumps(INSTALL_JS),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
