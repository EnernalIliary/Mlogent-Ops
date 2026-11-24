"""Automatic AFK presence, name badge and per-receiver low-frequency sync."""

INSTALL_JS = r"""
(function(){
 var mlogentAfkRootRef=this,mlogentAfkPolicyRef=this._mcpSnapshotPolicy;
 mlogentAfkPolicyRef.afkEnabled=false;mlogentAfkPolicyRef.afkIdleMs=180000;mlogentAfkPolicyRef.afkIntervalMs=1000;
 mlogentAfkPolicyRef.afkStates=mlogentAfkPolicyRef.afkStates||{};mlogentAfkPolicyRef.afkError=null;
 mlogentAfkPolicyRef.afkModeVersion=2;
 delete mlogentAfkPolicyRef.afkAsk;delete mlogentAfkPolicyRef.afkFail;delete mlogentAfkPolicyRef.afkAnswerMs;
 mlogentAfkPolicyRef.afkAvailable=function(){return mlogentAfkPolicyRef.afkEnabled&&mlogentAfkPolicyRef.interestEnabled&&!Vars.state.rules.pvp;};
 mlogentAfkPolicyRef.afkState=function(player,now){
  var key='c'+player.con.hashCode(),s=mlogentAfkPolicyRef.afkStates[key];
  if(!s)s=mlogentAfkPolicyRef.afkStates[key]={lastActivity:now,mode:'active',reason:'joined',lastEntity:0};
  return s;
 };
 mlogentAfkPolicyRef.afkBadge=function(player){
  if(!mlogentAfkPolicyRef.afkAvailable()||!player||!player.con)return '';
  var s=mlogentAfkPolicyRef.afkStates['c'+player.con.hashCode()];
  return s&&s.mode==='afk'?'[yellow][AFK][] ':'';
 };
 mlogentAfkPolicyRef.afkRefreshName=function(player){
  try{
   if(mlogentAfkRootRef._mlogentAfkNameScript)mlogentAfkRootRef._mlogentAfkNameScript.updateName(player);
   else if(player.name!==undefined){
    var base=String(player.name).replace(/^\[yellow\]\[AFK\]\[\]\s*/, '');
    player.name=mlogentAfkPolicyRef.afkBadge(player)+base;
   }
  }catch(error){mlogentAfkPolicyRef.afkNameError=String(error);}
 };
 mlogentAfkPolicyRef.afkActivity=function(player,reason){
  if(!mlogentAfkPolicyRef.afkAvailable()||!player||!player.con)return;
  var now=java.lang.System.currentTimeMillis(),s=mlogentAfkPolicyRef.afkState(player,now);
  var restore=s.mode!=='active'||!!s.limited;
  s.mode='active';s.limited=false;s.awaiting=false;s.lastActivity=now;s.reason=reason;
  if(!restore)return;
  s.lastEntity=0;s.nextEntity=0;s.lastSupplement=0;
  var adaptive=mlogentAfkPolicyRef.adaptiveClients&&mlogentAfkPolicyRef.adaptiveClients['c'+player.con.hashCode()];
  // Presence cannot override the player's independent bandwidth/resource limit.
  if(adaptive){adaptive.lastEntity=0;adaptive.nextEntity=0;}
  var delivery=mlogentAfkPolicyRef.interestStates&&mlogentAfkPolicyRef.interestStates['c'+player.con.hashCode()];
  if(delivery){
   if(mlogentAfkPolicyRef.resetBuildingState){mlogentAfkPolicyRef.resetBuildingState(delivery);if(delivery.reactorState)mlogentAfkPolicyRef.resetBuildingState(delivery.reactorState);}
   delivery.lastFar=0;delivery.lastEntityAt=0;delivery.farNextBucket=0;
  }
  mlogentAfkPolicyRef.afkRefreshName(player);
  player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.restored'));
 };
 mlogentAfkPolicyRef.afkEnter=function(player,s){
  if(s.mode==='afk'&&s.limited)return;
  s.mode='afk';s.limited=true;s.awaiting=false;s.reason='idle';s.nextEntity=0;s.interval=mlogentAfkPolicyRef.afkIntervalMs;
  mlogentAfkPolicyRef.afkRefreshName(player);
  player.sendMessage(mlogentAfkRootRef._mlogentI18n.text(player,'afk.limited'));
 };
 // Old, already-open menu callbacks cannot change automatic presence state.
 mlogentAfkPolicyRef.afkAnswer=function(){};
 mlogentAfkPolicyRef.afkTick=function(now){
  var active={},available=mlogentAfkPolicyRef.afkAvailable();
  if(!available){mlogentAfkPolicyRef.afkStates={};}
  for(var idx=0;idx<Groups.player.size();idx++){
   var player=Groups.player.index(idx),con=player.con;
   if(!con||!con.hasConnected||!con.isConnected())continue;
   if(!available){mlogentAfkPolicyRef.afkRefreshName(player);continue;}
   var key='c'+con.hashCode();active[key]=true;var s=mlogentAfkPolicyRef.afkState(player,now);
   if(now<s.lastActivity)s.lastActivity=now;
   if(s.mode==='pending'){s.mode=s.limited?'afk':'active';s.awaiting=false;}
   if(s.mode!=='afk'&&now-s.lastActivity>=mlogentAfkPolicyRef.afkIdleMs)mlogentAfkPolicyRef.afkEnter(player,s);
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
 // Extend Wayzer's existing prefix pipeline; its periodic refresh retains AFK.
 try{
  if(typeof Vars.mods!=='undefined'){
   var afkMods=Vars.mods.list(),afkLoader=null;
   for(var afkModIndex=0;afkModIndex<afkMods.size;afkModIndex++){
    var afkMod=afkMods.get(afkModIndex);
    if(String(afkMod.name)==='scriptagent4mindustry'){
     var afkField=afkMod.main.getClass().getDeclaredField('impl');afkField.setAccessible(true);
     afkLoader=afkField.get(afkMod.main).getClass().getClassLoader();break;
    }
   }
   if(afkLoader){
    var afkRegistryClass=afkLoader.loadClass('cf.wayzer.scriptAgent.ScriptRegistry');
    var afkRegistry=afkRegistryClass.getField('INSTANCE').get(null);
    var afkNameScript=afkRegistry.getScriptInfo('wayzer/user/nameExt').getInst();
    var afkNameLoader=afkNameScript.getClass().getClassLoader();
    var afkApiClass=afkNameLoader.loadClass('cf.wayzer.placehold.PlaceHoldApi');
    var afkInterface=afkNameLoader.loadClass('cf.wayzer.placehold.TypeBinder$ObjChild');
    var afkInterfaces=java.lang.reflect.Array.newInstance(java.lang.Class,1);afkInterfaces[0]=afkInterface;
    var afkProvider=java.lang.reflect.Proxy.newProxyInstance(afkNameLoader,afkInterfaces,
     new JavaAdapter(Packages.java.lang.reflect.InvocationHandler,{invoke:function(proxy,method,args){
      var methodName=String(method.getName());
      if(methodName==='resolve'){
       var current=mlogentAfkRootRef._mcpSnapshotPolicy;
       return new java.lang.String(current&&current.afkBadge?current.afkBadge(args[1]):'');
      }
      if(methodName==='toString')return new java.lang.String('Mlogent automatic AFK badge');
      if(methodName==='hashCode')return java.lang.Integer.valueOf(1);
      if(methodName==='equals')return java.lang.Boolean.valueOf(proxy===args[0]);
      return null;
     }}));
    afkApiClass.getField('INSTANCE').get(null).typeBinder(Packages.mindustry.gen.Player).registerChildAny('prefix.0-afk',afkProvider);
    mlogentAfkRootRef._mlogentAfkNameScript=afkNameScript;mlogentAfkPolicyRef.afkNameError=null;
   }
  }
 }catch(error){mlogentAfkPolicyRef.afkNameError=String(error);}
 if(!mlogentAfkRootRef._mlogentAfkAutomaticHooks){
  var afkActionFilter=new JavaAdapter(Packages.mindustry.net.Administration$ActionFilter,{allow:function(action){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;
   try{
    var type=String(action.type);
    if(current&&/^(placeBlock|breakBlock|configure|rotate|removePlanned|pickupBlock|dropPayload|control|buildSelect|command|commandUnits|commandBuilding|respawn)$/.test(type))current.afkActivity(action.player,type);
   }catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
   return true; // Observe attempts before permission filters; do not grant them.
  }});
  Vars.netServer.admins.actionFilters.insert(0,afkActionFilter);
  Events.on(Packages.mindustry.game.EventType.PlayerChatEvent,new JavaAdapter(Packages.arc.func.Cons,{get:function(event){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;
   try{if(current&&event.player&&event.message!==null&&String(event.message).length)current.afkActivity(event.player,'chat');}
   catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
  }}));
  var afkLastTick=0;
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy,now=java.lang.System.currentTimeMillis();
   if(now-afkLastTick<1000)return;afkLastTick=now;
   try{if(current&&current.afkTick)current.afkTick(now);}
   catch(error){if(current){current.afkEnabled=false;current.afkError=String(error);}}
  });
  Events.on(Packages.mindustry.game.EventType.PlayerLeave,new JavaAdapter(Packages.arc.func.Cons,{get:function(event){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;
   if(current&&event.player&&event.player.con){delete current.afkStates['c'+event.player.con.hashCode()];current.afkRefreshName(event.player);}
  }}));
  Events.on(Packages.mindustry.game.EventType.WorldLoadEvent,function(){
   var current=mlogentAfkRootRef._mcpSnapshotPolicy;
   if(current){current.afkStates={};for(var idx=0;idx<Groups.player.size();idx++)current.afkRefreshName(Groups.player.index(idx));}
  });
  mlogentAfkRootRef._mlogentAfkAutomaticHooks=true;
 }
 Vars.netServer.clientCommands.removeCommand('afkverify');
})();
"""

from .world_i18n import INSTALL_JS as I18N_INSTALL_JS
INSTALL_JS = I18N_INSTALL_JS + INSTALL_JS
