"""Per-receiver cadence controller driven by measured public game traffic."""

INSTALL_JS = r"""
(function(){
 var mlogentAdaptivePolicyRef=this._mcpSnapshotPolicy;
 mlogentAdaptivePolicyRef.adaptiveEnabled=false;mlogentAdaptivePolicyRef.adaptiveTargetBps=200000;mlogentAdaptivePolicyRef.adaptiveError=null;
 mlogentAdaptivePolicyRef.adaptiveFeedbackAt=0;mlogentAdaptivePolicyRef.adaptiveClients={};
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
  var intervals=fullView?[300,350,400,500]:[200,250,300,400];
  var interval=intervals[c.level];
  if(c.interval!==interval||c.nextEntity===undefined){c.nextEntity=c.lastEntity?c.lastEntity+interval:now;}
  c.interval=interval;return c;
 };
})();
"""
