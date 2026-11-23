# Mlogent-Ops

Mlogent 的独立服务器维护项目。管理同步策略、性能实验、部署资源预算和故障留档。

## 职责边界

- 本项目：C 组视野分频、错峰、远处单位轮转、资源保护、流量/进程遥测、回退留档、systemd 配置和实验报告。
- Mlogent 主体：MCP/OAuth/知识库/编译与仿真，以及游戏世界的业务 API、运行器和休眠协议。
- 主体只保留可选扩展加载接口；未安装本项目时使用原版同步路径。运维模块不复制主体实现。

## 使用

需要 Python 3.10+；策略回归测试需要 Node.js。常规运行无第三方 Python 依赖。

```powershell
python -m pip install -e D:\Develop\Mlogent-Ops
$env:MLOGENT_ROOT = 'D:\Develop\MlogAgent'
python -m mlogent_ops.world_traffic --help
python tools/check.py
```

Mlogent 服务设置 `MLOGENT_OPS_ROOT=/opt/mlogent-ops` 后即可加载本项目。
运维服务设置 `MLOGENT_ROOT` 指向实际 Mlogent 发布目录，通过现有本机控制口取数，不发起唤醒。

## 当前实验配置

- C＋错峰＋远处单位六批轮转：视野内单位 200ms；状态/建筑调度 300ms；远处普通单位约 1.2 秒覆盖一轮；所有受控单位全图补发 100ms，仍遵守战争迷雾。
- 冲击反应堆热量低于 0.7 时走独立 500ms 优先通道，达到 0.7 时补发一次最终状态，再恢复普通建筑周期。仍遵守迷雾与软预算；过载时记录实际间隔，不保证绝对时限。
- 连续三次调度超过 100ms，或更新间隔超过 5 秒才因时间回退；建筑软切片保持 2ms。
- 主机可用内存低于 96MiB 持续 10 秒，或低于 64MiB 立即回退；堆使用超过 93%，或 JVM 交换超过 128MiB 也回退。
- 入服与优化策略保护上限统一为 8 人；这不是已经完成的 8 人负载压测结论。
- 平时仅内存滚动记录；保护回退时保存前 90 秒、后 30 秒，最多 20 份。正常数据不持续落盘。

部署与迁移方式见 `docs/deployment.md`。历史实验依据见 `reports/`；`experiments/legacy/` 是当时的一次性脚本，保留原始路径作参考，不是生产入口。

不得把 SSH 私钥、MCP/OAuth token、密码、聊天记录或连续采样原始文件提交到本仓库。
