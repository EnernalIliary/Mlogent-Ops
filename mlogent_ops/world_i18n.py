"""Per-recipient Chinese/English messages; no network or Kotlin compilation."""
import json

MESSAGES = {
    'afk.limited': ('[gray]已自动进入 AFK 低频同步。聊天、建造或控制单位即可自动恢复。[]', '[gray]AFK low-frequency sync is active. Chat, build or control units to resume automatically.[]'),
    'afk.here': ('我在，恢复同步', 'I am here — restore sync'),
    'afk.stay': ('保持 AFK 低频', 'Stay in AFK mode'),
    'afk.title': ('AFK 确认', 'AFK check'),
    'afk.prompt': ('检测到长时间未操作。点击按钮恢复同步；不确认只会降低同步频率，不会踢出。', 'No recent activity detected. Confirm to restore normal sync. No answer only reduces sync frequency; it does not kick you.'),
    'afk.restored': ('[green]检测到操作，已退出 AFK 并恢复同步。[]', '[green]Activity detected. AFK cleared and synchronization resumed.[]'),
    'afk.disabled': ('AFK 验证当前未启用。', 'AFK verification is not currently enabled.'),
    'afk.pending': ('请回答当前验证，或等待本次验证结束后重试。', 'Please answer the current check, or retry after it ends.'),
    'poly.title': ('polyAI 验证', 'polyAI verification'),
    'poly.prompt': ('请勿使用 polyAI 自动协助建造脚本。\n请在 30 秒内回答下方问题。答错、关闭或超时会被踢出；关闭脚本后可重新连接。', 'Do not use polyAI automatic cooperative-building scripts.\nAnswer the question below within 30 seconds. A wrong answer, closing the check or timeout will disconnect you. Disable the script before reconnecting.'),
    'poly.kick': ('polyAI 验证未通过（{reason}）。自动跟随建造可能丢失建筑配置；请关闭自动协助建造脚本后重新连接。', 'polyAI verification failed ({reason}). Automatic cooperative building may lose building configuration. Disable the script before reconnecting.'),
    'poly.timeout': ('超时', 'timeout'),
    'poly.closed': ('关闭验证', 'check closed'),
    'poly.wrong-answer': ('答案错误', 'wrong answer'),
    'poly.passed': ('[green]polyAI 验证通过，5 分钟内不重复验证。请确认自动协助脚本不会丢失建筑配置。[]', '[green]polyAI verification passed. No repeat check for 5 minutes. Ensure automatic building scripts do not lose building configuration.[]'),
    'notice.afk': ('[accent][AFK提示][] 长时间未操作会自动进入 AFK 并降低同步频率。聊天、建造或控制单位即可自动恢复。', '[accent][AFK][] Inactivity enables AFK low-frequency sync. Chat, build or control units to resume automatically.'),
    'notice.poly': ('[accent][polyAI提示][] 请勿使用 polyAI。触发验证后请在 30 秒内回答，否则会被踢出。', '[accent][polyAI][] Do not use polyAI. If a verification prompt appears, answer within 30 seconds to avoid disconnection.'),
    'notice.mcp': ('[accent][MCP提示][] 输入 /mcp 打开 Mlogent 网站，查看接入指南和使用示例。语言：/language zh 或 /language en。', '[accent][MCP][] Use /mcp to open Mlogent connection guides and examples. Language: /language zh or /language en.'),
    'language.set': ('[green]Mlogent 语言已设为简体中文。Wayzer 命令可另用 /lang zh。[]', '[green]Mlogent language set to English. For Wayzer commands, also use /lang en.[]'),
    'language.help': ('语言跟随客户端。手动设置：/language zh、/language en；恢复自动：/language auto。Wayzer：/lang zh 或 /lang en。', 'Language follows your client. Override: /language zh or /language en; reset: /language auto. Wayzer: /lang zh or /lang en.'),
}

INSTALL_JS = r"""
(function(){
 var mlogentLanguageRoot=this;
 var mlogentLanguageHelper=mlogentLanguageRoot._mlogentI18n;
 if(!mlogentLanguageHelper)mlogentLanguageHelper=mlogentLanguageRoot._mlogentI18n={overrides:{}};
 mlogentLanguageHelper.catalog=CATALOG;
 mlogentLanguageHelper.language=function(player){
  var locale='zh';
  try{
   var id=String(player.uuid()),saved=mlogentLanguageHelper.overrides[id];
   if(!saved&&typeof Core!=='undefined'&&Core.settings)saved=String(Core.settings.getString('mlogent.language.'+id,''));
   locale=saved||String(player.locale||'zh');
  }catch(ignore){locale=String(player&&player.locale||'zh');}
  return locale.toLowerCase().indexOf('zh')===0?'zh':'en';
 };
 mlogentLanguageHelper.text=function(player,key,values){
  var pair=mlogentLanguageHelper.catalog[key];if(!pair)return key;
  var text=pair[mlogentLanguageHelper.language(player)==='zh'?0:1];
  if(values)text=text.replace(/\{([a-zA-Z]+)\}/g,function(all,name){return values[name]===undefined?all:String(values[name]);});
  return text;
 };
 if(typeof Vars!=='undefined'&&Vars.netServer&&Vars.netServer.clientCommands&&typeof JavaAdapter!=='undefined'){
  var commands=Vars.netServer.clientCommands;
  commands.removeCommand('language');
  commands.register('language','[zh/en/auto]','Language / 语言',new JavaAdapter(Packages.arc.util.CommandHandler$CommandRunner,{
   accept:function(args,player){
    if(!player)return;
    var choice=args.length?String(args[0]).toLowerCase():'';
    if(choice==='zh'||choice==='en'||choice==='auto'){
     var id=String(player.uuid());
     if(choice==='auto')delete mlogentLanguageHelper.overrides[id];else mlogentLanguageHelper.overrides[id]=choice;
     if(typeof Core!=='undefined'&&Core.settings){
      if(choice==='auto')Core.settings.remove('mlogent.language.'+id);else Core.settings.put('mlogent.language.'+id,choice);
      Core.settings.manualSave();
     }
     player.sendMessage(mlogentLanguageHelper.text(player,'language.set'));
    }else player.sendMessage(mlogentLanguageHelper.text(player,'language.help'));
   }
  }));
 }
})();
""".replace('CATALOG', json.dumps(MESSAGES, ensure_ascii=True))
