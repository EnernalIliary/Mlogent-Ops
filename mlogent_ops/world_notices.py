"""One rotating rule/help notice per interval, only with connected players."""

INSTALL_JS = r"""
(function(){
 var mlogentNoticeRootRef=this;
 if(!mlogentNoticeRootRef._mlogentNotices)mlogentNoticeRootRef._mlogentNotices={index:0,nextAt:0};
 var mlogentNoticePolicyRef=mlogentNoticeRootRef._mlogentNotices;
 mlogentNoticePolicyRef.enabled=false;mlogentNoticePolicyRef.intervalMs=300000;mlogentNoticePolicyRef.error=null;
 mlogentNoticePolicyRef.tick=function(now){
  var current=mlogentNoticeRootRef._mcpSnapshotPolicy;
  var online=false;
  for(var i=0;i<Groups.player.size();i++){var con=Groups.player.index(i).con;
   if(con&&con.hasConnected&&con.isConnected()){online=true;break;}}
  if(!mlogentNoticePolicyRef.enabled||!online||!Vars.state.isGame()){
   mlogentNoticePolicyRef.nextAt=now+mlogentNoticePolicyRef.intervalMs;return;
  }
  if(!mlogentNoticePolicyRef.nextAt){mlogentNoticePolicyRef.nextAt=now+mlogentNoticePolicyRef.intervalMs;return;}
  if(now<mlogentNoticePolicyRef.nextAt)return;
  mlogentNoticePolicyRef.nextAt=now+mlogentNoticePolicyRef.intervalMs;
  // Find one eligible message, never catch up multiple missed intervals.
  for(var tried=0;tried<3;tried++){
   var index=mlogentNoticePolicyRef.index++%3,text=null;
   if(index===0&&current&&current.afkEnabled&&current.interestEnabled&&!Vars.state.rules.pvp)
    text='notice.afk';
   if(index===1&&current&&current.polyEnabled)
    text='notice.poly';
   if(index===2)
    text='notice.mcp';
   if(text){for(var j=0;j<Groups.player.size();j++){var receiver=Groups.player.index(j);if(receiver.con&&receiver.con.hasConnected&&receiver.con.isConnected())receiver.sendMessage(mlogentNoticeRootRef._mlogentI18n.text(receiver,text));}mlogentNoticePolicyRef.sent=(mlogentNoticePolicyRef.sent||0)+1;return;}
  }
 };
 if(!mlogentNoticeRootRef._mlogentNoticeHook){
  var last=0;
  Events.run(Packages.mindustry.game.EventType.Trigger.update,function(){
   var now=java.lang.System.currentTimeMillis();if(now-last<1000)return;last=now;
   var current=mlogentNoticeRootRef._mlogentNotices;
   try{if(current&&current.tick)current.tick(now);}
   catch(error){if(current){current.error=String(error);current.enabled=false;}}
  });
  mlogentNoticeRootRef._mlogentNoticeHook=true;
 }
})();
"""

from .world_i18n import INSTALL_JS as I18N_INSTALL_JS
INSTALL_JS = I18N_INSTALL_JS + INSTALL_JS
