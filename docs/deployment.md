# 独立部署

本项目与 Mlogent 分别维护源码与 Git 历史。示例安装目录：

- 运维项目：`/opt/mlogent-ops`
- Mlogent：`/opt/mlogent-releases/v1.10.0-worldsleep-20261122`
- 游戏运行数据：沿用 `/opt/mlogent/out/_world`，不搬动存档。
- 故障留档：`/var/log/mlogent-world-traffic/incidents/`
- 当前状态：`/run/mlogent-world-recorder/status.json`，位于 tmpfs。

## 游戏侧扩展

在 `mlogent-world.service` 的 drop-in 中设置：

```ini
[Service]
Environment=MLOGENT_OPS_ROOT=/opt/mlogent-ops
Environment=MLOG_WORLD_VIEWPORT_SYNC=experimental
Environment=MLOG_WORLD_FALLBACK_EVENT=/opt/mlogent/out/_world/aoi-fallback.json
```

Mlogent 的 `tools/world_network_policy.py` 只加载本包生成的脚本，不再持有策略实现。
可编辑安装本包，也可以用 `MLOGENT_OPS_ROOT` 指向包含 `mlogent_ops/` 的项目根。

已运行的休眠主管不会因 `daemon-reload` 自动获得新环境。为保证下一次唤醒也能加载，
在主体的 `out/_world/snapshot-profile.json` 中保留：

```json
{
  "mode": "experimental",
  "eventPath": "/opt/mlogent/out/_world/aoi-fallback.json",
  "opsRoot": "/opt/mlogent-ops"
}
```

当前游戏可以热加载新包生成的脚本；游戏服务无需因路径迁移重启。
`deploy/snapshot-profile.example.json` 还包含 `runningDescription`，用于配置
运行时服务器消息，保留颜色标记和真正的换行。修改运行配置后，下次唤醒会自动读取；
当前游戏可通过现有本机管理口热设置 `Administration.Config.desc`。

## 记录服务

安装 `deploy/mlogent-world-traffic.service`，并设置其 `MLOGENT_ROOT` 指向实际主体目录。
服务直接执行 `python -m mlogent_ops.world_traffic`；不再从主体 `tools/` 运行维护脚本。
只需重启记录服务。缺少握手或世界休眠时，取样失败会记为暂时不可用，不会唤醒世界。

## 回滚

把运行配置的 `mode` 设为 `native`，并在游戏中调用现有策略的 `restoreOriginal()`。
停用运维记录服务不影响游戏或 MCP 主服务。未安装运维扩展时，主体使用原版同步路径。
部署预算和防火墙脚本均归本项目；修改前核对当前主机、磁盘和端口。
防火墙脚本应安装为 `/etc/mlogent/world-sleep-firewall.sh`，资源预算辅助脚本
安装为 `/etc/mlogent/world-resource-budget.sh`，再由 systemd 引用安装副本。
这样游戏启动不依赖运维源码目录里的部署脚本是否仍在原位置。

历史对照结论在 `reports/`，不保留正常运行的连续遥测原始文件。
