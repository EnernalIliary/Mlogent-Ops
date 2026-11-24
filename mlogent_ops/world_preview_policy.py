"""Bound the remote preview list without changing a player's build queue."""

INSTALL_JS = r"""
(function(){
 var p=this._mcpSnapshotPolicy;
 if(!p)throw new Error('Snapshot policy is not installed');
 p.previewPlanLimit=500;
 p.previewPlansTrimmed=p.previewPlansTrimmed||0;
 p.limitPreviewPlans=function(){
  if(!Vars.state.isGame())return;
  for(var i=0;i<Groups.player.size();i++){
   var player=Groups.player.index(i);
   // Trim the receive assembly as well as the committed list. Native group
   // IDs, commit timing and empty-list clearing remain owned by the engine.
   var assembling=player.previewPlansAssembling;
   var current=player.previewPlansCurrent;
   if(assembling.size>p.previewPlanLimit){
    p.previewPlansTrimmed+=assembling.size-p.previewPlanLimit;
    assembling.truncate(p.previewPlanLimit);
   }
   if(current.size>p.previewPlanLimit){
    p.previewPlansTrimmed+=current.size-p.previewPlanLimit;
    current.truncate(p.previewPlanLimit);
    player.previewPlansDirty=true;
   }
  }
 };
})();
"""
