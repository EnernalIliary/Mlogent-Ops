"""v160 headless interest management; all callbacks execute on the game thread."""

INSTALL_JS = r"""
(function(){
 var mcpInterestRoot=this;
 var policy=this._mcpSnapshotPolicy;
 var fresh=!policy.interestInstalled;
 if(Packages.mindustry.core.Version.build!==160)throw new Error('Interest management requires tested v160');
 var original=policy.interestOriginal||Vars.netServer;
 var listeners=Core.app.getListeners();
 var slot=listeners.indexOf(policy.interestWrapper||original,true);
 if(slot<0)slot=listeners.indexOf(original,true);
 if(slot<0)throw new Error('NetServer update listener not found');
 var field=original.getClass().getDeclaredField('blockSyncTime');
 field.setAccessible(true);
 var blockTimer=field.get(null);
 policy.interestEnabled=true;
 policy.interestError=null;
 policy.interestStates={};
 policy.interestLastBase=0;
 policy.interestStaggerEnabled=false;
 policy.interestEntityIntervalMs=0;
 policy.interestPerPlayerFullView=false;
 policy.interestAOIPlayers=0;
 policy.interestFullViewPlayers=0;
 policy.interestFullViewEntityTicks=0;
 policy.interestReactorEnabled=false;
 policy.interestReactorIntervalMs=500;
 policy.interestReactorHeatThreshold=0.7;
 policy.interestImpactReactorId=null;
 policy.interestReactors=null;
 policy.interestReactorCount=0;
 policy.interestReactorTicks=0;
 policy.interestReactorRecords=0;
 policy.interestReactorMaxAgeMs=0;
 policy.interestFarBucketsEnabled=false;
 policy.interestFarBucketCount=4;
 policy.interestFarBucketRounds=[0,0,0,0];
 policy.interestEntityMaxSelection=0;
 policy.interestPhaseOrigin=null;
 policy.interestPhaseNext=null;
 policy.interestPhaseInterval=0;
 policy.interestPhaseIntervals={};
 policy.interestPhaseTicks={state:0,entities:0,buildings:0};
 policy.interestDispatchTicks=0;
 policy.interestDispatchMaxMs=0;
 policy.interestCycleIndex=-1;
 policy.interestCycleWorkMs=0;
 policy.interestEntityRecords=0;
 policy.interestBuildingRecords=0;
 policy.interestBuildingMode='pending';
 policy.interestBuildingReason=null;
 policy.interestBuildingCount=0;
 policy.interestBuildingCheckAt=0;
 policy.interestBuildings=null;
 policy.interestUnitMode='pending';
 policy.interestBuildingEffectiveMode='pending';
 policy.interestTicks=0;
 policy.interestMaxMs=0;
 policy.interestTotalMs=0;
 policy.interestMargin=1.5;
 policy.interestBuildingLimit=64;
 policy.interestBuildingByteLimit=16384;
 policy.interestBuildingScanLimit=128;
 policy.interestBuildingCleanupLimit=16;
 policy.interestBuildingSoftBudgetMs=2;
 policy.interestBuildingBuffer=null;
 policy.interestBuildingTimings={};
 policy.interestBuildingScanned=0;
 policy.interestBuildingCleaned=0;
 policy.interestBuildingYields=0;
 policy.interestBuildingFogSkipped=0;
 policy.interestBuildingRevealed=0;
 policy.interestEnemyBuildingsInViewOnly=false;
 policy.interestBuildingOutsideSkipped=0;
 policy.interestDiagnosticsEnabled=false;
 policy.interestDiagnosticActive=null;
 // Conservative experimental bounds. Native serialization cannot be preempted;
 // checks bound JS work and disable AOI after an overrun, not interrupt a JVM stall.
 policy.interestBudgetMs=8;
 policy.interestRelaxedGuards=false;
 policy.interestUpdateGapMs=750;
 policy.interestHardWorkMs=100;
 policy.interestSlowLimit=3;
 policy.interestSlowCount=0;
 policy.interestWorkLastMs=0;
 policy.interestWorkMaxMs=0;
 policy.interestHeapMaxRatio=0.85;
 policy.interestSwapMaxKB=65536;
 policy.interestEventPath=null;
 policy.interestLastFallbackEvent=null;
 policy.interestMaxPlayers=12;
 policy.interestMaxEntities=1024;
 policy.interestMaxBuildings=3072;
 policy.interestMaxClientBuildingRecords=3072;
 policy.interestDeadlineNs=0;
 policy.interestLastUpdate=0;
 policy.interestMemoryCheckAt=0;
 policy.interestHostSoftMinKB=131072;
 policy.interestHostHardMinKB=98304;
 policy.interestHostHoldMs=5000;
 policy.interestHostLowSince=null;
 policy.interestFallbackReason=null;
 policy.interestFullViewFallbacks=0;
 policy.interestInFullView=false;
 policy.interestStage='idle';
 policy.interestGuardLastMs=0;
 policy.interestGuardMaxMs=0;
 policy.checkBudget=function(){
  if(this.interestRelaxedGuards)return;
  var cBudgetNow=java.lang.System.nanoTime();
  if(this.interestDeadlineNs&&cBudgetNow>this.interestDeadlineNs)
   throw new Error('AOI scheduling budget exceeded at '+this.interestStage+
    ', over by '+((cBudgetNow-this.interestDeadlineNs)/1000000)+' ms');
 };
 policy.readMetric=function(path,key){
  var reader=new java.io.BufferedReader(new java.io.FileReader(path));
  try{
   var line;
   while((line=reader.readLine())!=null){
    line=String(line);
    if(line.indexOf(key+':')===0){
     // parseFloat tolerates tabs/units and avoids Rhino's Java String.split overloads.
     var value=parseFloat(line.substring(key.length+1));
     if(isFinite(value)&&value>=0)return value;
     throw new Error('AOI memory guard invalid metric: '+key);
    }
   }
  }finally{reader.close();}
  throw new Error('AOI memory guard metric unavailable: '+key);
 };
 policy.runtimeGuard=function(now){
  var last=policy.interestMemoryCheckAt;
  if(now>=last&&now-last<1000)return;
  // Do not count unobserved gaps (or wall-clock steps) as sustained pressure.
  if(now<last||now-last>2500)policy.interestHostLowSince=null;
  policy.interestMemoryCheckAt=now;
  var runtime=java.lang.Runtime.getRuntime();
  var used=runtime.totalMemory()-runtime.freeMemory();
  var sample={at:now,heapUsed:used,heapMax:runtime.maxMemory()};
  policy.interestMemorySample=sample;
  if(used>runtime.maxMemory()*policy.interestHeapMaxRatio)throw new Error('AOI heap pressure guard');
  sample.jvmSwapKB=policy.readMetric('/proc/self/status','VmSwap');
  if(sample.jvmSwapKB>policy.interestSwapMaxKB)throw new Error('AOI JVM swap exceeds '+(policy.interestSwapMaxKB/1024)+' MiB');
  sample.hostAvailableKB=policy.readMetric('/proc/meminfo','MemAvailable');
  sample.hostSoftMinKB=policy.interestHostSoftMinKB;
  sample.hostHardMinKB=policy.interestHostHardMinKB;
  sample.hostHoldMs=policy.interestHostHoldMs;
  if(sample.hostAvailableKB<policy.interestHostSoftMinKB){
   if(policy.interestHostLowSince===null)policy.interestHostLowSince=now;
   sample.hostLowForMs=now-policy.interestHostLowSince;
   sample.hostState=sample.hostAvailableKB<policy.interestHostHardMinKB?'critical':
    (sample.hostLowForMs>=policy.interestHostHoldMs?'sustained':'pending');
  }else{
   policy.interestHostLowSince=null;sample.hostLowForMs=0;sample.hostState='ok';
  }
  if(sample.hostState==='critical')throw new Error('AOI available host memory below '+(policy.interestHostHardMinKB/1024)+' MiB emergency floor');
  if(sample.hostState==='sustained')throw new Error('AOI available host memory below '+(policy.interestHostSoftMinKB/1024)+' MiB for '+sample.hostLowForMs+' ms');
 };
 policy.failInterest=function(error){
  var at=Number(java.lang.System.currentTimeMillis());
  var event={id:String(policy.interestPid||0)+'-'+at+'-'+String(java.lang.System.nanoTime()),
   at:at,kind:'aoi-safety-fallback',reason:String(error),stage:policy.interestStage,
   pid:policy.interestPid||null,tid:policy.interestTid||null,
   unitMode:policy.interestUnitMode,buildingMode:policy.interestBuildingEffectiveMode,
   memory:policy.interestMemorySample||null,workLastMs:policy.interestWorkLastMs,
   workMaxMs:policy.interestWorkMaxMs,slowCount:policy.interestSlowCount,
   phases:policy.interestPhaseTicks,buckets:policy.interestFarBucketRounds};
  policy.interestLastFallbackEvent=event;
  if(policy.interestEventPath)try{
   var tmp=String(policy.interestEventPath)+'.tmp',writer=new java.io.FileWriter(tmp,false);
   try{writer.write(JSON.stringify(event));}finally{writer.close();}
   if(!new java.io.File(tmp).renameTo(new java.io.File(String(policy.interestEventPath))))
    throw new Error('Cannot publish fallback marker');
  }catch(recordError){policy.interestRecorderError=String(recordError);}
  original.snapshotSyncTime=0;policy.interestEnabled=false;
  policy.interestError=String(error);policy.interestFallbackReason=String(error);
  if(policy.restoreOriginal)policy.restoreOriginal();
 };
 policy.fullView=function(receiver){
  var view=policy.view(receiver);
  if(view==null)return true;
  var area=Vars.world.width()*Vars.world.height()*Vars.tilesize*Vars.tilesize;
  return view.w*view.h>=area*0.6;
 };
 policy.preflight=function(){
  if(Groups.player.size()>policy.interestMaxPlayers)throw new Error('AOI player bound exceeded');
  if(Groups.sync.size()>policy.interestMaxEntities)throw new Error('AOI entity bound exceeded');
  var near=0,full=0;
  for(var i=0;i<Groups.player.size();i++){
   policy.checkBudget();
   var player=Groups.player.index(i);
   if(!player.con||!player.con.hasConnected||!player.con.isConnected())continue;
   if(policy.fullView(player))full++;else near++;
  }
  policy.interestAOIPlayers=near;policy.interestFullViewPlayers=full;
  return policy.interestPerPlayerFullView||full===0;
 };
 policy.view=function(receiver){
  var c=receiver.con,x=Number(c.viewX),y=Number(c.viewY);
  var w=Number(c.viewWidth),h=Number(c.viewHeight);
  // Invalid/uninitialised/oversized camera reports fall back to full-rate sync.
  var max=Math.max(Vars.world.width(),Vars.world.height())*Vars.tilesize*4;
  if(!isFinite(x)||!isFinite(y)||!isFinite(w)||!isFinite(h)||w<=0||h<=0||w>max||h>max)return null;
  return {x:x,y:y,w:w*policy.interestMargin,h:h*policy.interestMargin};
 };
 policy.inView=function(view,entity){
  if(view==null)return true;
  var radius=Math.max(Number(entity.hitSize)||0,Number(entity.block?entity.block.size*Vars.tilesize:0)||0)/2;
  return Math.abs(entity.x-view.x)<=view.w/2+radius&&Math.abs(entity.y-view.y)<=view.h/2+radius;
 };
 policy.controlledUnitIds=function(){
  var ids={};
  for(var pi=0;pi<Groups.player.size();pi++){
   var player=Groups.player.index(pi),con=player.con;
   if(!con||!con.hasConnected||!con.isConnected()||player.dead())continue;
   var unit=player.unit();if(unit!=null)ids[unit.id]=true;
  }
  return ids;
 };
 policy.nearEntity=function(receiver,view,entity){
  // Every connected player's controlled unit bypasses far-view cadence.
  return !(entity instanceof Packages.mindustry.gen.Unit)||
   !!policy.controlledUnitIds()[entity.id]||policy.inView(view,entity);
 };
 policy.selectEntities=function(receiver,view,farDue,entities,hidden,farBucket){
  var selected=new Packages.arc.struct.Seq();
  var unitType=policy.interestUnitType||(policy.interestUnitType=Packages.mindustry.gen.Unit);
  var fog=!!Vars.state.rules.fog;
  var team=fog?receiver.team():null;
  var ownId=receiver.dead()?-1:receiver.unit().id;
  var controlled=policy.controlledUnitIds();
  var bucketed=farBucket!==undefined&&farBucket!==null;
  var all=view==null||(!bucketed&&farDue);
  var left=all?0:view.x-view.w/2,right=all?0:view.x+view.w/2;
  var bottom=all?0:view.y-view.h/2,top=all?0:view.y+view.h/2;
  for(var i=0;i<entities.size();i++){
   if(i%16===0)policy.checkBudget();
   var entity=entities.index(i);
   // Vanilla skips visibility checks entirely without fog. Cache per-receiver
   // invariants and reject distant units before crossing the JS/Java bridge
   // for additional getters; do not recalculate camera/team/owner per entity.
   if(fog&&entity.isSyncHidden(team)){hidden.add(entity.id);continue;}
   // Controlled units have one authoritative periodic lane while the
   // supplement is healthy. A disabled/failed supplement restores this lane.
   if(policy.controlledEnabled&&policy.supplement&&controlled[entity.id]&&entity instanceof unitType)continue;
   if(all||!(entity instanceof unitType)||entity.id===ownId||controlled[entity.id]){selected.add(entity);continue;}
   var radius=Number(entity.hitSize)/2||0,x=entity.x;
   var near=x>=left-radius&&x<=right+radius;
   if(near){var y=entity.y;near=y>=bottom-radius&&y<=top+radius;}
   // Stable IDs keep group membership unchanged as entities move or disappear.
   // Near/own units bypass the bucket, including immediately after a camera jump.
   if(near||(bucketed&&((Number(entity.id)%policy.interestFarBucketCount+
      policy.interestFarBucketCount)%policy.interestFarBucketCount)===farBucket))selected.add(entity);
  }
  return selected;
 };
 policy.isLowHeatReactor=function(build){
  return policy.interestReactorEnabled&&Number(build.block.id)===policy.interestImpactReactorId&&
   Number(build.warmup)<policy.interestReactorHeatThreshold;
 };
 policy.prepareReactors=function(){
  var result=new Packages.arc.struct.Seq();
  var impact=Vars.content.block('impact-reactor');
  policy.interestImpactReactorId=impact?Number(impact.id):null;
  if(impact&&Core.settings.getBool('blocksync',true)){
   var teams=Vars.state.teams.present,total=0;
   for(var ti=0;ti<teams.size;ti++){
    var flagged=Vars.indexer.getFlagged(teams.get(ti).team,Packages.mindustry.world.meta.BlockFlag.reactor);
    total+=flagged.size;if(total>policy.interestMaxBuildings)throw new Error('AOI reactor candidate bound exceeded');
    for(var bi=0;bi<flagged.size;bi++){
     policy.checkBudget();var build=flagged.get(bi);
     if(Number(build.block.id)===policy.interestImpactReactorId)result.add(build);
    }
   }
  }
  policy.interestReactors=result;policy.interestReactorCount=result.size;
 };
 policy.buildingDue=function(state,key,blockId,near,now,critical){
  var prev=state.buildings[key];
  if(state.reactorPriority)return !prev||prev.fogHidden||prev.outsideInterest||prev.block!==blockId||
   prev.reactorActive!==critical||(critical&&now-prev.time>=policy.interestReactorIntervalMs);
  return !prev||prev.fogHidden||prev.outsideInterest||prev.block!==blockId||(near&&!prev.near)||now-prev.time>=(near?6000:12000);
 };
 policy.prepareBuildings=function(now){
  if(policy.interestBuildings!==null&&now-policy.interestBuildingCheckAt<
    Packages.mindustry.net.Administration.Config.snapshotInterval.num())return;
  var capacityStarted=java.lang.System.nanoTime();
  policy.interestBuildingCheckAt=now;
  var mode='disabled',reason=null,count=0,flaggedTeams=[];
  if(Core.settings.getBool('blocksync',true)){
   var teams=Vars.state.teams.present;
   for(var i=0;i<teams.size;i++){
    policy.checkBudget();
    var flagged=Vars.indexer.getFlagged(teams.get(i).team,Packages.mindustry.world.meta.BlockFlag.synced);
    count+=flagged.size;flaggedTeams.push(flagged);
   }
   mode=count>policy.interestMaxBuildings?'native':'aoi';
   if(mode==='native')reason='synced building count '+count+' exceeds AOI limit '+policy.interestMaxBuildings;
  }
  // Decide from team sequence sizes before copying or scanning any records.
  var buildings=new Packages.arc.struct.Seq();
  if(mode==='aoi')for(var j=0;j<flaggedTeams.length;j++)buildings.addAll(flaggedTeams[j]);
  if(mode!==policy.interestBuildingMode){
   for(var key in policy.interestStates){
    policy.resetBuildingState(policy.interestStates[key]);
   }
  }
  policy.interestBuildingCount=count;policy.interestBuildingMode=mode;
  policy.interestBuildingReason=reason;policy.interestBuildings=buildings;
  policy.buildingTiming('capacity',java.lang.System.nanoTime()-capacityStarted);
 };
 policy.resetBuildingState=function(state){
  state.buildings={};state.cursor=0;state.buildingKeys=[];state.buildingFree=[];
  state.buildingCount=0;state.buildingSweep=0;state.buildingEvict=0;
  state.buildingEpoch=1;
 };
 policy.buildingTiming=function(stage,nanos){
  var metric=policy.interestBuildingTimings[stage];
  if(!metric)metric=policy.interestBuildingTimings[stage]={lastMs:0,maxMs:0,totalMs:0,calls:0};
  var ms=nanos/1000000;metric.lastMs=ms;metric.maxMs=Math.max(metric.maxMs,ms);metric.totalMs+=ms;metric.calls++;
 };
 policy.writeBuildings=function(receiver,view,state,buildings,now){
  var started=java.lang.System.nanoTime(),cleanupNs=0,initNs=0,serializeNs=0,visibilityNs=0;
  var count=0,total=0,records=0,scanned=0,cleaned=0,yielded=false,buffer=null;
  var detailed=policy.interestDiagnosticsEnabled,encodeNs=0,copyNs=0,sendNs=0;
  var observations=[];
  var fog=!!Vars.state.rules.fog,receiverTeam=receiver.team(),teamKey=String(receiverTeam),viewer=fog?receiverTeam:null;
  var length=buildings.size;
  if(length>policy.interestMaxBuildings)throw new Error('AOI building bound exceeded');
  if(!state.buildingKeys)policy.resetBuildingState(state);
  if(state.receiverTeamKey!==teamKey){policy.resetBuildingState(state);state.receiverTeamKey=teamKey;}
  if(state.buildingCount>policy.interestMaxClientBuildingRecords)
   throw new Error('AOI client building-state bound exceeded');
  var deadline=started+policy.interestBuildingSoftBudgetMs*1000000;
  if(policy.interestDeadlineNs)deadline=Math.min(deadline,policy.interestDeadlineNs-500000);
  function hasTime(){return java.lang.System.nanoTime()<deadline;}
  function save(build,key,near){
   var previous=state.buildings[key],slot;
   if(previous)slot=previous.slot;
   else{
    if(state.buildingFree.length)slot=state.buildingFree.pop();
    else if(state.buildingKeys.length<policy.interestMaxClientBuildingRecords)slot=state.buildingKeys.length;
    else{
     slot=state.buildingEvict++%state.buildingKeys.length;
     delete state.buildings[state.buildingKeys[slot]];state.buildingCount--;
    }
    state.buildingKeys[slot]=key;state.buildingCount++;
   }
   if(previous&&previous.fogHidden)policy.interestBuildingRevealed++;
   state.buildings[key]={time:now,near:near,block:build.block.id,id:build.id,slot:slot,seenEpoch:state.buildingEpoch,fogHidden:false,outsideInterest:false,
    reactorActive:state.reactorPriority?critical:false};
  }
  function flush(){
   if(count===0)return;
   var t=java.lang.System.nanoTime(),data=buffer.stream.toByteArray(),sendCount=count;
   if(detailed)copyNs+=java.lang.System.nanoTime()-t;
   var dedup=!!policy.buildingDedupEnabled&&observations.length===count;
   if(dedup){
    var kept=[],skipped=0,skippedBytes=0;
    for(var oi=0;oi<observations.length;oi++){
     var observation=observations[oi];
     var skip=policy.observeBuildingRecord(state,observation.key,observation.build,data,
      observation.start,observation.end,now,observation.force);
     if(skip){skipped++;skippedBytes+=observation.end-observation.start;}
     else kept.push(observation);
    }
    // An observer failure restores the entire original packet.
    if(policy.buildingDedupEnabled&&skipped){
     buffer.stream.reset();
     for(var ki=0;ki<kept.length;ki++){
      var part=kept[ki];buffer.stream.write(data,part.start,part.end-part.start);
     }
     data=buffer.stream.toByteArray();sendCount=kept.length;
    }else{skipped=0;skippedBytes=0;}
   }
   try{
    if(sendCount){t=java.lang.System.nanoTime();
     try{Packages.mindustry.gen.Call.blockSnapshot(receiver.con,sendCount,data);}
     finally{if(detailed)sendNs+=java.lang.System.nanoTime()-t;}
    }
   }catch(error){
    // No successful send: discard optimistic byte baselines before fallback.
    if(typeof policy.resetBuildingObservation==='function')policy.resetBuildingObservation();
    throw error;
   }
   if(policy.buildingObservation&&sendCount){
    policy.buildingObservation.sentRecords+=sendCount;
    policy.buildingObservation.sentPayloadBytes+=data.length;
    policy.buildingObservation.sentPackets++;
   }
   if(dedup){
    policy.buildingObservation.skippedRecords+=skipped;
    policy.buildingObservation.skippedBytes+=skippedBytes;
    if(sendCount===0)policy.buildingObservation.skippedPackets++;
   }else for(var oi=0;oi<observations.length;oi++){
    var observation=observations[oi];
    policy.observeBuildingRecord(state,observation.key,observation.build,data,observation.start,observation.end,now);
   }
   observations=[];
   count=0;buffer.stream.reset();
  }
  try{
   policy.checkBudget();
   // Bounded generational sweep: no Object.keys(), full live set, retained
   // Building references or per-entry JS/Java tile lookups. Two cursor passes
   // tolerate indexer reordering; an eviction only causes a later resnapshot.
   policy.interestStage='building-cleanup';
   var phase=java.lang.System.nanoTime();
   var sweep=Math.min(state.buildingKeys.length,policy.interestBuildingCleanupLimit);
   for(var n=0;n<sweep&&hasTime();n++){
    var slot=state.buildingSweep++%state.buildingKeys.length,key=state.buildingKeys[slot];
    if(key==null)continue;
    var previous=state.buildings[key];cleaned++;
    if(length===0||previous.seenEpoch<state.buildingEpoch-1){
     delete state.buildings[key];state.buildingKeys[slot]=null;state.buildingFree.push(slot);state.buildingCount--;
    }
   }
   cleanupNs=java.lang.System.nanoTime()-phase;
   policy.checkBudget();
   while(scanned<length&&scanned<policy.interestBuildingScanLimit&&
     records<policy.interestBuildingLimit&&total<policy.interestBuildingByteLimit){
    if(!hasTime()){yielded=true;break;}
    policy.checkBudget();policy.interestStage='building-scan';
    var index=state.cursor%length,build=buildings.get(index),key='b'+build.pos();
    var previous=state.buildings[key];
    if(fog){
     policy.interestStage='building-visibility';phase=java.lang.System.nanoTime();
     var hidden;
     try{hidden=build.inFogTo(viewer);}finally{visibilityNs+=java.lang.System.nanoTime()-phase;}
     policy.checkBudget();
     if(hidden){
      // Keep last delivered state but never serialize an invisible enemy.
      // Mark reappearance due immediately, even within its old 6/12s period.
      if(previous){previous.seenEpoch=state.buildingEpoch;previous.fogHidden=true;previous.near=false;}
      policy.interestBuildingFogSkipped++;state.cursor=(index+1)%length;scanned++;
      if(state.cursor===0)state.buildingEpoch++;
      continue;
     }
    }
    var near=policy.inView(view,build);
    if(policy.interestEnemyBuildingsInViewOnly&&!near&&build.team!=null&&String(build.team)!==teamKey){
     if(previous){previous.seenEpoch=state.buildingEpoch;previous.outsideInterest=true;previous.near=false;}
     policy.interestBuildingOutsideSkipped++;state.cursor=(index+1)%length;scanned++;
     if(state.cursor===0)state.buildingEpoch++;
     continue;
    }
    var critical=policy.isLowHeatReactor(build);
    var priorityLast=!state.reactorPriority&&state.reactorState&&state.reactorState.buildings&&state.reactorState.buildings[key];
    var priorityFresh=priorityLast&&state.reactorState.receiverTeamKey===teamKey&&!critical&&!priorityLast.fogHidden&&
     !(previous&&(previous.fogHidden||previous.outsideInterest||(near&&!previous.near)))&&priorityLast.id===build.id&&
     priorityLast.block===build.block.id&&now-priorityLast.time<(policy.inView(view,build)?6000:12000);
    if((state.reactorPriority&&!critical&&(!previous||!previous.reactorActive))||(!state.reactorPriority&&critical)||priorityFresh){
     if(previous)previous.seenEpoch=state.buildingEpoch;
     state.cursor=(index+1)%length;scanned++;
     if(state.cursor===0)state.buildingEpoch++;
     continue;
    }
    if(state.reactorPriority&&critical&&previous&&!previous.fogHidden&&previous.reactorActive)
     policy.interestReactorMaxAgeMs=Math.max(policy.interestReactorMaxAgeMs,now-previous.time);
    policy.interestStage='building-scan';
    if(previous&&previous.id!==build.id){delete state.buildings[key];
     state.buildingKeys[previous.slot]=null;state.buildingFree.push(previous.slot);state.buildingCount--;}
    else if(previous)previous.seenEpoch=state.buildingEpoch;
    if(policy.buildingDue(state,key,build.block.id,near,now,critical)){
     if(!hasTime()){yielded=true;break;}
     if(!buffer){
      policy.interestStage='building-initialize';phase=java.lang.System.nanoTime();
      buffer=policy.interestBuildingBuffer;
      if(!buffer){var stream=new java.io.ByteArrayOutputStream();var output=new java.io.DataOutputStream(stream);
       buffer={stream:stream,output:output,writes:Packages.arc.util.io.Writes.get(output)};
       policy.interestBuildingBuffer=buffer;}
      buffer.stream.reset();initNs+=java.lang.System.nanoTime()-phase;
      policy.checkBudget();
      // Initializing native helpers can consume this soft slice. Retry this
      // exact candidate next turn, reusing the now-warm buffer.
      if(!hasTime()){yielded=true;break;}
     }
     policy.interestStage='building-serialize';phase=java.lang.System.nanoTime();
     try{
      var before=buffer.stream.size();
      var encodeStart=detailed?java.lang.System.nanoTime():0;
      try{buffer.output.writeInt(build.pos());buffer.output.writeShort(build.block.id);build.writeSync(buffer.writes);}
      finally{if(detailed)encodeNs+=java.lang.System.nanoTime()-encodeStart;}
      if(policy.buildingObservationEnabled&&typeof policy.observeBuildingRecord==='function')
       observations.push({key:String(receiver.team())+':'+key,build:build,start:before,end:buffer.stream.size(),
        force:!!state.reactorPriority||!previous||previous.fogHidden||previous.outsideInterest||previous.id!==build.id||
         previous.block!==build.block.id||(near&&!previous.near)});
      total+=buffer.stream.size()-before;count++;records++;save(build,key,near);
      if(buffer.stream.size()>800)flush();
     }finally{serializeNs+=java.lang.System.nanoTime()-phase;}
     policy.checkBudget();
    }else if(!near){state.buildings[key].near=false;}
    // Advance only after the candidate is handled; a soft yield loses no work.
    state.cursor=(index+1)%length;scanned++;
    if(state.cursor===0)state.buildingEpoch++;
   }
   policy.interestStage='building-flush';phase=java.lang.System.nanoTime();
   try{flush();}finally{serializeNs+=java.lang.System.nanoTime()-phase;}
   policy.checkBudget();
  }finally{
   var elapsed=java.lang.System.nanoTime()-started;
   policy.buildingTiming('cleanup',cleanupNs);policy.buildingTiming('initialize',initNs);
   policy.buildingTiming('visibility',visibilityNs);
   policy.buildingTiming('serialize',serializeNs);
   if(detailed){policy.buildingTiming('encode',encodeNs);policy.buildingTiming('copy',copyNs);policy.buildingTiming('send',sendNs);}
   policy.buildingTiming('scan',Math.max(0,elapsed-cleanupNs-initNs-serializeNs-visibilityNs));
   policy.buildingTiming('total',elapsed);
   policy.interestBuildingScanned+=scanned;policy.interestBuildingCleaned+=cleaned;
   if(yielded)policy.interestBuildingYields++;
   policy.interestBuildingRecords+=records;
  }
 };
 policy.interestPhaseDue=function(key,now,interval,baseInterval){
  baseInterval=baseInterval||interval;
  if(policy.interestPhaseOrigin===null||policy.interestPhaseInterval!==baseInterval){
   policy.interestPhaseOrigin=now;policy.interestPhaseInterval=baseInterval;
   var entityInterval=policy.interestEntityIntervalMs||baseInterval;
   var entityOffset=entityInterval<baseInterval?Math.floor(entityInterval/4):Math.floor(baseInterval/3);
   policy.interestPhaseNext={state:now,entities:now+entityOffset,fullEntities:now+Math.floor(baseInterval/3),buildings:now+Math.floor(2*baseInterval/3),
    reactors:now+Math.floor(policy.interestReactorIntervalMs/4)};
   policy.interestPhaseIntervals={};
  }
  if(policy.interestPhaseIntervals[key]&&policy.interestPhaseIntervals[key]!==interval)policy.interestPhaseNext[key]=now;
  policy.interestPhaseIntervals[key]=interval;
  var next=policy.interestPhaseNext[key];
  if(now<next)return false;
  // Skip missed slots rather than replaying a backlog as a packet burst.
  policy.interestPhaseNext[key]=next+(Math.floor((now-next)/interval)+1)*interval;
  return true;
 };
 policy.interestSend=function(now,buildingsOnly){
  var interval=Packages.mindustry.net.Administration.Config.snapshotInterval.num();
  var sendState=!buildingsOnly,sendEntities=!buildingsOnly,sendBuildings=policy.interestBuildingMode==='aoi';
  var sendFullEntities=!buildingsOnly&&policy.interestPerPlayerFullView&&policy.interestFullViewPlayers>0;
  var sendReactors=policy.interestReactorEnabled;
  var adaptiveOpportunity=!!policy.adaptiveEnabled&&!Vars.state.rules.pvp;
  if(policy.interestStaggerEnabled){
   sendState=sendState&&policy.interestPhaseDue('state',now,interval,interval);
   sendEntities=sendEntities&&policy.interestPhaseDue('entities',now,policy.interestEntityIntervalMs||interval,interval);
   sendFullEntities=sendFullEntities&&policy.interestPhaseDue('fullEntities',now,interval,interval);
   sendBuildings=sendBuildings&&policy.interestPhaseDue('buildings',now,interval,interval);
   sendReactors=sendReactors&&policy.interestPhaseDue('reactors',now,policy.interestReactorIntervalMs,interval);
   if(!sendState&&!sendEntities&&!sendFullEntities&&!sendBuildings&&!sendReactors&&!adaptiveOpportunity)return;
  }else if(now-policy.interestLastBase<interval)return;
  // A native update may cross a due boundary. Open a send-only trace here if
  // the pre-update observer did not run; its setup is outside the work budget.
  if(policy.interestDiagnosticsEnabled&&!policy.interestDiagnosticActive&&typeof policy.interestDiagnosticBegin==='function'){
   var observerStarted=java.lang.System.nanoTime();
   policy.interestDiagnosticBegin(now,true);
   if(policy.interestDeadlineNs)policy.interestDeadlineNs+=java.lang.System.nanoTime()-observerStarted;
  }
  policy.interestLastBase=now;
  var started=java.lang.System.nanoTime();
  policy.interestStage='state';
  if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('state');
  if(sendState){original.writeStateSnapshot();policy.interestPhaseTicks.state++;}
  var buildings=policy.interestBuildings;
  if(sendReactors&&Groups.player.size()>0)policy.prepareReactors();
  var active={};
  if(sendEntities||sendFullEntities||sendBuildings||sendReactors||adaptiveOpportunity){
  for(var j=0;j<Groups.player.size();j++){
   policy.checkBudget();
   var receiver=Groups.player.index(j),con=receiver.con;
   if(con==null||!con.hasConnected||!con.isConnected())continue;
   var key='c'+con.hashCode();active[key]=true;
   var state=policy.interestStates[key];
   if(!state){state={lastFar:0,buildings:{},cursor:0};policy.interestStates[key]=state;}
   var view=policy.view(receiver),farDue=now-state.lastFar>=1000;
   var fullView=policy.interestPerPlayerFullView&&policy.fullView(receiver);
   state.entityMode=fullView?'full-view':'aoi';
   if(sendReactors){
    policy.interestStage='reactor-priority';
    if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('reactor-priority');
    if(!state.reactorState)state.reactorState={reactorPriority:true};
    var beforeRecords=policy.interestBuildingRecords;
    policy.writeBuildings(receiver,null,state.reactorState,policy.interestReactors,now);
    policy.interestReactorRecords+=policy.interestBuildingRecords-beforeRecords;
   }
   var cadence=typeof policy.adaptiveCadence==='function'?policy.adaptiveCadence(receiver,now,fullView):null;
   if(typeof policy.afkCadence==='function')cadence=policy.afkCadence(receiver,now)||cadence;
   var entityDue=fullView?sendFullEntities:sendEntities;
   if(cadence){
    entityDue=now>=cadence.nextEntity;
    // Dispatch opportunities include staggered building/reactor phases,
    // avoiding rounding a requested 250ms cadence up to a 400ms global slot.
   }
   if(entityDue){
   var farBucket=null;
   if(policy.interestFarBucketsEnabled&&!fullView){
    if(state.farNextBucket===undefined)state.farNextBucket=0;
    farBucket=state.farNextBucket;
   }
   var hidden=new Packages.arc.struct.IntSeq();
   policy.interestStage='entity-selection';
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('entity-selection');
   var selected=policy.selectEntities(receiver,fullView?null:view,fullView||farDue,Groups.sync,hidden,farBucket);
   policy.interestEntityMaxSelection=Math.max(policy.interestEntityMaxSelection,selected.size);
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('entity-write');
   // An empty heartbeat prevents client snapshot timeout when its viewport is empty.
   if(selected.isEmpty())Packages.mindustry.gen.Call.entitySnapshot(con,0,java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE,0));
   else if(selected.size<=128){
    // Vanilla chunks the packet natively. Rebuilding another JS batch for a
    // small selection costs more bridge calls than serialization itself.
    policy.interestStage='entity-native-write';
    original.writeCustomEntitySnapshot(receiver,selected);policy.checkBudget();
   }else{
    policy.interestStage='entity-batched-write';
    // Small batches allow a cooperative budget check between native writes.
    var batch=new Packages.arc.struct.Seq();
    for(var n=0;n<selected.size;n++){
     batch.add(selected.get(n));
     if(batch.size>=32||n===selected.size-1){
      original.writeCustomEntitySnapshot(receiver,batch);
      batch=new Packages.arc.struct.Seq();policy.checkBudget();
     }
    }
   }
   policy.interestEntityRecords+=selected.size;
   state.entityBatches=(state.entityBatches||0)+1;state.entityRecords=(state.entityRecords||0)+selected.size;
   state.lastEntityAt=now;
   if(cadence){
    cadence.lastEntity=now;
    cadence.nextEntity+=cadence.interval*(Math.floor(Math.max(0,now-cadence.nextEntity)/cadence.interval)+1);
   }
   if(farDue)state.lastFar=now;
   if(hidden.size>0)Packages.mindustry.gen.Call.hiddenSnapshot(con,hidden);
   if(con.localEntities.size>0)original.writeCustomEntitySnapshot(receiver,con.localEntities);
   if(farBucket!==null){
    policy.interestFarBucketRounds[farBucket]++;
    // Advance only after a completed dispatch. Long frames do not skip an
    // entire ID group or trigger a catch-up burst of all four groups.
    state.farNextBucket=(farBucket+1)%policy.interestFarBucketCount;
   }
   }
   if(sendBuildings){
    policy.interestStage='building-write';
    if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('buildings');
    policy.writeBuildings(receiver,view,state,buildings,now);
   }
  }
  for(var key in policy.interestStates)if(!active[key])delete policy.interestStates[key];
  }
  if(sendEntities)policy.interestPhaseTicks.entities++;
  if(sendFullEntities)policy.interestFullViewEntityTicks++;
  if(sendBuildings)policy.interestPhaseTicks.buildings++;
  if(sendReactors)policy.interestReactorTicks++;
  if(sendEntities||(buildingsOnly&&sendBuildings))policy.interestTicks++;
  policy.interestDispatchTicks++;
  var elapsed=(java.lang.System.nanoTime()-started)/1000000;
  policy.interestTotalMs+=elapsed;
  policy.interestDispatchMaxMs=Math.max(policy.interestDispatchMaxMs,elapsed);
  if(policy.interestStaggerEnabled){
   var cycle=Math.floor((now-policy.interestPhaseOrigin)/interval);
   if(cycle!==policy.interestCycleIndex){policy.interestCycleIndex=cycle;policy.interestCycleWorkMs=0;}
   policy.interestCycleWorkMs+=elapsed;
   policy.interestMaxMs=Math.max(policy.interestMaxMs,policy.interestCycleWorkMs);
  }else policy.interestMaxMs=Math.max(policy.interestMaxMs,elapsed);
 };
 policy.interestUpdate=function(){
  try{if(typeof policy.limitPreviewPlans==='function')policy.limitPreviewPlans();}
  catch(error){policy.previewPlanError=String(error);}
  if(!policy.interestEnabled||Vars.state.rules.pvp||!Vars.state.isGame()||!Vars.net.server()){
   policy.interestUnitMode='native';
   policy.interestBuildingEffectiveMode='native';
   original.update();return;
  }
  var diagnosticError=null,dispatchBefore=policy.interestDispatchTicks;
  try{
   var now=java.lang.System.currentTimeMillis();
   if(policy.interestDiagnosticsEnabled&&typeof policy.interestDiagnosticBegin==='function')policy.interestDiagnosticBegin(now);
   if(policy.interestLastUpdate&&now-policy.interestLastUpdate>policy.interestUpdateGapMs)
    throw new Error('AOI update gap exceeds '+policy.interestUpdateGapMs+' ms');
   policy.interestLastUpdate=now;
   policy.interestDeadlineNs=0;
   policy.interestStage='memory-guard';
   var guardStarted=java.lang.System.nanoTime();
   policy.runtimeGuard(now);
   policy.interestGuardLastMs=(java.lang.System.nanoTime()-guardStarted)/1000000;
   policy.interestGuardMaxMs=Math.max(policy.interestGuardMaxMs,policy.interestGuardLastMs);
   policy.interestDeadlineNs=java.lang.System.nanoTime()+policy.interestBudgetMs*1000000;
   policy.interestStage='preflight';
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('preflight');
   var entityAOI=policy.preflight();
   policy.interestStage='building-capacity';
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('capacity');
   policy.prepareBuildings(now);
   policy.interestBuildingEffectiveMode=policy.interestBuildingMode;
   if(!entityAOI){
    policy.interestUnitMode='native-full-view';
    policy.interestFullViewFallbacks++;
    // Do not use the freshly suppressed timestamp from the prior AOI frame.
    if(!policy.interestInFullView){original.snapshotSyncTime=0;policy.interestInFullView=true;policy.interestLastBase=0;policy.interestPhaseOrigin=null;}
    // Full-view bypass changes entity cadence only. Keep bounded, fog-filtered
    // building snapshots instead of leaking hidden buildings via vanilla sync.
    if(policy.interestBuildingMode==='aoi')blockTimer.reset();
    policy.interestStage='native-full-view-update';
    if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('native-update');
    var fullRemainingNs=policy.interestDeadlineNs-java.lang.System.nanoTime();
    original.update();
    if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('building-control');
    policy.interestDeadlineNs=java.lang.System.nanoTime()+Math.max(0,fullRemainingNs);
    if(policy.interestBuildingMode==='aoi')policy.interestSend(java.lang.System.currentTimeMillis(),true);
    return;
   }
   if(policy.interestInFullView)policy.interestPhaseOrigin=null;
   policy.interestInFullView=false;
   policy.interestUnitMode=policy.interestPerPlayerFullView&&policy.interestFullViewPlayers?
    (policy.interestAOIPlayers?'mixed-per-player':'full-view-per-player'):'aoi';
   // Suppress only the stock periodic entity/state branch, not events,
   // health updates, build previews, disconnect handling or custom RPCs.
   original.snapshotSyncTime=Packages.arc.util.Time.millis()+60000;
   // Oversized maps retain the native six-second building timer unchanged.
   if(policy.interestBuildingMode==='aoi')blockTimer.reset();
   policy.interestStage='native-update';
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('native-update');
   var customRemainingNs=policy.interestDeadlineNs-java.lang.System.nanoTime();
   original.update();
   if(policy.interestDiagnosticActive)policy.interestDiagnosticMark('snapshot-control');
   // Budget added AOI work separately from stock engine work and OS probes.
   policy.interestDeadlineNs=java.lang.System.nanoTime()+Math.max(0,customRemainingNs);
   original.snapshotSyncTime=Packages.arc.util.Time.millis();
   policy.interestSend(java.lang.System.currentTimeMillis());
  }catch(error){
   diagnosticError=String(error);
   policy.failInterest(error);
   Packages.arc.util.Log.err('Interest snapshots disabled; vanilla sync restored: '+error);
  }finally{
   if(policy.interestEnabled&&policy.interestDeadlineNs){
    var workMs=Math.max(0,policy.interestBudgetMs+
      (java.lang.System.nanoTime()-policy.interestDeadlineNs)/1000000);
    policy.interestWorkLastMs=workMs;policy.interestWorkMaxMs=Math.max(policy.interestWorkMaxMs,workMs);
    if(policy.interestRelaxedGuards){
     if(workMs>policy.interestHardWorkMs)policy.interestSlowCount++;
     else if(policy.interestDispatchTicks!==dispatchBefore)policy.interestSlowCount=0;
     if(policy.interestSlowCount>=policy.interestSlowLimit){
      diagnosticError='AOI work exceeds '+policy.interestHardWorkMs+' ms for '+policy.interestSlowCount+' consecutive dispatches';
      policy.failInterest(diagnosticError);
     }
    }
   }
   if(policy.interestDiagnosticActive)policy.interestDiagnosticEnd(diagnosticError);
   policy.interestDeadlineNs=0;
  }
 };
 var wrapper=new JavaAdapter(Packages.arc.ApplicationListener,{
  update:function(){
   var current=mcpInterestRoot._mcpSnapshotPolicy;
   if(!current||typeof current.interestUpdate!=='function'){
    original.snapshotSyncTime=Math.min(original.snapshotSyncTime,Packages.arc.util.Time.millis());
    original.update();return;
   }
   try{current.interestUpdate();}catch(error){
    if(typeof current.failInterest==='function')current.failInterest(error);
    else{current.interestEnabled=false;current.interestError=String(error);original.snapshotSyncTime=0;
     if(current.restoreOriginal)current.restoreOriginal();}
    Packages.arc.util.Log.err('Interest callback disabled: '+error);
   }
  },
  init:function(){original.init();},pause:function(){original.pause();},
  resume:function(){original.resume();},resize:function(w,h){original.resize(w,h);},
  dispose:function(){original.dispose();}
 });
 if(!policy.interestWorldCallbackInstalled||!policy.interestIncrementalWorldCallbackInstalled||!policy.interestPhaseWorldCallbackInstalled||!policy.interestRelaxedWorldCallbackInstalled||!policy.interestResourceWorldCallbackInstalled)Events.on(Packages.mindustry.game.EventType.WorldLoadEvent,function(){
  var current=mcpInterestRoot._mcpSnapshotPolicy;
  if(current){
   current.interestStates={};current.interestLastBase=0;current.interestLastUpdate=0;current.interestInFullView=false;
   current.interestBuildings=null;current.interestBuildingCheckAt=0;
   current.interestBuildingMode='pending';current.interestBuildingReason=null;current.interestBuildingCount=0;
   current.interestUnitMode='pending';
   current.interestBuildingEffectiveMode='pending';
   current.interestBuildingBuffer=null;
   current.adaptiveClients={};current.adaptiveFeedbackAt=0;
   if(current.adaptiveResource)current.adaptiveResource={tier:1,at:0,high:0,healthySince:0,lastChange:0,reason:'world-changed'};
   if(current.adaptiveFrame)current.adaptiveFrame={last:0,gaps:[]};
   current.controlledNext=0;
   if(typeof current.resetBuildingObservation==='function')current.resetBuildingObservation();
   current.interestPhaseOrigin=null;current.interestPhaseNext=null;
   current.interestSlowCount=0;
   current.interestReactors=null;current.interestReactorCount=0;
  }
 });
 // Replace the listener in-place; keep Vars.netServer and all its registered
 // packet handlers/commands intact. No second NetServer constructor is invoked.
 listeners.set(slot,wrapper);
 policy.interestOriginal=original;
 policy.interestWrapper=wrapper;
 policy.interestWorldCallbackInstalled=true;
 policy.interestBuildingWorldCallbackInstalled=true;
 policy.interestIncrementalWorldCallbackInstalled=true;
 policy.interestPhaseWorldCallbackInstalled=true;
 policy.interestRelaxedWorldCallbackInstalled=true;
 policy.interestResourceWorldCallbackInstalled=true;
 policy.restoreOriginal=function(){
  var currentListeners=Core.app.getListeners();
  var currentSlot=currentListeners.indexOf(policy.interestWrapper,true);
  if(currentSlot>=0)currentListeners.set(currentSlot,original);
  policy.interestEnabled=false;policy.interestInstalled=false;policy.interestStates={};
  policy.interestUnitMode='native';policy.interestBuildingMode='native';policy.interestBuildings=null;
  policy.interestBuildingEffectiveMode='native';
  policy.interestBuildingBuffer=null;
 };
 policy.interestInstalled=true;
 sb.append('interest installed');
})();
"""
