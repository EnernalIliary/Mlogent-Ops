# Changelog

## Unreleased

- 受控单位使用单一同步路径，避免普通快照与100ms补发重复；失败与原版回退保留接管路径。
- 根据世界服务CPU配额、主机可用资源、帧耗时和堆占用限制自适应最高频率；迟滞恢复、监测过期回退与每玩家带宽限制共同生效。
- 将原生 `/push` 请求持久化投递到服务器 Agent 收件箱，移除旧中继的自动群发路径；投递失败保留原文件重试。

## 0.2.1 — 2026-11-24

- Use a module-specific language-helper reference so later startup loops cannot
  overwrite callback state under the live Rhino runtime.

## 0.2.0 — 2026-11-24

- Add bounded building observation and optional byte-identical deduplication.
- Add experimental enemy-building interest filtering and per-player adaptive
  bandwidth feedback with a default target of 200 kbps, without a hard cap.
- Add AFK confirmation, separate polyAI verification and rotating notices.
- Localize Mlogent player messages in Simplified Chinese and English, with
  `/language zh|en|auto`; Wayzer retains its independent `/lang` preference.
- Extend incident telemetry and policy regression coverage. Preserve native
  synchronization fallback, fog checks and bounded memory use.
- Include deployment files, tests and historical experiment reports in the
  standalone release archive. Historical reports describe their observation date.

## 0.1.0

- Extract server operations, synchronization experiments and incident recording
  from the main Mlogent repository.
