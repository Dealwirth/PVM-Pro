/* Build a standalone visual preview from the real render functions.
 *
 * Usage: node scripts/build_preview.mjs
 * Output: preview/pv-manager-preview.html (generated, not committed)
 *
 * This preview uses the production render.js and styles.js, so it verifies the
 * actual UI output without needing a running Home Assistant instance.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { STYLES } from '../custom_components/pv_manager/frontend/styles.js';
import { renderApp } from '../custom_components/pv_manager/frontend/render.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

/* Both languages are spelled out. Copying the German text into the English
 * fields would make the preview look correct while proving nothing. */
const MODULES = [
  ['core', 'PV-Manager Grundsystem', 'PV Manager core', 'base', false, true, 'Immer aktiv. Zeigt PV, Verbrauch, Netzbezug und Einspeisung. Erkennt Geräte, schützt Grenzen und verhindert unsinnige Automatik.', 'Always active. Shows PV, consumption, grid import and export. Detects devices, protects limits and prevents pointless automation.'],
  ['price_cost', 'Preis & Kosten', 'Price & cost', 'energy', true, true, 'Nutzt Strompreise für günstige Zeiten und verhindert teure Überraschungen mit einem Kostenlimit.', 'Uses electricity prices for cheap hours and avoids costly surprises with a spending limit.'],
  ['storage_grid', 'Speicher & Netz', 'Storage & grid', 'energy', true, false, 'Entscheidet über Speichern, Nutzen und Einspeisen und überwacht Anschluss- und Phasengrenzen.', 'Decides on storing, using and exporting, and watches connection and phase limits.'],
  ['thermal', 'Thermische Flexibilität', 'Thermal flexibility', 'devices', true, false, 'Plant Wärmepumpe und Warmwasser nur innerhalb von Komfort- und Hygienegrenzen.', 'Schedules heat pump and hot water only within comfort and hygiene limits.'],
  ['mobility_calendar', 'Mobilität & Kalender', 'Mobility & calendar', 'devices', true, true, 'Liest Abfahrten und wiederkehrende Fahrten für eine sichere Ladeplanung.', 'Reads departures and recurring trips for safe charging plans.'],
  ['forecast_learning', 'Prognose & Lernen', 'Forecast & learning', 'intelligence', true, true, 'Berechnet Verbrauch und Solarproduktion und erlaubt begrenzte Lernläufe.', 'Estimates consumption and solar production and allows bounded learning runs.'],
  ['what_if', 'Was wäre wenn?', 'What if?', 'intelligence', true, false, 'Zeigt vorab, was ein späteres oder schnelleres Laden bewirken würde.', 'Shows in advance what charging later or faster would change.'],
  ['flexible_loads', 'Flexible Geräte', 'Flexible loads', 'devices', true, false, 'Plant Waschmaschine, Trockner, Geschirrspüler, Pumpen und Bewässerung.', 'Schedules washing machine, dryer, dishwasher, pumps and irrigation.'],
  ['goals_reports', 'Ziele, Berichte & Komfort', 'Goals, reports & comfort', 'energy', true, false, 'Zeigt Monatsziele, Eigenstrom, CO₂ und Komfortbereiche in einfacher Sprache.', 'Shows monthly goals, self-consumption, CO₂ and comfort ranges in plain language.'],
  ['presence_modes', 'Anwesenheit & Sondermodi', 'Presence & special modes', 'comfort', true, false, 'Urlaub, Eco, Gast und Anwesenheit reduzieren Automatik sinnvoll.', 'Holiday, eco, guest and presence settings sensibly reduce automation.'],
  ['maintenance_pv_health', 'Wartungsassistent & PV-Zustand', 'Maintenance & PV health', 'safety', true, false, 'Erinnert an Wartung und erkennt auffällige Abweichungen bei PV und Verbrauchern.', 'Reminds about maintenance and spots unusual deviations in PV and loads.'],
  ['ventilation', 'Lüftungssteuerung', 'Ventilation control', 'comfort', true, false, 'Steuert eine unterstützte Lüftung nur mit gültigen Sensoren und Komfortgrenzen.', 'Controls assisted ventilation only with valid sensors and comfort limits.'],
  ['energy_habits', 'Energie-Gewohnheiten', 'Energy habits', 'intelligence', true, false, 'Erkennt wiederkehrende Muster und nutzt sie erst nach Bestätigung.', 'Detects recurring patterns and only uses them after confirmation.'],
  ['ev_wallbox_link', 'Auto–Wallbox-Verknüpfung', 'Car–wallbox linking', 'devices', true, true, 'Ordnet Autos und Wallboxen eindeutig zu, erlaubt priorisiertes und manuelles Laden.', 'Links cars and wallboxes unambiguously and allows prioritised and manual charging.'],
  ['security_terminal', 'Sicherheitsterminal', 'Security terminal', 'safety', true, true, 'Überwacht dauerhaft Module, Grenzen, Sensoren, Fehler und Datenschutz. Die KI berät nur.', 'Continuously monitors modules, limits, sensors, faults and privacy. The AI only advises.'],
].map(([module_id, name_de, name_en, category, optional, enabled, summary_de, summary_en]) => ({
  module_id,
  name_de,
  name_en,
  summary_de,
  summary_en,
  reason_de: 'Mehr Kontrolle, Sicherheit und Komfort im Alltag.',
  reason_en: 'More control, safety and comfort in everyday life.',
  category,
  optional,
  enabled,
}));

