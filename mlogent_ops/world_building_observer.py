"""Bounded byte observation and opt-in suppression of unchanged building records."""

INSTALL_JS = r"""
(function(){
 var mlogentBuildingObserverRef=this._mcpSnapshotPolicy;
 mlogentBuildingObserverRef.buildingObservationEnabled=false;
 mlogentBuildingObserverRef.buildingDedupEnabled=false;
 mlogentBuildingObserverRef.buildingDedupRefreshMs=24000;
 mlogentBuildingObserverRef.buildingObservation={mode:'observe',samples:0,comparable:0,repeated:0,
  sampledBytes:0,repeatedBytes:0,oversize:0,rateLimited:0,cohortSkipped:0,cacheBytes:0,
  skippedRecords:0,skippedBytes:0,skippedPackets:0,forcedRefreshes:0,
  sentRecords:0,sentPayloadBytes:0,sentPackets:0,
  calls:0,totalMs:0,maxMs:0,error:null};
 var cache={},slots=[],cursor=0,windowAt=0,windowSamples=0;
 mlogentBuildingObserverRef.buildingObservationNextState=mlogentBuildingObserverRef.buildingObservationNextState||0;
 mlogentBuildingObserverRef.buildingObservationGeneration=(mlogentBuildingObserverRef.buildingObservationGeneration||0)+1;
 mlogentBuildingObserverRef.resetBuildingObservation=function(){
  cache={};slots=[];cursor=0;mlogentBuildingObserverRef.buildingObservation.cacheBytes=0;
 };
 mlogentBuildingObserverRef.observeBuildingRecord=function(state,key,build,data,start,end,now,force){
  if(!mlogentBuildingObserverRef.buildingObservationEnabled)return false;
  var m=mlogentBuildingObserverRef.buildingObservation,t=java.lang.System.nanoTime();
  try{
   var length=end-start;
   // Identity includes receiver state, building position, ID and block type.
   // Cache is global and bounded: <=64 records, <=128KiB of byte arrays.
   if(state.observationGeneration!==mlogentBuildingObserverRef.buildingObservationGeneration){
    state.observationId=++mlogentBuildingObserverRef.buildingObservationNextState;
    state.observationGeneration=mlogentBuildingObserverRef.buildingObservationGeneration;
   }
   var id=state.observationId+':'+key+':'+build.id+':'+build.block.id;
   var old=cache[id];
   if(length>2048){if(old)old.valid=false;m.oversize++;return false;}
   // Keep a cohort long enough to see its next 6/12s update. A rolling FIFO
   // on a 2000-building map evicts every sample before it can be compared.
   if(!old&&slots.length>=64&&now-cache[slots[cursor]].at<60000){m.cohortSkipped++;return;}
   if(now-windowAt>=1000||now<windowAt){windowAt=now;windowSamples=0;}
   if(windowSamples>=8){if(old)old.valid=false;m.rateLimited++;return false;}
   windowSamples++;
   var bytes=java.util.Arrays.copyOfRange(data,start,end);
   m.samples++;m.sampledBytes+=length;
   var same=false,skip=false;
   if(old){
    m.comparable++;
    same=java.util.Arrays.equals(old.bytes,bytes);
    if(same){m.repeated++;m.repeatedBytes+=length;}
    skip=!!mlogentBuildingObserverRef.buildingDedupEnabled&&same&&old.valid!==false&&!force&&now>=old.sentAt&&now-old.sentAt<mlogentBuildingObserverRef.buildingDedupRefreshMs;
    if(mlogentBuildingObserverRef.buildingDedupEnabled&&same&&!skip)m.forcedRefreshes++;
    m.cacheBytes-=old.bytes.length;
   }else{
    if(slots.length<64)slots.push(id);
    else{var victim=slots[cursor];m.cacheBytes-=cache[victim].bytes.length;
     delete cache[victim];slots[cursor]=id;cursor=(cursor+1)%64;}
   }
   cache[id]={bytes:bytes,at:now,sentAt:skip?old.sentAt:now};m.cacheBytes+=length;
   return skip;
  }catch(error){m.error=String(error);mlogentBuildingObserverRef.buildingObservationEnabled=false;mlogentBuildingObserverRef.buildingDedupEnabled=false;return false;}
  finally{var ms=(java.lang.System.nanoTime()-t)/1000000;
   m.calls++;m.totalMs+=ms;m.maxMs=Math.max(m.maxMs,ms);}
 };
})();
"""
