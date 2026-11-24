# Changelog

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
