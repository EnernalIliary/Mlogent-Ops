import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mlogent_ops.world_adaptive_policy import INSTALL_JS
from mlogent_ops.world_bandwidth_controller import outbound_peer


class AdaptivePolicyTests(unittest.TestCase):
    def test_resource_headroom_pressure_hysteresis_and_stale_budget(self):
        script=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const player={con:{address:'a',hashCode:()=>1}};
const p={},ctx={_mcpSnapshotPolicy:p,Groups:{player:{size:()=>1,index:()=>player}},Vars:{state:{rules:{pvp:false}}}};
vm.createContext(ctx);vm.runInContext(JSON.parse(require('node:fs').readFileSync(0,'utf8')),ctx);
p.adaptiveEnabled=true;let now=100000;
const healthy={cpuRatio:.3,hostCpuRatio:.4,availableKB:400000,cpuBudgetCores:1};
function feed(sample,max=17){p.adaptiveFrame.gaps=Array(120).fill(17);p.adaptiveFrame.gaps.push(max);p.adaptiveFeedback({a:50000},now);p.adaptiveResourceFeedback(sample,now);now+=2000;}
assert.equal(p.adaptiveResourceTier(now),1);
for(let i=0;i<15;i++)feed(healthy);assert.equal(p.adaptiveResource.tier,1);
for(let i=0;i<3;i++)feed(healthy);assert.equal(p.adaptiveResource.tier,0);
assert.equal(p.adaptiveCadence(player,now,false).interval,100);
assert.equal(p.adaptiveControlledInterval(now),100);
// One spike cannot lower quality immediately. Sustained load degrades gradually.
feed({...healthy,cpuRatio:.95});assert.equal(p.adaptiveResource.tier,0);
for(let i=0;i<20;i++)feed({...healthy,cpuRatio:.95});
assert.equal(p.adaptiveResource.tier,3);assert.equal(p.adaptiveCadence(player,now,false).interval,300);
assert.equal(p.adaptiveControlledInterval(now),200);
for(let i=0;i<12;i++)feed(healthy);assert.equal(p.adaptiveResource.tier,3);
for(let i=0;i<50;i++)feed(healthy);assert.equal(p.adaptiveResource.tier,0);
// Invalid samples cannot refresh health, and stale telemetry loses the boost.
const at=p.adaptiveResource.at;p.adaptiveResourceFeedback({cpuRatio:NaN},now);assert.equal(p.adaptiveResource.at,at);
assert.equal(p.adaptiveResourceTier(now+11000),1);
p.adaptiveFeedback({a:50000},now+11000);assert.equal(p.adaptiveCadence(player,now+11000,false).interval,200);
feed({...healthy,availableKB:80000});assert.ok(p.adaptiveResource.tier>=1);
ctx.Vars.state.rules.pvp=true;assert.equal(p.adaptiveControlledInterval(now),100);
'''
        result=subprocess.run(['node','-e',script],input=json.dumps(INSTALL_JS),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_receiver_isolation_hysteresis_limits_stale_and_nat(self):
        script = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const players=[{con:{address:'a',hashCode:()=>1}},{con:{address:'b',hashCode:()=>2}}];
const p={},ctx={_mcpSnapshotPolicy:p,Groups:{player:{size:()=>players.length,index:i=>players[i]}},Vars:{state:{rules:{pvp:false}}}};
vm.createContext(ctx);vm.runInContext(JSON.parse(require('node:fs').readFileSync(0,'utf8')),ctx);
p.adaptiveEnabled=true;let now=100000;
for(let i=0;i<31;i++){p.adaptiveFeedback({a:400000,b:100000},now);now+=2000;}
assert.equal(p.adaptiveClients.c1.level,3);assert.equal(p.adaptiveClients.c2.level,0);
assert.equal(p.adaptiveCadence(players[0],now,false).interval,400);
assert.equal(p.adaptiveCadence(players[0],now,true).interval,500);
assert.equal(p.adaptiveCadence(players[1],now,false).interval,200);
assert.equal(p.adaptiveCadence(players[0],now+11000,false),null);
// A transient low reading never immediately recovers all levels.
p.adaptiveFeedback({a:0,b:0},now);assert.equal(p.adaptiveClients.c1.level,3);
for(let i=0;i<70;i++){now+=2000;p.adaptiveFeedback({a:40000,b:40000},now);}
assert.equal(p.adaptiveClients.c1.level,0);
// Shared IP is explicitly reported and its rate divided, never duplicated.
players[1].con.address='a';p.adaptiveFeedback({a:180000},now);
assert.equal(p.adaptiveClients.c1.measuredBps,90000);
assert.equal(p.adaptiveClients.c2.sharedAddress,2);
players.pop();p.adaptiveFeedback({a:100000},now);assert.equal(p.adaptiveClients.c2,undefined);
ctx.Vars.state.rules.pvp=true;assert.equal(p.adaptiveCadence(players[0],now,false),null);
"""
        result = subprocess.run(['node','-e',script], input=json.dumps(INSTALL_JS),
                                text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_outbound_game_packet_only(self):
        packet = bytearray(42)
        packet[12:14]=b'\x08\x00';packet[14]=0x45
        packet[16:18]=(28).to_bytes(2,'big');packet[23]=17
        packet[30:34]=socket.inet_aton('192.0.2.7')
        packet[34:36]=(6567).to_bytes(2,'big');packet[36:38]=(30000).to_bytes(2,'big')
        outgoing = getattr(socket,'PACKET_OUTGOING',4)
        # Windows lacks AF_PACKET constants; patch only this platform value.
        from unittest.mock import patch
        with patch.object(socket,'PACKET_OUTGOING',outgoing,create=True):
            self.assertEqual(outbound_peer(packet,('eth0',0,outgoing)),('192.0.2.7',28))
            self.assertIsNone(outbound_peer(packet,('eth0',0,0)))
            packet[34:36]=(8765).to_bytes(2,'big')
            self.assertIsNone(outbound_peer(packet,('eth0',0,outgoing)))


if __name__ == '__main__':
    unittest.main()
