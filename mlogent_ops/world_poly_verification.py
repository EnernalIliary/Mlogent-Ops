"""Bounded cooperative-build request heuristic; challenge before kicking."""

INSTALL_JS = r"""
(function(){
 var mlogentPolyRootRef=this,mlogentPolyPolicyRef=this._mcpSnapshotPolicy;
 mlogentPolyPolicyRef.polyEnabled=false;mlogentPolyPolicyRef.polyWindowMs=60000;mlogentPolyPolicyRef.polyThreshold=5;mlogentPolyPolicyRef.polyAnswerMs=30000;
 mlogentPolyPolicyRef.polyGraceMs=300000;mlogentPolyPolicyRef.polyStates={};mlogentPolyPolicyRef.polyTargets={};mlogentPolyPolicyRef.polySlots=[];mlogentPolyPolicyRef.polySlotIndex={};mlogentPolyPolicyRef.polyCursor=0;
 mlogentPolyPolicyRef.polyError=null;mlogentPolyPolicyRef.polyStats={overlaps:0,challenges:0,passed:0,kicked:0,menuErrors:0};
 mlogentPolyPolicyRef.polyAvailable=function(){return mlogentPolyPolicyRef.polyEnabled;};
 mlogentPolyPolicyRef.polyState=function(player){
  var key='c'+player.con.hashCode(),s=mlogentPolyPolicyRef.polyStates[key];
  if(!s)s=mlogentPolyPolicyRef.polyStates[key]={mode:'watch',hits:[],graceUntil:0};
  return s;
 };
 mlogentPolyPolicyRef.polyPending=function(player){
  var s=player&&player.con&&mlogentPolyPolicyRef.polyStates['c'+player.con.hashCode()];
  return mlogentPolyPolicyRef.polyEnabled&&s&&s.mode==='pending';
 };
 mlogentPolyPolicyRef.polyFail=function(player,s,reason){
  if(s.mode!=='pending')return;
  s.mode='kicked';s.answer=null;s.reason=reason;
  player.kick(mlogentPolyRootRef._mlogentI18n.text(player,'poly.kick',{reason:mlogentPolyRootRef._mlogentI18n.text(player,'poly.'+reason)}),0);
  mlogentPolyPolicyRef.polyStats.kicked++;
 };
 mlogentPolyPolicyRef.polyAsk=function(player,now){
  var s=mlogentPolyPolicyRef.polyState(player);if(s.mode==='pending'||s.mode==='kicked'||now<s.graceUntil)return;
  var a=3+Math.floor(Math.random()*7),b=1+Math.floor(Math.random()*8),answer=a+b;
  var correct=Math.floor(Math.random()*3);
  var rows=java.lang.reflect.Array.newInstance(java.lang.Class.forName('[Ljava.lang.String;'),1);
  var row=java.lang.reflect.Array.newInstance(java.lang.String,3);
  for(var i=0;i<3;i++)row[i]=String(answer+(i-correct)*3);rows[0]=row;
  try{
   Packages.mindustry.gen.Call.menu(player.con,mlogentPolyRootRef._mlogentPolyMenuId,mlogentPolyRootRef._mlogentI18n.text(player,'poly.title'),
    mlogentPolyRootRef._mlogentI18n.text(player,'poly.prompt')+'\n\n'+a+' + '+b+' = ?',rows);
  }catch(error){mlogentPolyPolicyRef.polyError=String(error);mlogentPolyPolicyRef.polyStats.menuErrors++;s.hits=[];s.graceUntil=now+60000;return;}
  s.mode='pending';s.answer=correct;s.deadline=now+mlogentPolyPolicyRef.polyAnswerMs;mlogentPolyPolicyRef.polyStats.challenges++;
 };
 mlogentPolyPolicyRef.polyAnswer=function(player,option){
  if(!mlogentPolyPolicyRef.polyAvailable()||!player||!player.con)return;
  var s=mlogentPolyPolicyRef.polyStates['c'+player.con.hashCode()],now=java.lang.System.currentTimeMillis();
  if(!s||s.mode!=='pending')return;
  if(now>=s.deadline){mlogentPolyPolicyRef.polyFail(player,s,'timeout');return;}
  if(option!==s.answer){mlogentPolyPolicyRef.polyFail(player,s,option<0?'closed':'wrong-answer');return;}
  s.mode='watch';s.answer=null;s.hits=[];s.graceUntil=now+mlogentPolyPolicyRef.polyGraceMs;mlogentPolyPolicyRef.polyStats.passed++;
  // A successful human-interaction challenge also satisfies a pending AFK check.
  var afk=mlogentPolyPolicyRef.afkStates&&mlogentPolyPolicyRef.afkStates['c'+player.con.hashCode()];
  if(afk){afk.mode='active';afk.limited=false;afk.awaiting=false;afk.lastActivity=now;afk.reason='poly-verified';}
  player.sendMessage(mlogentPolyRootRef._mlogentI18n.text(player,'poly.passed'));
 };
 mlogentPolyPolicyRef.polyObserve=function(action,now){
  if(!mlogentPolyPolicyRef.polyAvailable()||String(action.type)!=='placeBlock'||!action.player||!action.player.con||!action.tile||!action.block)return;
  var player=action.player,who='c'+player.con.hashCode(),team=String(player.team());
  // Never retain pooled Administration actions, tiles or buildings. Only
  // bounded connection references are retained and cleaned after disconnect.
  var target=team+':'+action.tile.pos()+':'+action.block.id+':'+action.rotation;
  var old=mlogentPolyPolicyRef.polyTargets[target],s=mlogentPolyPolicyRef.polyState(player);
  if(!old||now<old.at||now-old.at>mlogentPolyPolicyRef.polyWindowMs||!old.con.isConnected()){
   if(mlogentPolyPolicyRef.polySlotIndex[target]===undefined){
    var slot;
    if(mlogentPolyPolicyRef.polySlots.length<2048){slot=mlogentPolyPolicyRef.polySlots.length;mlogentPolyPolicyRef.polySlots.push(target);}
    else{slot=mlogentPolyPolicyRef.polyCursor;var victim=mlogentPolyPolicyRef.polySlots[slot];delete mlogentPolyPolicyRef.polyTargets[victim];delete mlogentPolyPolicyRef.polySlotIndex[victim];mlogentPolyPolicyRef.polySlots[slot]=target;mlogentPolyPolicyRef.polyCursor=(mlogentPolyPolicyRef.polyCursor+1)%2048;}
    mlogentPolyPolicyRef.polySlotIndex[target]=slot;
   }
   mlogentPolyPolicyRef.polyTargets[target]={owner:who,con:player.con,at:now,team:team,configPresent:action.config!=null};return;
  }
  if(old.owner===who){old.at=now;return;}
  if(s.mode!=='watch'||now<s.graceUntil)return;
  var hits=[];
  for(var i=0;i<s.hits.length;i++)if(now>=s.hits[i].at&&now-s.hits[i].at<=mlogentPolyPolicyRef.polyWindowMs)hits.push(s.hits[i]);
  s.hits=hits;
  for(var i=0;i<hits.length;i++)if(hits[i].target===target)return;
  // Only a subsequent request at a DISTINCT teammate target counts. Repeated
  // snapshots of one plan do not produce five hits or accuse the first sender.
  s.hits.push({target:target,at:now,owner:old.owner,
   missingConfig:old.configPresent&&action.config==null});
  mlogentPolyPolicyRef.polyStats.overlaps++;
  if(s.hits.length>=mlogentPolyPolicyRef.polyThreshold)mlogentPolyPolicyRef.polyAsk(player,now);
 };
 mlogentPolyPolicyRef.polyTick=function(now){
  if(!mlogentPolyPolicyRef.polyAvailable()){mlogentPolyPolicyRef.polyStates={};mlogentPolyPolicyRef.polyTargets={};mlogentPolyPolicyRef.polySlots=[];mlogentPolyPolicyRef.polySlotIndex={};mlogentPolyPolicyRef.polyCursor=0;return;}
  var active={};
  for(var i=0;i<Groups.player.size();i++){
   var player=Groups.player.index(i),con=player.con;
   if(!con||!con.hasConnected||!con.isConnected())continue;
   var key='c'+con.hashCode();active[key]=true;var s=mlogentPolyPolicyRef.polyStates[key];
   if(s&&s.mode==='pending'&&now>=s.deadline)mlogentPolyPolicyRef.polyFail(player,s,'timeout');
  }
  for(var key in mlogentPolyPolicyRef.polyStates)if(!active[key])delete mlogentPolyPolicyRef.polyStates[key];
  // Bounded cleanup; retain no disconnected connection references indefinitely.
  for(var i=0;i<32&&mlogentPolyPolicyRef.polySlots.length;i++){
   var slot=mlogentPolyPolicyRef.polyCursor++%mlogentPolyPolicyRef.polySlots.length,key=mlogentPolyPolicyRef.polySlots[slot],t=mlogentPolyPolicyRef.polyTargets[key];
   if(t&&(now<t.at||now-t.at>mlogentPolyPolicyRef.polyWindowMs||!active[t.owner]))delete mlogentPolyPolicyRef.polyTargets[key];
  }
  mlogentPolyPolicyRef.polyCursor=mlogentPolyPolicyRef.polySlots.length?mlogentPolyPolicyRef.polyCursor%mlogentPolyPolicyRef.polySlots.length:0;
 };
 if(mlogentPolyRootRef._mlogentPolyMenuId===undefined){
  mlogentPolyRootRef._mlogentPolyMenuId=Packages.mindustry.ui.Menus.registerMenu(
   new JavaAdapter(Packages.mindustry.ui.Menus$MenuListener,{get:function(player,option){
    var current=mlogentPolyRootRef._mcpSnapshotPolicy;
    try{if(current&&current.polyAnswer)current.polyAnswer(player,Number(option));}
    catch(error){if(current){current.polyEnabled=false;current.polyError=String(error);}}
   }}));
 }
 if(!mlogentPolyRootRef._mlogentPolyHooks){
  Vars.netServer.admins.addActionFilter(new JavaAdapter(Packages.mindustry.net.Administration$ActionFilter,{allow:function(action){
   var current=mlogentPolyRootRef._mcpSnapshotPolicy;
   try{if(current&&current.polyObserve)current.polyObserve(action,java.lang.System.currentTimeMillis());}
   catch(error){if(current){current.polyEnabled=false;current.polyError=String(error);}}
   return true;
  }}));
  var last=0;
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var now=java.lang.System.currentTimeMillis();if(now-last<1000)return;last=now;
   var current=mlogentPolyRootRef._mcpSnapshotPolicy;
   try{if(current&&current.polyTick)current.polyTick(now);}
   catch(error){if(current){current.polyEnabled=false;current.polyError=String(error);}}
  });
  Events.on(Packages.mindustry.game.EventType.WorldLoadEvent,function(){
   var current=mlogentPolyRootRef._mcpSnapshotPolicy;
   if(current){current.polyStates={};current.polyTargets={};current.polySlots=[];current.polySlotIndex={};current.polyCursor=0;}
  });
  mlogentPolyRootRef._mlogentPolyHooks=true;
 }
})();
"""

from .world_i18n import INSTALL_JS as I18N_INSTALL_JS
INSTALL_JS = I18N_INSTALL_JS + INSTALL_JS
