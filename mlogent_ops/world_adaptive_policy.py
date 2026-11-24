"""Per-receiver cadence controller driven by measured public game traffic."""

INSTALL_JS = r"""
(function(){
 var mlogentAdaptivePolicyRef=this._mcpSnapshotPolicy;
 mlogentAdaptivePolicyRef.adaptiveEnabled=false;mlogentAdaptivePolicyRef.adaptiveTargetBps=200000;mlogentAdaptivePolicyRef.adaptiveError=null;
 mlogentAdaptivePolicyRef.adaptiveFeedbackAt=0;mlogentAdaptivePolicyRef.adaptiveClients={};
 mlogentAdaptivePolicyRef.adaptiveResource={tier:1,at:0,high:0,healthySince:0,lastChange:0,reason:'awaiting-resource-sample'};
 mlogentAdaptivePolicyRef.adaptiveFrame={last:0,gaps:[]};
 mlogentAdaptivePolicyRef.adaptiveFrameTick=function(now){
  var f=mlogentAdaptivePolicyRef.adaptiveFrame;
  if(f.last&&now>=f.last){f.gaps.push(now-f.last);if(f.gaps.length>240)f.gaps.shift();}
  f.last=now;
 };
 mlogentAdaptivePolicyRef.adaptiveResourceFeedback=function(sample,now){
  var r=mlogentAdaptivePolicyRef.adaptiveResource;
  if(!sample||!isFinite(sample.cpuRatio)||sample.cpuRatio<0||!isFinite(sample.hostCpuRatio)||sample.hostCpuRatio<0||
     !isFinite(sample.availableKB)||sample.availableKB<=0||!isFinite(sample.cpuBudgetCores)||sample.cpuBudgetCores<=0)return;
  var gaps=mlogentAdaptivePolicyRef.adaptiveFrame.gaps.slice().sort(function(a,b){return a-b;});
  mlogentAdaptivePolicyRef.adaptiveFrame.gaps=[];
  var p95=gaps.length?gaps[Math.floor((gaps.length-1)*.95)]:0,max=gaps.length?gaps[gaps.length-1]:0;
  var memory=mlogentAdaptivePolicyRef.interestMemorySample,heap=memory&&memory.heapMax?memory.heapUsed/memory.heapMax:0;
  var critical=sample.availableKB<98304||heap>.90||max>=500;
  var pressured=critical||sample.cpuRatio>.85||sample.hostCpuRatio>.90||sample.availableKB<147456||heap>.82||p95>35||max>150;
  var healthy=sample.cpuRatio<.65&&sample.hostCpuRatio<.75&&sample.availableKB>=196608&&heap<.75&&p95<=22&&max<80&&gaps.length>=30;
  if(!r.at||now<r.at||now-r.at>10000){r.healthySince=0;r.high=0;if(r.tier<1)r.tier=1;}
  r.at=now;r.sample=sample;r.frameP95Ms=p95;r.frameMaxMs=max;r.heapRatio=heap;
  if(pressured){
   r.high++;r.healthySince=0;r.reason=critical?'critical-resource-pressure':'resource-pressure';
   if((critical||r.high>=3)&&now-r.lastChange>=10000){r.tier=Math.min(3,r.tier+1);r.lastChange=now;r.high=0;}
  }else{
   r.high=0;r.reason=healthy?'resource-headroom':'normal-resource-budget';
   if(healthy){if(!r.healthySince)r.healthySince=now;
    if(now-r.healthySince>=30000&&now-r.lastChange>=30000&&r.tier>0){r.tier--;r.lastChange=now;r.healthySince=now;}
   }else{r.healthySince=0;}
  }
 };
 mlogentAdaptivePolicyRef.adaptiveResourceTier=function(now){
  var r=mlogentAdaptivePolicyRef.adaptiveResource;
  return r.at&&now>=r.at&&now-r.at<=10000?r.tier:1;
 };
 mlogentAdaptivePolicyRef.adaptiveControlledInterval=function(now){
  if(!mlogentAdaptivePolicyRef.adaptiveEnabled||Vars.state.rules.pvp)return mlogentAdaptivePolicyRef.controlledInterval||100;
  return [100,100,150,200][mlogentAdaptivePolicyRef.adaptiveResourceTier(now)];
 };
 if(!this._mlogentAdaptiveFrameHook&&typeof Events!=='undefined'&&typeof Events.run==='function'&&Packages.mindustry.game.EventType.Trigger){
  var mlogentAdaptiveFrameRoot=this;
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var p=mlogentAdaptiveFrameRoot._mcpSnapshotPolicy;
   if(p&&p.adaptiveEnabled&&p.adaptiveFrameTick)p.adaptiveFrameTick(java.lang.System.currentTimeMillis());
  });
  this._mlogentAdaptiveFrameHook=true;
 }
 mlogentAdaptivePolicyRef.adaptiveFeedback=function(rates,now){
  var counts={};
  for(var i=0;i<Groups.player.size();i++){
   var player=Groups.player.index(i),ip=String(player.con.address);
   counts[ip]=(counts[ip]||0)+1;
  }
  var active={};
  for(var i=0;i<Groups.player.size();i++){
   var player=Groups.player.index(i),key='c'+player.con.hashCode(),ip=String(player.con.address);
   var c=mlogentAdaptivePolicyRef.adaptiveClients[key];
   if(!c)c=mlogentAdaptivePolicyRef.adaptiveClients[key]={level:0,ema:null,high:0,low:0,lastChange:now,joinedAt:now,lastEntity:0};
   active[key]=true;
   var measured=Number(rates[ip]||0)/counts[ip];
   c.sharedAddress=counts[ip];c.measuredBps=measured;
   c.ema=c.ema===null?measured:c.ema*0.8+measured*0.2;
   c.high=c.ema>mlogentAdaptivePolicyRef.adaptiveTargetBps*1.10?c.high+1:0;
   c.low=c.ema<mlogentAdaptivePolicyRef.adaptiveTargetBps*0.85?c.low+1:0;
   if(c.high>=3&&now-c.joinedAt>=20000&&now-c.lastChange>=10000&&c.level<3){c.level++;c.lastChange=now;c.high=0;}
   else if(c.low>=8&&now-c.lastChange>=20000&&c.level>0){c.level--;c.lastChange=now;c.low=0;}
  }
  for(var key in mlogentAdaptivePolicyRef.adaptiveClients)if(!active[key])delete mlogentAdaptivePolicyRef.adaptiveClients[key];
  mlogentAdaptivePolicyRef.adaptiveFeedbackAt=now;
 };
 mlogentAdaptivePolicyRef.adaptiveCadence=function(receiver,now,fullView){
  if(!mlogentAdaptivePolicyRef.adaptiveEnabled||Vars.state.rules.pvp)return null;
  var key='c'+receiver.con.hashCode(),c=mlogentAdaptivePolicyRef.adaptiveClients[key];
  // Missing/stale monitoring restores the ordinary C cadence. Never freeze.
  if(!c||now<mlogentAdaptivePolicyRef.adaptiveFeedbackAt||now-mlogentAdaptivePolicyRef.adaptiveFeedbackAt>10000)return null;
  var tier=mlogentAdaptivePolicyRef.adaptiveResourceTier(now);
  var intervals=fullView?[300,350,400,500]:[[100,150,200,300],[200,250,300,400],[250,300,400,500],[300,350,450,500]][tier];
  if(fullView&&tier>1)intervals=tier===2?[350,400,450,500]:[400,450,500,500];
  var interval=intervals[c.level];
  if(c.interval!==interval||c.nextEntity===undefined){c.nextEntity=c.lastEntity?c.lastEntity+interval:now;}
  c.interval=interval;return c;
 };
})();
"""
