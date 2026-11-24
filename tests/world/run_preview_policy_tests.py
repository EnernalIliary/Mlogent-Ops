import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_preview_policy import INSTALL_JS


class PreviewPolicyTests(unittest.TestCase):
    def test_limit_receive_assembly_and_committed_list_only(self):
        script = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const seq=n=>({size:n,truncate(n){this.size=Math.min(this.size,n);}});
const players=[0,500,501,1000].map(n=>({
 previewPlansAssembling:seq(n),previewPlansCurrent:seq(n),
 previewPlansDirty:false,buildQueue:seq(2000)}));
const ctx={_mcpSnapshotPolicy:{},Vars:{state:{isGame:()=>true}},
 Groups:{player:{size:()=>players.length,index:i=>players[i]}}};
vm.createContext(ctx);
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
vm.runInContext(source,ctx);const p=ctx._mcpSnapshotPolicy;
p.limitPreviewPlans();
assert.deepEqual(players.map(x=>x.previewPlansCurrent.size),[0,500,500,500]);
assert.deepEqual(players.map(x=>x.previewPlansAssembling.size),[0,500,500,500]);
assert.deepEqual(players.map(x=>x.previewPlansDirty),[false,false,true,true]);
assert.equal(p.previewPlansTrimmed,1002);
assert.ok(players.every(x=>x.buildQueue.size===2000));
// Additional chunks in the same group are capped again before native send.
players[2].previewPlansAssembling.size+=75;p.limitPreviewPlans();
assert.equal(players[2].previewPlansAssembling.size,500);
vm.runInContext(source,ctx);assert.equal(p.previewPlansTrimmed,1077);
// Clearing a cancelled preview must still reach the engine unchanged.
players[2].previewPlansCurrent.size=0;p.limitPreviewPlans();
assert.equal(players[2].previewPlansCurrent.size,0);
ctx.Vars.state.isGame=()=>false;assert.doesNotThrow(()=>p.limitPreviewPlans());
"""
        result = subprocess.run(['node', '-e', script], input=json.dumps(INSTALL_JS),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
