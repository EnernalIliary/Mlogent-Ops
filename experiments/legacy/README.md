# 历史一次性脚本

这些脚本从 Mlogent 的工作区迁入，用于保存当时实验过程。它们没有注册为生产入口，
其中的发布目录、日期、控制口客户端和导入路径对应当时环境，不能直接用于新部署。

日常监控使用 `python -m mlogent_ops.world_traffic`，被动压力采样使用
`python -m mlogent_ops.world_interest_diagnostics`。重新执行历史实验前，应基于
`mlogent_ops.world_api`、当前发布目录和当前保护线重新准备有界的实验入口。
这些脚本不会被安装为命令，也不会在包导入、服务启动或游戏唤醒时执行。
