import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
  escapeHtml,
  fmt,
  renderApp,
  renderDashboard,
  renderDevices,
  renderStore,
  renderSecurity,
  renderAi,
  renderSettings,
  renderTutorial,
  renderPlans,
} from '../../custom_components/pv_manager/frontend/render.js';
import { STRINGS } from '../../custom_components/pv_manager/frontend/i18n.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');

const MODULES = [
  ['core', 'base', false, true],
  ['price_cost', 'energy', true, false],
  ['storage_grid', 'energy', true, false],
  ['thermal', 'devices', true, false],
  ['mobility_calendar', 'devices', true, false],
  ['forecast_learning', 'intelligence', true, true],
  ['what_if', 'intelligence', true, false],
  ['flexible_loads', 'devices', true, false],
  ['goals_reports', 'energy', true, false],
  ['presence_modes', 'comfort', true, false],
  ['maintenance_pv_health', 'safety', true, false],
  ['ventilation', 'comfort', true, false],
  ['energy_habits', 'intelligence', true, false],
  ['ev_wallbox_link', 'devices', true, false],
  ['security_terminal', 'safety', true, false],
].map(([module_id, category, optional, enabled]) => ({
  module_id,
  category,
  optional,
  enabled,
  name_de: `Modul ${module_id}`,
  name_en: `Module ${module_id}`,
  summary_de: `Beschreibung ${module_id}`,
  summary_en: `Description ${module_id}`,
  reason_de: 'Grund',
  reason_en: 'Reason',
}));

function baseState(overrides = {}) {
  return {
    language: 'de',
    theme: 'auto',
    tutorial_done: true,
    emergency_stop: false,
    settings: { grid_import_limit_w: 11000, grid_export_limit_w: 0, pv_peak_w: 0 },
    summary: {
      pv_w: 4200,
      grid_import_w: 0,
      grid_export_w: 1200,
      load_w: 3000,
      battery_charge_w: 0,
      battery_discharge_w: 0,
      battery_soc: 55,
      balance_ok: true,
    },
    forecast: {
      solar_kwh_next_24h: 24.5,
      consumption_kwh_next_24h: 12.1,
      confidence: 0.6,
      confidence_label: 'medium',
      solar: [{ start: '2026-06-01T08:00:00Z', expected_kwh: 3.2 }],
      consumption: [{ start: '2026-06-01T08:00:00Z', expected_kwh: 1.1 }],
    },
    privacy: { external_active: false, label_de: 'GRÜN: Lokal – keine externe KI-Datenübertragung.', label_en: 'GREEN: Local.', settings: { mode: 'local_only' } },
    security: { overall: 'info', score: 100, summary_de: 'Alles in Ordnung.', summary_en: 'All good.', findings: [] },
    terminal: { level: 'observe', reaction: '30s' },
    devices: [],
    modules: MODULES,
    plans: [],
    audit: [],
    ai: { provider_id: 'local_rules', enabled: false, api_key_set: false, report_interval: 'daily', last_report: null },
    ...overrides,
  };
}

test('escapeHtml neutralizes markup', () => {
  assert.equal(escapeHtml('<script>alert(1)</script>'), '&lt;script&gt;alert(1)&lt;/script&gt;');
  assert.equal(escapeHtml("a'b\"c"), 'a&#39;b&quot;c');
});

test('fmt never renders NaN', () => {
  assert.equal(fmt(undefined), '–');
  assert.equal(fmt(Number.NaN), '–');
  assert.equal(fmt(1234.5, 1), '1.234,5');
});

test('dashboard shows a green privacy banner in local mode', () => {
  const html = renderDashboard(baseState(), 'de');
  assert.match(html, /pm-privacy-banner green/);
  assert.match(html, /GRÜN/);
  assert.doesNotMatch(html, /pm-privacy-banner red/);
});

test('dashboard marks external AI bold and red', () => {
  const state = baseState({
    privacy: { external_active: true, label_de: 'ROT: Externe KI aktiv.', label_en: 'RED: external AI active.', settings: {} },
  });
  const html = renderDashboard(state, 'de');
  assert.match(html, /pm-privacy-banner red/);
  assert.match(html, /ROT/);
});

test('store renders all 15 module cards with descriptions', () => {
  const html = renderStore(baseState(), 'de');
  for (const module of MODULES) {
    assert.match(html, new RegExp(module.name_de));
  }
  assert.equal((html.match(/pm-card/g) || []).length, 15);
  assert.match(html, /Grundfunktion/);
});

test('charging plans show names instead of raw entity ids', () => {
  const state = baseState({
    plans: [
      {
        vehicle_id: 'sensor.id4_soc',
        wallbox_id: 'sensor.wallbox_power',
        vehicle_name: 'Auto ID4',
        wallbox_name: 'Garage Wallbox',
        feasible: true,
        planned_energy_kwh: 22.4,
        solar_energy_kwh: 17.9,
        grid_energy_kwh: 4.5,
        reasons_de: ['Grund'],
        reasons_en: ['Reason'],
        warnings: [],
      },
    ],
  });
  const html = renderPlans(state, 'de');
  assert.match(html, /Garage Wallbox/);
  assert.match(html, /Auto ID4/);
  assert.doesNotMatch(html, /<h3>sensor\.wallbox_power<\/h3>/);
});

