import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_i18n import INSTALL_JS, MESSAGES

class I18nTests(unittest.TestCase):
    def test_catalog_and_player_language_are_independent(self):
        for key,pair in MESSAGES.items():
            self.assertEqual(len(pair),2,key)
            self.assertTrue(all(isinstance(x,str) and x for x in pair),key)
        script=r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const saved={},commands={},messages=[];
const ctx={JavaAdapter:function(t,o){return o;},Packages:{arc:{util:{CommandHandler$CommandRunner:{}}}},
Core:{settings:{getString:(k,d)=>saved[k]||d,put:(k,v)=>saved[k]=v,remove:k=>delete saved[k],manualSave(){}}},
Vars:{netServer:{clientCommands:{removeCommand(){},register:(name,args,desc,runner)=>commands[name]=runner}}}};
vm.createContext(ctx);vm.runInContext(source,ctx);
const en={locale:'en_US',uuid:()=> 'english',sendMessage:m=>messages.push(m)},zh={locale:'zh_CN',uuid:()=> 'chinese',sendMessage:m=>messages.push(m)};
const i=ctx._mlogentI18n;
assert.equal(i.language(en),'en');assert.equal(i.language(zh),'zh');
assert.equal(i.language({locale:'ru',uuid:()=> 'other'}),'en');
assert.ok(i.text(en,'poly.prompt').includes('30 seconds'));
assert.ok(!i.text(en,'poly.kick',{reason:'timeout'}).includes('{reason}'));
assert.ok(i.text(zh,'poly.prompt').includes('30'));
commands.language.accept(['zh'],en);assert.equal(i.language(en),'zh');assert.equal(i.language(zh),'zh');
vm.runInContext(source,ctx);assert.equal(ctx._mlogentI18n.language(en),'zh');
commands.language.accept(['auto'],en);assert.equal(i.language(en),'en');
assert.equal(Object.keys(saved).length,0);
"""
        r=subprocess.run(['node','-e',script],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':unittest.main()