const state = {
  language: 'de',
  theme: 'auto',
  tutorial_done: true,
  emergency_stop: false,
  settings: { grid_import_limit_w: 11000, grid_export_limit_w: 0, pv_peak_w: 9800 },
  terminal: { level: 'assist', reaction: 'immediate' },
  summary: {
    pv_w: 6120,
    grid_import_w: 340,
    grid_export_w: 0,
    load_w: 4350,
    battery_charge_w: 2100,
    battery_discharge_w: 0,
    battery_soc: 68,
    balance_ok: true,
  },
  forecast: {
    solar_kwh_next_24h: 38.4,
    consumption_kwh_next_24h: 17.2,
    confidence: 0.62,
    confidence_label: 'medium',
    solar: Array.from({ length: 14 }, (_, index) => ({ start: `2026-09-24T${String(6 + index).padStart(2, '0')}:00:00Z`, expected_kwh: Math.max(0, Math.sin((index / 14) * Math.PI) * 5.2) })),
    consumption: Array.from({ length: 14 }, () => ({ start: '2026-09-24T06:00:00Z', expected_kwh: 1.1 })),
  },
  privacy: {
    external_active: false,
    label_de: 'GRÜN: Lokal – keine externe KI-Datenübertragung.',
    label_en: 'GREEN: Local.',
    settings: { mode: 'local_only' },
  },
  security: {
    overall: 'warning',
    score: 84,
    summary_de: '1 Warnung. Das System läuft, benötigt aber Aufmerksamkeit.',
    summary_en: 'One warning.',
    findings: [
      {
        code: 'stale_reading',
        severity: 'warning',
        module_id: 'core',
        title_de: 'Daten von Netz-Leistung sind veraltet',
        title_en: 'Grid power data is stale',
        detail_de: 'Der Wert ist 420 Sekunden alt. Automatik für betroffene Geräte ist pausiert.',
        detail_en: 'The value is 420 seconds old.',
        repair_de: 'Sensor, Verbindung oder Energiezähler prüfen.',
        repair_en: 'Check sensor, connection or meter.',
      },
    ],
  },
  devices: [
    {
      device_id: 'sensor.pv_generation',
      name: 'PV-Erzeugung',
      kind: 'pv',
      automation_allowed: true,
      controllable: false,
      capabilities: ['measure_power'],
      reading: { value: 6120, unit: 'W', age_seconds: 4, fresh: true },
      decision: { reason_code: 'ok', message_de: 'Automatik freigegeben, alle Prüfungen bestanden.', message_en: 'ok' },
      warnings: [],
      limits: { verified: true, max_power_w: 12000 },
    },
    {
      device_id: 'switch.pool_pumpe',
      name: 'Poolpumpe',
      kind: 'flexible_load',
      automation_allowed: false,
      controllable: true,
      capabilities: ['switch', 'measure_power'],
      reading: { value: 0, unit: 'W', age_seconds: 12, fresh: true },
      decision: { reason_code: 'not_enabled_by_user', message_de: 'Automatik wurde noch nicht freigegeben.', message_en: 'Not enabled.' },
      warnings: ['limits_not_verified'],
      limits: { verified: false, max_power_w: 0 },
    },
    {
      device_id: 'sensor.wallbox_power',
      name: 'Garage Wallbox',
      kind: 'ev_charger',
      automation_allowed: true,
      controllable: false,
      capabilities: ['set_power', 'measure_power', 'measure_soc'],
      reading: { value: 4200, unit: 'W', age_seconds: 3, fresh: true },
      decision: { reason_code: 'ok', message_de: 'Automatik freigegeben, alle Prüfungen bestanden.', message_en: 'ok' },
      warnings: [],
      limits: { verified: true, max_power_w: 11000 },
    },
    {
      // Controllable device with automation allowed: shows both switch-off
      // (always a safe stop) and switch-on (needs confirmed limits).
      device_id: 'switch.warmwasser_boiler',
      name: 'Warmwasser-Speicher',
      kind: 'hot_water',
      automation_allowed: true,
      controllable: true,
      capabilities: ['switch', 'measure_power', 'measure_temperature'],
      reading: { value: 1800, unit: 'W', age_seconds: 6, fresh: true },
      decision: { reason_code: 'ok', message_de: 'Automatik freigegeben, alle Prüfungen bestanden.', message_en: 'ok' },
      warnings: [],
      limits: { verified: true, max_power_w: 3000 },
    },
  ],
  manual_overrides: [],
  modules: MODULES,
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
      reasons_de: ['Solarüberschuss am Nachmittag nutzen, Rest kurz vor Abfahrt aus dem Netz.'],
      reasons_en: ['Use afternoon solar, charge the rest shortly before departure.'],
      warnings: [],
    },
  ],
  audit: [
    { timestamp: '2026-09-24T08:12:00Z', kind: 'module', module_id: 'ev_wallbox_link', message_de: 'Modul aktiviert.', message_en: 'Module enabled.' },
    { timestamp: '2026-09-24T08:14:00Z', kind: 'decision', module_id: 'core', message_de: 'Auto-ID4 sicher der Garage Wallbox zugeordnet.', message_en: 'Car ID4 safely linked to the garage wallbox.' },
    { timestamp: '2026-09-24T08:20:00Z', kind: 'security', module_id: 'core', message_de: 'Netz-Leistung ist veraltet, Automatik pausiert.', message_en: 'Grid power is stale, automation paused.' },
  ],
  ai: { provider_id: 'local_rules', enabled: false, api_key_set: false, report_interval: 'daily', last_report: null },
  providers: [
    { provider_id: 'local_rules', name_de: 'Lokale Regeln (keine Cloud)', name_en: 'Local rules (no cloud)', suggested: true, local: true },
    { provider_id: 'local_model', name_de: 'Lokales Modell', name_en: 'Local model', suggested: false, local: true },
    { provider_id: 'groq', name_de: 'Groq', name_en: 'Groq', suggested: true, local: false },
    { provider_id: 'openai_compatible', name_de: 'Anderer OpenAI-kompatibler Anbieter', name_en: 'Other OpenAI-compatible provider', suggested: false, local: false },
  ],
};