test('a plan without names still falls back to the entity id', () => {
  const state = baseState({
    plans: [
      {
        wallbox_id: 'sensor.wallbox_power',
        feasible: false,
        planned_energy_kwh: 0,
        solar_energy_kwh: 0,
        grid_energy_kwh: 0,
        warnings: [],
      },
    ],
  });
  const html = renderPlans(state, 'de');
  assert.match(html, /sensor\.wallbox_power/);
  assert.doesNotMatch(html, /undefined/);
});

test('devices never claim automation for unverified devices', () => {
  const state = baseState({
    devices: [
      {
        device_id: 'switch.pool',
        name: 'Poolpumpe',
        kind: 'flexible_load',
        automation_allowed: false,
        reading: { value: 0, unit: 'W', age_seconds: 5, fresh: true },
        decision: { reason_code: 'not_enabled_by_user', message_de: 'Noch nicht freigegeben.', message_en: 'Not enabled.' },
        warnings: ['limits_not_verified'],
        limits: {},
      },
    ],
  });
  const html = renderDevices(state, 'de', []);
  assert.match(html, /Sicher beobachtet/);
  assert.match(html, /data-action="automode"/);
  assert.doesNotMatch(html, /data-action="manual"/);
});

test('discovery candidates expose a kind selector and confirm button', () => {
  const html = renderDevices(baseState(), 'de', [
    { entity_id: 'sensor.pv_power', name: 'PV Power', kind: 'pv', score: 0.8, capabilities: ['measure_power'] },
  ]);
  assert.match(html, /data-kind-for="sensor.pv_power"/);
  assert.match(html, /data-action="register"/);
});

test('security page shows repairs and never hides findings', () => {
  const state = baseState({
    security: {
      overall: 'critical',
      score: 50,
      summary_de: '1 kritischer Hinweis.',
      summary_en: '1 critical finding.',
      findings: [
        {
          code: 'module_error',
          severity: 'critical',
          module_id: 'forecast_learning',
          title_de: 'Modul Fehler',
          title_en: 'Module error',
          detail_de: 'Sensor fehlt',
          detail_en: 'Sensor missing',
          repair_de: 'Sensor prüfen',
          repair_en: 'Check sensor',
        },
      ],
    },
  });
  const html = renderSecurity(state, 'de');
  assert.match(html, /Kritisch/);
  assert.match(html, /Sensor prüfen/);
  assert.match(html, /data-action="estop"/);
});

test('AI page always states that the AI cannot control devices', () => {
  const html = renderAi(baseState(), 'de', [
    { provider_id: 'local_rules', name_de: 'Lokale Regeln', suggested: true, local: true },
    { provider_id: 'groq', name_de: 'Groq', suggested: true, local: false },
  ]);
  assert.match(html, /keine Schaltbefehle/);
  assert.match(html, /Lokale Regeln/);
  assert.match(html, /Groq/);
  assert.match(html, /data-action="preview-ai"/);
});

test('tutorial has four steps and can be skipped', () => {
  const html = renderTutorial('de', 0);
  assert.equal((html.match(/<i /g) || []).length, 4);
  assert.match(html, /data-action="tutorial-skip"/);
});

test('settings explains that deletion removes PV Manager data only', () => {
  const html = renderSettings(baseState(), 'de');
  assert.match(html, /Fremde Home-Assistant-Geräte bleiben unangetastet/);
  assert.match(html, /data-action="tutorial-start"/);
});

test('app renders every navigation view without throwing', () => {
  const state = baseState();
  for (const view of ['dashboard', 'devices', 'store', 'plans', 'security', 'ai', 'audit', 'settings']) {
    const html = renderApp(state, view, 'de');
    assert.ok(html.length > 200, view);
    assert.doesNotMatch(html, /undefined/);
  }
});

