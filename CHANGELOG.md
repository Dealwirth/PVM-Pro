# Changelog

All notable changes are documented here. The format follows Keep a Changelog
and the project uses semantic versioning.

## [0.1.0] - 2026-09-24

### Added

- HACS-ready Home Assistant integration `pv_manager` with config flow and
  options flow.
- Own custom sidebar panel, not a Lovelace dashboard, with a first-run
  tutorial in German and English.
- Internal module store with 15 cards: core, price & cost, storage & grid,
  thermal flexibility, mobility & calendar, forecast & learning, what-if,
  flexible loads, goals/reports/comfort, presence & special modes,
  maintenance & PV health, ventilation, energy habits, car–wallbox linking and
  the security terminal.
- Automatic device discovery from Home Assistant entity and device metadata
  with a manual fallback and explicit confirmation before automation.
- Canonical power/energy normalization for signed net meters, import/export
  meters, separate values and import-only meters.
- Fail-safe fallback engine: unknown, stale, contradictory or unverified data
  blocks automation instead of guessing.
- Deterministic constraint engine for grid, phase, device, energy, comfort,
  state-of-charge and user limits.
- Explainable consumption baseline and solar forecast with confidence values.
- EV charging planner with calendar deadlines, solar priority, optional grid
  charging and hard-limit clamping.
- Bounded calibration/learning runs for switch entities with time, power,
  energy, grid-headroom and abort limits.
- Optional security terminal with observe/assist/intervene levels, module
  input/output contract checks, repeated notifications and repair guidance.
- Optional AI advice with a provider catalogue: local rules, local
  OpenAI-compatible models, Groq (suggested cloud provider) and other
  OpenAI-compatible providers.
- Privacy engine with one-time aliases, payload validation, forbidden-key
  detection, preview before sending and a bold red external-AI indicator.
- Audit log with automatic redaction and JSON/CSV export.
- Sensors and binary sensors for energy, forecast, safety and privacy state.
- 208 tests: 119 core, 54 runtime and AI transport, 13 contract checks and
  22 frontend rendering tests. The repository is linted and formatted with ruff
  in CI.
- Final safety gate for every explicit device command: switching off is always
  a safe stop, switching on requires confirmed limits and grid headroom.
- Complete English coverage: every dialog, status label and number format
  follows the selected language. The translation tables are compared by tests,
  and confirmations, including the external-AI consent prompt, are checked to
  run through the translation table instead of hardcoded text.
- Device limits are shown as concrete values (power, daily energy, phase,
  state of charge, temperature) next to the verification badge, so a user can
  read what was agreed instead of trusting a label.
- The standalone preview now renders with the real colour palette; previously
  the design tokens only resolved inside the shadow root, which silently turned
  badges, charts and banners transparent.
- Fixed a crash that broke device registration and every device list:
  `DeviceLimits` uses slots and therefore has no `__dict__`, so building the
  device snapshot raised `AttributeError` as soon as one device existed.
- Home Assistant notifications now follow the selected language; they used to
  be German only, including on an English system.
- Charging plans carry display names, so the panel shows "Garage Wallbox"
  instead of a raw entity id such as `sensor.wallbox_power`.
- The runtime layer (entity state, safety gate, audit log, persistence) is now
  covered by tests that need no Home Assistant installation, and the core
  module cannot be disabled, stale readings block switching on while switching
  off stays a safe stop, and the API key is never written to storage.
- Contract tests link the panel's WebSocket commands and the service schemas to
the implementation, and compare every version statement and repository URL.
- The preview harness renders both languages with the real colour palette, so
  the English translation can be reviewed visually, not only by tests.
- The AI transport is covered by tests that inspect the real outgoing HTTP
  request: no device names, entity ids, calendar contents, coordinates or keys
  are sent, the API key only travels in the `Authorization` header, a local
  provider never receives it, and local-only mode produces no device context at
  all. A rejected response is truncated instead of echoed in full.
- The AI advisory follows the selected language end to end: system prompt,
  user prompt, the payload's own locale field and the local rules provider's
  answer. Previously every prompt was German, so an English user was answered
  in German.
- Added `.gitattributes` and `.editorconfig`, so line endings and indentation
  are identical for every contributor.