const views = ['dashboard', 'devices', 'store', 'plans', 'security', 'ai', 'audit', 'settings'];

/* Render every view in both languages so the English translation can be
 * reviewed with eyes instead of only through tests. */
const LANGUAGES = ['de', 'en'];
const rendered = Object.fromEntries(
  LANGUAGES.map((lang) => [
    lang,
    Object.fromEntries(
      views.map((view) => [
        view,
        renderApp({ ...state, language: lang, candidates: [] }, view, lang),
      ]),
    ),
  ]),
);

const html = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PV-Manager Vorschau</title>
<style>
:root { color-scheme: dark; }
body { margin: 0; background: #111418; --primary-background-color: #111418; --primary-text-color: #e8eaed; --card-background-color: #1b1f24; --secondary-text-color: #9aa0a6; --divider-color: #2a2f36; --primary-color: #0a84ff; }
.preview-note { max-width: 1180px; margin: 16px auto 0; padding: 10px 14px; border: 1px solid #2a2f36; border-radius: 12px; color: #9aa0a6; font: 13px system-ui; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.preview-langs { margin-left: auto; display: flex; gap: 6px; }
.preview-langs button { border: 1px solid #2a2f36; background: transparent; color: inherit; font: inherit; padding: 5px 12px; border-radius: 999px; cursor: pointer; }
.preview-langs button.active { background: #0a84ff; border-color: #0a84ff; color: #fff; }
${STYLES}
</style>
</head>
<body>
<div class="preview-note">
  Entwicklungsvorschau mit den echten PV-Manager-Renderfunktionen. Keine Home-Assistant-Instanz nötig.
  <span class="preview-langs">
    ${LANGUAGES.map((lang) => `<button type="button" data-preview-lang="${lang}">${lang === 'de' ? 'Deutsch' : 'English'}</button>`).join('')}
  </span>
</div>
<div id="app"></div>
<script>
const VIEWS = ${JSON.stringify(rendered).replaceAll('</', '<\\/')};
const KNOWN_VIEWS = ${JSON.stringify(views)};
let currentLang = 'de';
let currentView = 'dashboard';

function show() {
  document.getElementById('app').innerHTML = VIEWS[currentLang][currentView];
  document.documentElement.lang = currentLang;
  for (const button of document.querySelectorAll('[data-preview-lang]')) {
    button.classList.toggle('active', button.dataset.previewLang === currentLang);
  }
}

document.addEventListener('click', (event) => {
  const langButton = event.target.closest('[data-preview-lang]');
  if (langButton) {
    currentLang = langButton.dataset.previewLang;
    show();
    return;
  }
  const viewButton = event.target.closest('[data-action="view"]');
  if (!viewButton) return;
  const view = viewButton.dataset.view;
  if (!KNOWN_VIEWS.includes(view)) return;
  currentView = view;
  show();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

show();
</script>
</body>
</html>
`;

mkdirSync(join(root, 'preview'), { recursive: true });
const target = join(root, 'preview', 'pv-manager-preview.html');
writeFileSync(target, html, 'utf8');
console.log(`wrote preview/pv-manager-preview.html (${html.length} bytes)`);