test('panel does not use Lovelace card APIs', () => {
  const panel = readFileSync(join(root, 'custom_components', 'pv_manager', 'frontend', 'pv-manager-panel.js'), 'utf8');
  assert.doesNotMatch(panel, /hui-[a-z]/);
  assert.doesNotMatch(panel, /window\.loadCardHelpers/);
  assert.doesNotMatch(panel, /customElements\.get\('hui/);
});

// --- Language completeness ---------------------------------------------
// The UI promises a full English translation. These tests exist because
// hardcoded German strings can silently bypass the translation table.

test('German and English contain exactly the same keys, none empty', () => {
  const de = Object.keys(STRINGS.de).sort();
  const en = Object.keys(STRINGS.en).sort();
  assert.deepEqual(en, de, 'translation tables drifted apart');
  for (const [key, value] of Object.entries(STRINGS.de)) {
    assert.ok(value && value.length > 0, `empty German value for ${key}`);
  }
  for (const [key, value] of Object.entries(STRINGS.en)) {
    assert.ok(value && value.length > 0, `empty English value for ${key}`);
  }
});

test('number formatting follows the selected language', () => {
  assert.equal(fmt(1234.5, 1, 'de'), '1.234,5');
  assert.equal(fmt(1234.5, 1, 'en'), '1,234.5');
  // Defaults keep backwards compatibility with earlier call sites.
  assert.equal(fmt(1234.5, 1), '1.234,5');
});

test('every confirmation dialog is translated', () => {
  const panel = readFileSync(
    join(root, 'custom_components', 'pv_manager', 'frontend', 'pv-manager-panel.js'),
    'utf8',
  );
  const calls = panel.match(/window\.confirm\([^)]*/g) || [];
  // Switching on, emergency stop, external AI, log deletion and automation
  // release must all ask first.
  assert.ok(calls.length >= 5, `expected at least 5 confirmations, found ${calls.length}`);
  for (const call of calls) {
    assert.match(call, /window\.confirm\(t\(/, `untranslated confirmation dialog: ${call}`);
  }
});

test('no user-facing German text hides outside the translation table', () => {
  // The guard is deliberately strict: German words must either live in
  // i18n.js or sit on a line that selects German explicitly. It cannot see a
  // hardcoded string sharing a line with an unrelated t() call, so it reduces
  // the problem rather than proving it absent.
  const germanOnly =
    /[äöüßÄÖÜ]|\bGespeichert\b|\bAutomatik\b|\bNot-Aus\b|\bEinschalten\b|\bAusschalten\b|\bGrenzen\b|\bGrenzwerte\b|\bSuche\b/;
  const frontendDir = join(root, 'custom_components', 'pv_manager', 'frontend');
  const offenders = [];

  for (const name of ['render.js', 'pv-manager-panel.js', 'styles.js']) {
    const lines = readFileSync(join(frontendDir, name), 'utf8').split('\n');
    lines.forEach((line, index) => {
      if (!germanOnly.test(line)) return;
      // Comments are never shown to a user.
      if (/^\s*(\/\*|\*|\/\/)/.test(line)) return;
      if (line.includes("lang === 'de'")) return;
      if (line.includes('t(lang,') || line.includes('t(this._lang,')) return;
      offenders.push(`${name}:${index + 1}: ${line.trim()}`);
    });
  }

  assert.deepEqual(offenders, [], `hardcoded German text:\n${offenders.join('\n')}`);
});

test('English views contain no German leftovers', () => {
  const germanOnly = [
    'Sicher beobachtet',
    'Automatik',
    'Not-Aus',
    'Einschalten',
    'Ausschalten',
    'Gespeichert',
    'Grenzen',
    'Grenzwerte',
    'Suche läuft',
  ];
  const state = baseState({
    language: 'en',
    privacy: { external_active: false, label_de: 'GRÜN: Lokal.', label_en: 'GREEN: Local.', settings: {} },
    security: { overall: 'info', score: 100, summary_de: 'Alles in Ordnung.', summary_en: 'All good.', findings: [] },
  });
  for (const view of ['dashboard', 'devices', 'store', 'plans', 'security', 'ai', 'audit', 'settings']) {
    const html = renderApp(state, view, 'en');
    for (const word of germanOnly) {
      assert.ok(!html.includes(word), `"${word}" leaked into the English ${view} view`);
    }
    assert.doesNotMatch(html, /undefined/, `undefined leaked into the English ${view} view`);
  }
});

test('device limits are shown as concrete values', () => {
  const state = baseState({
    devices: [
      {
        device_id: 'switch.boiler',
        name: 'Boiler',
        kind: 'hot_water',
        controllable: true,
        automation_allowed: true,
        reading: { value: 1800, unit: 'W', age_seconds: 5, fresh: true },
        decision: { reason_code: 'ok', message_de: 'ok', message_en: 'ok' },
        warnings: [],
        limits: {
          verified: true,
          max_power_w: 3000,
          max_energy_kwh_per_day: 6,
          phase_limit_a: 16,
          min_soc: 0,
          max_soc: 0,
          min_temperature_c: 45,
          max_temperature_c: 60,
        },
      },
    ],
  });
  const html = renderDevices(state, 'de', []);
  assert.match(html, /Max\. Leistung ≤ 3\.000 W/);
  assert.match(html, /Max\. Energie pro Tag ≤ 6,00 kWh/);
  assert.match(html, /Phasengrenze ≤ 16,0 A/);
  assert.match(html, /Temperatur 45–60 °C/);
  assert.match(html, /Grenzen bestätigt/);
});

test('unverified limits are never presented as confirmed values', () => {
  const state = baseState({
    devices: [
      {
        device_id: 'switch.pool',
        name: 'Pool',
        kind: 'pool',
        controllable: true,
        automation_allowed: false,
        reading: { value: 0, unit: 'W', age_seconds: 5, fresh: true },
        decision: { reason_code: 'not_enabled_by_user', message_de: 'x', message_en: 'x' },
        warnings: ['limits_not_verified'],
        limits: { verified: false },
      },
    ],
  });
  const html = renderDevices(state, 'de', []);
  assert.match(html, /Keine Grenzwerte hinterlegt/);
  assert.match(html, /Grenzen noch nicht bestätigt/);
  assert.doesNotMatch(html, /Grenzen bestätigt/);
});
