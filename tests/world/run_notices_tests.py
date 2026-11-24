import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_notices import INSTALL_JS


class NoticesTests(unittest.TestCase):
    def test_rotation_single_message_idle_no_burst_and_idempotence(self):
        script=r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let now=1000,online=true;const sent=[],callbacks=[];
const ctx={_mcpSnapshotPolicy:{afkEnabled:true,polyEnabled:true,interestEnabled:true},
 Groups:{player:{size:()=>online?1:0,index:()=>({locale:'en',con:{hasConnected:true,isConnected:()=>true},sendMessage:m=>sent.push(m)})}},
 Vars:{state:{isGame:()=>true,rules:{pvp:false}}},java:{lang:{System:{currentTimeMillis:()=>now}}},
 Events:{run:(e,f)=>callbacks.push(f)},Packages:{mindustry:{game:{EventType:{Trigger:{update:'update'}}},gen:{Call:{sendMessage:m=>sent.push(m)}}}}};
vm.createContext(ctx);const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));vm.runInContext(source,ctx);
const n=ctx._mlogentNotices;n.enabled=true;n.tick(now);assert.equal(sent.length,0);
for(let i=0;i<3;i++){now+=300000;n.tick(now);assert.equal(sent.length,i+1);}
assert.ok(sent[0].includes('AFK'));assert.ok(sent[1].includes('polyAI'));assert.ok(sent[2].includes('/mcp'));
assert.ok(sent[0].includes('Inactivity'));assert.ok(sent[1].includes('30 seconds'));
now+=3000000;n.tick(now);assert.equal(sent.length,4);n.tick(now);assert.equal(sent.length,4);
online=false;now+=600000;n.tick(now);online=true;n.tick(now);assert.equal(sent.length,4);
now+=300000;n.tick(now);assert.equal(sent.length,5);
ctx._mcpSnapshotPolicy.afkEnabled=false;ctx._mcpSnapshotPolicy.polyEnabled=false;
now+=300000;n.tick(now);assert.equal(sent.length,6);assert.ok(sent.at(-1).includes('/mcp'));
vm.runInContext(source,ctx);assert.equal(callbacks.length,1);
// Generic variables used by packet scripts cannot corrupt retained closures.
ctx.p={};ctx.root={};n.enabled=true;now+=300000;assert.doesNotThrow(()=>callbacks[0]());
"""
        r=subprocess.run(['node','-e',script],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)


if __name__=='__main__':unittest.main()
