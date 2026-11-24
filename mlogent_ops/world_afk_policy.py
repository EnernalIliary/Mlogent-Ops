"""Request-based AFK challenges and per-receiver low-frequency snapshots."""

INSTALL_JS = r"""
(function(){
 var mlogentAfkRootRef=this,mlogentAfkPolicyRef=this._mcpSnapshotPolicy;
 mlogentAfkPolicyRef.afkEnabled=false;mlogentAfkPolicyRef.afkIdleMs=180000;mlogentAfkPolicyRef.afkAnswerMs=30000;mlogentAfkPolicyRef.afkIntervalMs=1000;
 mlogentAfkPolicyRef.afkStates={};mlogentAfkPolicyRef.afkError=null;
 mlogentAfkPolicyRef.afkState=function(player,now){
  var key='c'+player.con.hashCode(),s=mlogentAfkPolicyRef.afkStates[key];
  if(!s)s=mlogentAfkPolicyRef.afkStates[key]={lastActivity:now,mode:'active',reason:'joined',lastEntity:0,lastPrompt:0};
  return s;
 };
 mlogentAfkPolicyRef.afkAvailable=function(){return mlogentAfkPolicyRef.afkEnabled&&mlogentAfkPolicyRef.interestEnabled&&!Vars.state.rules.pvp;};
 mlogentAfkPolicyRef.afkActivity=function(player,reason){
  if(!mlogentAfkPolicyRef.afkAvailable()||!player||!player.con)return;
  var now=java.lang.System.currentTimeMillis(),s=mlogentAfkPolicyRef.afkState(player,now);
  // Once challenged, requests (including scripted ones) cannot dismiss it.
  if(s.mode==='active'){s.lastActivity=now;s.reason=reason;}
 };
 mlogentAfkPolicyRef.afkFail=function(player,s,reason){
  s.mode='afk';s.limited=true;s.reason=reason;s.nextEntity=0;s.interval=mlogentAfkPolicyRef.afkIntervalMs;
  player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.limited'));
 };
 mlogentAfkPolicyRef.afkAsk=function(player,now){
  if(typeof mlogentAfkPolicyRef.polyPending==='function'&&mlogentAfkPolicyRef.polyPending(player))return;
  var s=mlogentAfkPolicyRef.afkState(player,now);
  if(s.mode==='pending'||now-s.lastPrompt<5000)return;
  var options=[mlogentAfkRootRef._mlogentI18n.text(player,'afk.here'),mlogentAfkRootRef._mlogentI18n.text(player,'afk.stay')];
  s.mode='pending';s.awaiting=true;s.deadline=now+mlogentAfkPolicyRef.afkAnswerMs;s.lastPrompt=now;
  try{
   var optionsType=java.lang.Class.forName('[Ljava.lang.String;');
   var rows=java.lang.reflect.Array.newInstance(optionsType,1);
   var row=java.lang.reflect.Array.newInstance(java.lang.String,2);
   for(var i=0;i<2;i++)row[i]=options[i];rows[0]=row;
   Packages.mindustry.gen.Call.menu(player.con,mlogentAfkRootRef._mlogentAfkMenuId,
    mlogentAfkRootRef._mlogentI18n.text(player,'afk.title'),mlogentAfkRootRef._mlogentI18n.text(player,'afk.prompt'),rows);
  }catch(error){
   s.mode=s.limited?'afk':'active';s.lastActivity=now;s.awaiting=false;mlogentAfkPolicyRef.afkError=String(error);
   // A menu delivery failure never penalizes the player.
  }
 };
 mlogentAfkPolicyRef.afkAnswer=function(player,option){
  if(!mlogentAfkPolicyRef.afkAvailable()||!player||!player.con)return;
  var s=mlogentAfkPolicyRef.afkStates['c'+player.con.hashCode()],now=java.lang.System.currentTimeMillis();
  if(!s||!s.awaiting||(s.mode!=='pending'&&s.mode!=='afk'))return;
  if(option===1||option===-1){if(s.mode!=='afk')mlogentAfkPolicyRef.afkFail(player,s,option<0?'closed':'chosen-afk');return;}
  if(option!==0)return;
  // Confirmation remains valid after the 30-second grace and auto-AFK.
  s.mode='active';s.limited=false;s.awaiting=false;s.lastActivity=now;s.reason='confirmed';s.lastEntity=0;s.nextEntity=0;
  var adaptive=mlogentAfkPolicyRef.adaptiveClients&&mlogentAfkPolicyRef.adaptiveClients['c'+player.con.hashCode()];
  if(adaptive){adaptive.level=0;adaptive.high=0;adaptive.low=0;adaptive.ema=null;adaptive.lastChange=now;adaptive.joinedAt=now;adaptive.nextEntity=0;}
  var delivery=mlogentAfkPolicyRef.interestStates&&mlogentAfkPolicyRef.interestStates['c'+player.con.hashCode()];
  if(delivery){mlogentAfkPolicyRef.resetBuildingState(delivery);if(delivery.reactorState)mlogentAfkPolicyRef.resetBuildingState(delivery.reactorState);delivery.lastFar=0;}
  player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.restored'));
 };
 mlogentAfkPolicyRef.afkTick=function(now){
  if(!mlogentAfkPolicyRef.afkAvailable()){mlogentAfkPolicyRef.afkStates={};return;}
  var active={};
  for(var i=0;i<Groups.player.size();i++){
   var player=Groups.player.index(i),con=player.con;
   if(!con||!con.hasConnected||!con.isConnected())continue;
   var key='c'+con.hashCode();active[key]=true;var s=mlogentAfkPolicyRef.afkState(player,now);
   if(typeof mlogentAfkPolicyRef.polyPending==='function'&&mlogentAfkPolicyRef.polyPending(player))continue;
   if(s.mode==='active'&&now-s.lastActivity>=mlogentAfkPolicyRef.afkIdleMs)mlogentAfkPolicyRef.afkAsk(player,now);
   else if(s.mode==='pending'&&now>=s.deadline)mlogentAfkPolicyRef.afkFail(player,s,'timeout');
  }
  for(var key in mlogentAfkPolicyRef.afkStates)if(!active[key])delete mlogentAfkPolicyRef.afkStates[key];
 };
 mlogentAfkPolicyRef.afkCadence=function(player,now){
  if(!mlogentAfkPolicyRef.afkAvailable())return null;
  var s=mlogentAfkPolicyRef.afkStates['c'+player.con.hashCode()];
  if(!s||!s.limited)return null;
  s.interval=mlogentAfkPolicyRef.afkIntervalMs;if(s.nextEntity===undefined)s.nextEntity=now;
  return s;
 };
 mlogentAfkPolicyRef.afkSupplementDue=function(player,now){
  var s=mlogentAfkPolicyRef.afkCadence(player,now);if(!s)return true;
  if(s.lastSupplement&&now-s.lastSupplement<mlogentAfkPolicyRef.afkIntervalMs)return false;
  s.lastSupplement=now;return true;
 };
 if(mlogentAfkRootRef._mlogentAfkMenuId===undefined){
  mlogentAfkRootRef._mlogentAfkMenuId=Packages.mindustry.ui.Menus.registerMenu(
   new JavaAdapter(Packages.mindustry.ui.Menus$MenuListener,{get:function(player,option){
    var current=mlogentAfkRootRef._mcpSnapshotPolicy;
    try{if(current&&current.afkAnswer)current.afkAnswer(player,Number(option));}
    catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
   }}));
 }
 if(!mlogentAfkRootRef._mlogentAfkHooks){
  Vars.netServer.admins.addActionFilter(new JavaAdapter(Packages.mindustry.net.Administration$ActionFilter,{allow:function(action){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;
   try{
    var type=String(action.type);
    if(current&&(type==='placeBlock'||type==='breakBlock'||type==='control'||type==='buildSelect'||type==='commandUnits'))
     current.afkActivity(action.player,type);
   }catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
   return true; // Never change the authorization outcome of any game request.
  }}));
  var lastTick=0;
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy,now=java.lang.System.currentTimeMillis();
   if(now-lastTick<1000)return;lastTick=now;
   try{if(current&&current.afkTick)current.afkTick(now);}
   catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
  });
  Events.on(Packages.mindustry.game.EventType.WorldLoadEvent,function(){
   if(mlogentAfkRootRef._mcpSnapshotPolicy)mlogentAfkRootRef._mcpSnapshotPolicy.afkStates={};
  });
  mlogentAfkRootRef._mlogentAfkHooks=true;
 }
 var commands=Vars.netServer.clientCommands;
 commands.removeCommand('afkverify');
 commands.register('afkverify','','重新打开 AFK 验证或查看状态',
  new JavaAdapter(Packages.arc.util.CommandHandler$CommandRunner,{accept:function(args,player){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;if(!current||!current.afkAvailable()){player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.disabled'));return;}
   var now=java.lang.System.currentTimeMillis(),s=current.afkState(player,now);
   if(s.mode==='pending')player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.pending'));
   else current.afkAsk(player,now);
  }}));
})();
"""

from .world_i18n import INSTALL_JS as I18N_INSTALL_JS
INSTALL_JS = I18N_INSTALL_JS + INSTALL_JS
