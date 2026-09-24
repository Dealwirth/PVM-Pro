/* Pure rendering helpers. Keeping them free of DOM access makes them
   testable with Node and keeps the custom element small. */

import { t } from './i18n.js';

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function fmt(value, digits = 0, lang = 'de') {
  const number = Number(value);
  if (!Number.isFinite(number)) return '–';
  return number.toLocaleString(lang === 'en' ? 'en-GB' : 'de-DE', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

/** Bind number formatting to one language, so English users do not see German
    thousands separators like "1.234,5". */
function fmtFor(lang) {
  return (value, digits = 0) => fmt(value, digits, lang);
}

function badge(text, kind) {
  return `<span class="pm-badge ${kind}">${escapeHtml(text)}</span>`;
}

function severityBadge(severity, lang) {
  const map = {
    critical: ['crit', lang === 'de' ? 'Kritisch' : 'Critical'],
    warning: ['warn', lang === 'de' ? 'Warnung' : 'Warning'],
    info: ['ok', lang === 'de' ? 'Info' : 'Info'],
  };
  const [kind, label] = map[severity] || map.info;
  return badge(label, kind);
}

function statusFor(device, lang) {
  if (device.automation_allowed) return badge(t(lang, 'automatic_mode'), 'ok');
  return badge(t(lang, 'status_observed'), 'info');
}

/** Show the actual boundary values. Limits must be visible, not only implied
    by a "verified" badge, otherwise a user cannot check what was agreed. */
function limitsSummary(device, lang) {
  const limits = device.limits || {};
  const fmtLocal = fmtFor(lang);
  const parts = [];
  if (Number(limits.max_power_w) > 0) {
    parts.push(`${escapeHtml(t(lang, 'limit_power'))} ≤ ${fmtLocal(limits.max_power_w)} W`);
  }
  if (Number(limits.max_energy_kwh_per_day) > 0) {
    parts.push(`${escapeHtml(t(lang, 'limit_energy'))} ≤ ${fmtLocal(limits.max_energy_kwh_per_day, 2)} kWh`);
  }
  if (Number(limits.phase_limit_a) > 0) {
    parts.push(`${escapeHtml(t(lang, 'limit_phase'))} ≤ ${fmtLocal(limits.phase_limit_a, 1)} A`);
  }
  if (Number(limits.max_soc) > Number(limits.min_soc)) {
    parts.push(`${escapeHtml(t(lang, 'limit_soc'))} ${fmtLocal(limits.min_soc)}–${fmtLocal(limits.max_soc)} %`);
  }
  if (Number(limits.max_temperature_c) > Number(limits.min_temperature_c)) {
    parts.push(
      `${escapeHtml(t(lang, 'limit_temperature'))} ${fmtLocal(limits.min_temperature_c)}–${fmtLocal(limits.max_temperature_c)} °C`
    );
  }
  const verified = limits.verified === true;
  const badgeHtml = badge(t(lang, verified ? 'limits_ok' : 'limits_missing'), verified ? 'ok' : 'warn');
  if (parts.length === 0) {
    return `<p class="pm-limits"><span class="pm-muted">${escapeHtml(t(lang, 'limits_none'))}</span> ${badgeHtml}</p>`;
  }
  return `<p class="pm-limits"><span class="pm-muted">${escapeHtml(t(lang, 'limits_values'))}:</span> ${parts.join(' · ')} ${badgeHtml}</p>`;
}

export function renderTutorial(lang, step) {
  const titles = [1, 2, 3, 4].map((index) => t(lang, `tutorial_${index}_title`));
  const texts = [1, 2, 3, 4].map((index) => t(lang, `tutorial_${index}_text`));
  const current = Math.max(0, Math.min(step, 3));
  return `
  <div class="pm-overlay" role="dialog" aria-modal="true" aria-label="${escapeHtml(t(lang, 'tutorial_title'))}">
    <div class="pm-modal">
      <h2>${escapeHtml(t(lang, 'tutorial_title'))}</h2>
      <p class="pm-muted">${t(lang, 'tutorial_step')} ${current + 1} ${t(lang, 'of')} 4</p>
      <div class="pm-steps">${[0, 1, 2, 3].map((index) => `<i class="${index <= current ? 'on' : ''}"></i>`).join('')}</div>
      <h3>${escapeHtml(titles[current])}</h3>
      <p>${escapeHtml(texts[current])}</p>
      <div class="pm-row" style="justify-content:flex-end;margin-top:16px">
        <button class="pm-button" data-action="tutorial-skip">${escapeHtml(t(lang, 'skip'))}</button>
        ${current < 3
          ? `<button class="pm-button primary" data-action="tutorial-next">${escapeHtml(t(lang, 'next'))}</button>`
          : `<button class="pm-button primary" data-action="tutorial-finish">${escapeHtml(t(lang, 'finish'))}</button>`}
      </div>
    </div>
  </div>`;
}

export function renderDashboard(state, lang) {
  const fmt = fmtFor(lang);
  const summary = state.summary || {};
  const forecast = state.forecast || {};
  const privacy = state.privacy || {};
  const security = state.security || {};
  const outage = Boolean(state.emergency_stop);
  const solarPoints = Array.isArray(forecast.solar) ? forecast.solar : [];
  const consumptionPoints = Array.isArray(forecast.consumption) ? forecast.consumption : [];
  const maxSolar = Math.max(0.1, ...solarPoints.map((point) => Number(point.expected_kwh) || 0));
  return `
  <div class="pm-privacy-banner ${privacy.external_active ? 'red' : 'green'}">
    ${escapeHtml(lang === 'de' ? privacy.label_de : privacy.label_en)}
  </div>
  ${outage ? `<div class="pm-privacy-banner red">${escapeHtml(t(lang, 'emergency_stop_on'))}</div>` : ''}
  <div class="pm-grid pm-cols-3">
    <div class="pm-card"><h2><span style="color:var(--pm-pv)">●</span> ${escapeHtml(t(lang, 'pv'))}</h2>
      <div class="pm-metric">${fmt(summary.pv_w)}<small>W</small></div>
      <p class="pm-muted">${escapeHtml(t(lang, 'today_forecast'))}: ${fmt(forecast.solar_kwh_next_24h, 1)} kWh</p></div>
    <div class="pm-card"><h2><span style="color:var(--pm-grid)">●</span> ${escapeHtml(t(lang, 'grid'))}</h2>
      <div class="pm-metric">${fmt(summary.grid_import_w)}<small>W ${escapeHtml(t(lang, 'import'))}</small></div>
      <p class="pm-muted">${fmt(summary.grid_export_w)} W ${escapeHtml(t(lang, 'export'))}</p></div>
    <div class="pm-card"><h2><span style="color:var(--pm-house)">●</span> ${escapeHtml(t(lang, 'house'))}</h2>
      <div class="pm-metric">${fmt(summary.load_w)}<small>W</small></div>
      <p class="pm-muted">${escapeHtml(t(lang, 'consumption_forecast'))}: ${fmt(forecast.consumption_kwh_next_24h, 1)} kWh</p></div>
    <div class="pm-card"><h2><span style="color:var(--pm-battery)">●</span> ${escapeHtml(t(lang, 'battery'))}</h2>
      <div class="pm-metric">${summary.battery_soc == null ? '–' : fmt(summary.battery_soc)}<small>%</small></div>
      <p class="pm-muted">${fmt(summary.battery_charge_w)} W laden · ${fmt(summary.battery_discharge_w)} W entladen</p></div>
    <div class="pm-card"><h2>${escapeHtml(t(lang, 'confidence'))}</h2>
      <div class="pm-metric">${fmt((forecast.confidence || 0) * 100)}<small>%</small></div>
      <p class="pm-muted">${escapeHtml(forecast.confidence_label || '–')}</p></div>
    <div class="pm-card"><h2>${escapeHtml(t(lang, 'security_score'))}</h2>
      <div class="pm-metric">${fmt(security.score)}<small>%</small></div>
      <p class="pm-muted">${security.findings ? security.findings.length : 0} ${escapeHtml(t(lang, 'findings'))}</p></div>
  </div>
  <div class="pm-grid pm-cols-2" style="margin-top:16px">
    <div class="pm-card">
      <h2>${escapeHtml(lang === 'de' ? 'Energiefluss' : 'Energy flow')}</h2>
      <div class="pm-flow">
        <div class="node"><div class="dot" style="background:var(--pm-pv)"></div><strong>${escapeHtml(t(lang, 'pv'))}</strong><div>${fmt(summary.pv_w)} W</div></div>
        <div class="arrow">→</div>
        <div class="node"><div class="dot" style="background:var(--pm-house)"></div><strong>${escapeHtml(t(lang, 'house'))}</strong><div>${fmt(summary.load_w)} W</div></div>
        <div class="node"><div class="dot" style="background:var(--pm-grid)"></div><strong>${escapeHtml(t(lang, 'grid'))}</strong><div>${fmt(summary.grid_import_w)} / ${fmt(summary.grid_export_w)} W</div></div>
        <div class="arrow">↔</div>
        <div class="node"><div class="dot" style="background:var(--pm-battery)"></div><strong>${escapeHtml(t(lang, 'battery'))}</strong><div>${fmt(summary.battery_charge_w)} / ${fmt(summary.battery_discharge_w)} W</div></div>
      </div>
    </div>
    <div class="pm-card">
      <h2>${escapeHtml(t(lang, 'today_forecast'))}</h2>
      <div class="pm-chart">
        ${solarPoints.slice(0, 24).map((point) => `<div class="bar" style="height:${Math.max(2, (Number(point.expected_kwh) / maxSolar) * 100)}%" title="${escapeHtml(point.start)}: ${fmt(point.expected_kwh, 2)} kWh"></div>`).join('')}
      </div>
      <p class="pm-muted">${escapeHtml(lang === 'de' ? 'Balken: erwartete Solar-Energie pro Stunde.' : 'Bars: expected solar energy per hour.')}</p>
      <div class="pm-chart" style="height:60px">
        ${consumptionPoints.slice(0, 24).map((point) => `<div class="bar consumption" style="height:${Math.max(2, (Number(point.expected_kwh) / Math.max(0.1, maxSolar)) * 100)}%" title="${escapeHtml(point.start)}: ${fmt(point.expected_kwh, 2)} kWh"></div>`).join('')}
      </div>
      <p class="pm-muted">${escapeHtml(lang === 'de' ? 'Balken: erwarteter Verbrauch pro Stunde.' : 'Bars: expected consumption per hour.')}</p>
    </div>
  </div>
  ${summary.balance_ok === false ? `<div class="pm-card" style="margin-top:16px;border-color:var(--pm-warning)"><h2>${escapeHtml(lang === 'de' ? 'Energiebilanz prüfen' : 'Check energy balance')}</h2><p>${escapeHtml(lang === 'de' ? 'Die Messwerte passen rechnerisch nicht zusammen. Der PV-Manager pausiert Automatik, bis die Zuordnung stimmt.' : 'Readings do not add up. PV Manager pauses automation until the assignment is correct.')}</p></div>` : ''}`;
}

export function renderDevices(state, lang, candidates) {
  const fmt = fmtFor(lang);
  const devices = Array.isArray(state.devices) ? state.devices : [];
  const candidateList = candidates || [];
  const overrides = new Set(Array.isArray(state.manual_overrides) ? state.manual_overrides : []);
  return `
  <div class="pm-row" style="justify-content:space-between">
    <div><h2>${escapeHtml(t(lang, 'devices_title'))}</h2><p class="pm-subtitle">${escapeHtml(t(lang, 'devices_subtitle'))}</p></div>
    <button class="pm-button primary" data-action="discover">${escapeHtml(t(lang, 'discover'))}</button>
  </div>
  ${devices.length === 0 ? `<div class="pm-card"><p>${escapeHtml(t(lang, 'no_devices'))}</p></div>` : ''}
  <div class="pm-list">
    ${devices.map((device) => `
      <div class="pm-list-item">
        <div class="head">
          <div><h3>${escapeHtml(device.name)}</h3><p class="pm-muted">${escapeHtml(device.kind)} · ${escapeHtml(device.device_id)}</p></div>
          <div class="pm-row">${statusFor(device, lang)}${device.controllable
            ? `<button class="pm-button" data-action="device-off" data-device="${escapeHtml(device.device_id)}">${escapeHtml(t(lang, 'turn_off'))}</button>${device.automation_allowed || overrides.has(device.device_id)
              ? `<button class="pm-button" data-action="device-on" data-device="${escapeHtml(device.device_id)}">${escapeHtml(t(lang, 'turn_on'))}</button>`
              : ''}`
            : ''}${device.automation_allowed
            ? (overrides.has(device.device_id)
              ? `<button class="pm-button primary" data-action="clear-manual" data-device="${escapeHtml(device.device_id)}">${escapeHtml(t(lang, 'automatic_mode'))}</button>`
              : `<button class="pm-button" data-action="manual" data-device="${escapeHtml(device.device_id)}">${escapeHtml(t(lang, 'manual_mode'))}</button>`)
            : `<button class="pm-button primary" data-action="automode" data-device="${escapeHtml(device.device_id)}">${escapeHtml(t(lang, 'confirm_device'))}</button>`}</div>
        </div>
        <div class="pm-row" style="margin-top:8px">
          <span>${escapeHtml(t(lang, 'reading'))}: <strong>${fmt(device.reading && device.reading.value)}</strong> ${escapeHtml((device.reading && device.reading.unit) || '')}</span>
          <span class="pm-muted">${escapeHtml(t(lang, 'age'))}: ${device.reading && device.reading.age_seconds != null ? `${fmt(device.reading.age_seconds)} ${escapeHtml(t(lang, 'seconds'))}` : '–'}</span>
          <span>${escapeHtml(t(lang, 'fallback'))}: <strong>${escapeHtml(device.decision ? device.decision.reason_code : '–')}</strong></span>
        </div>
        <p class="pm-muted">${escapeHtml(device.decision ? (lang === 'de' ? device.decision.message_de : device.decision.message_en) : '')}</p>
        ${limitsSummary(device, lang)}
        ${Array.isArray(device.warnings) && device.warnings.length
          ? `<p class="pm-error">${escapeHtml(t(lang, 'warnings'))}: ${escapeHtml(device.warnings.join(', '))}</p>`
          : ''}
      </div>`).join('')}
  </div>
  ${candidateList.length ? `
    <div class="pm-card" style="margin-top:16px">
      <h2>${escapeHtml(lang === 'de' ? 'Gefundene Geräte' : 'Discovered devices')}</h2>
      <table class="pm-table">
        <thead><tr><th>${escapeHtml(t(lang, 'candidate_name'))}</th><th>${escapeHtml(t(lang, 'candidate_kind'))}</th><th>${escapeHtml(t(lang, 'confidence'))}</th><th></th></tr></thead>
        <tbody>
          ${candidateList.slice(0, 40).map((candidate) => `
            <tr>
              <td>${escapeHtml(candidate.name)}<div class="pm-muted">${escapeHtml(candidate.entity_id)}</div></td>
              <td>
                <select data-kind-for="${escapeHtml(candidate.entity_id)}">
                  ${['unknown', 'grid_meter', 'pv', 'load', 'battery', 'ev_charger', 'ev', 'heat_pump', 'hot_water', 'pool', 'ventilation', 'flexible_load']
                    .map((kind) => `<option value="${kind}" ${candidate.kind === kind ? 'selected' : ''}>${escapeHtml(kind)}</option>`).join('')}
                </select>
              </td>
              <td>${fmt((candidate.score || 0) * 100)}%</td>
              <td><button class="pm-button primary" data-action="register" data-entity="${escapeHtml(candidate.entity_id)}" data-name="${escapeHtml(candidate.name)}">${escapeHtml(t(lang, 'confirm_device'))}</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>` : ''}`;
}

export function renderStore(state, lang) {
  const modules = Array.isArray(state.modules) ? state.modules : [];
  const groups = {};
  for (const module of modules) {
    const key = module.category || 'base';
    groups[key] = groups[key] || [];
    groups[key].push(module);
  }
  const categoryNames = {
    base: lang === 'de' ? 'Grundfunktion' : 'Core',
    energy: lang === 'de' ? 'Energie' : 'Energy',
    devices: lang === 'de' ? 'Geräte' : 'Devices',
    intelligence: lang === 'de' ? 'Intelligenz' : 'Intelligence',
    safety: lang === 'de' ? 'Sicherheit' : 'Safety',
    comfort: lang === 'de' ? 'Komfort' : 'Comfort',
  };
  return `
  <h2>${escapeHtml(t(lang, 'store_title'))}</h2>
  <p class="pm-subtitle">${escapeHtml(t(lang, 'store_subtitle'))}</p>
  ${Object.entries(groups).map(([category, entries]) => `
    <h3 style="margin-top:18px">${escapeHtml(categoryNames[category] || category)}</h3>
    <div class="pm-grid pm-cols-2">
      ${entries.map((module) => `
        <div class="pm-card">
          <div class="pm-row" style="justify-content:space-between">
            <h3>${escapeHtml(lang === 'de' ? module.name_de : module.name_en)}</h3>
            ${module.optional
              ? badge(module.enabled ? t(lang, 'store_active') : t(lang, 'store_inactive'), module.enabled ? 'ok' : 'info')
              : badge(t(lang, 'store_base'), 'ok')}
          </div>
          <p>${escapeHtml(lang === 'de' ? module.summary_de : module.summary_en)}</p>
          <p class="pm-muted"><strong>${escapeHtml(t(lang, 'store_reason'))}</strong> ${escapeHtml(lang === 'de' ? module.reason_de : module.reason_en)}</p>
          ${module.optional
            ? `<button class="pm-button ${module.enabled ? '' : 'primary'}" data-action="toggle-module" data-module="${escapeHtml(module.module_id)}" data-enabled="${module.enabled ? 'true' : 'false'}">${escapeHtml(module.enabled ? t(lang, 'store_deactivate') : t(lang, 'store_activate'))}</button>`
            : ''}
        </div>`).join('')}
    </div>`).join('')}`;
}

export function renderPlans(state, lang) {
  const fmt = fmtFor(lang);
  const plans = Array.isArray(state.plans) ? state.plans : [];
  return `
  <h2>${escapeHtml(t(lang, 'plans_title'))}</h2>
  <p class="pm-subtitle">${escapeHtml(t(lang, 'plans_subtitle'))}</p>
  ${plans.length === 0 ? `<div class="pm-card"><p>${escapeHtml(t(lang, 'no_plans'))}</p></div>` : ''}
  <div class="pm-grid pm-cols-2">
    ${plans.map((plan) => {
      const total = Math.max(0.001, (plan.solar_energy_kwh || 0) + (plan.grid_energy_kwh || 0));
      const solarPct = ((plan.solar_energy_kwh || 0) / total) * 100;
      return `
      <div class="pm-card">
        <div class="pm-row" style="justify-content:space-between">
          <h3>${escapeHtml(plan.wallbox_name || plan.wallbox_id)}</h3>
          ${badge(plan.feasible ? (lang === 'de' ? 'möglich' : 'feasible') : (lang === 'de' ? 'nicht möglich' : 'not feasible'), plan.feasible ? 'ok' : 'warn')}
        </div>
        ${plan.vehicle_name
          ? `<p class="pm-muted">${escapeHtml(t(lang, 'vehicle'))}: <strong>${escapeHtml(plan.vehicle_name)}</strong></p>`
          : ''}
        <p class="pm-muted">${escapeHtml(t(lang, 'planned_energy'))}: <strong>${fmt(plan.planned_energy_kwh, 2)} kWh</strong></p>
        <div class="pm-bar" title="${fmt(solarPct)}% Solar">
          <span class="solar" style="width:${Math.max(0, Math.min(100, solarPct))}%"></span>
          <span class="grid" style="width:${100 - Math.max(0, Math.min(100, solarPct))}%"></span>
        </div>
        <p class="pm-muted">${escapeHtml(t(lang, 'solar_share'))}: ${fmt(plan.solar_energy_kwh, 2)} kWh · ${escapeHtml(t(lang, 'grid_share'))}: ${fmt(plan.grid_energy_kwh, 2)} kWh</p>
        ${(plan.reasons_de || []).length ? `<p><strong>${escapeHtml(t(lang, 'reason'))}:</strong> ${escapeHtml((lang === 'de' ? plan.reasons_de : plan.reasons_en).join(' '))}</p>` : ''}
        ${(plan.warnings || []).length ? `<p class="pm-error">${escapeHtml((plan.warnings || []).join(', '))}</p>` : ''}
      </div>`;
    }).join('')}
  </div>`;
}

export function renderSecurity(state, lang) {
  const fmt = fmtFor(lang);
  const security = state.security || {};
  const findings = Array.isArray(security.findings) ? security.findings : [];
  return `
  <h2>${escapeHtml(t(lang, 'security_title'))}</h2>
  <p class="pm-subtitle">${escapeHtml(t(lang, 'security_subtitle'))}</p>
  <div class="pm-card">
    <div class="pm-row" style="justify-content:space-between">
      <div class="pm-safety ${security.overall === 'critical' ? 'crit' : ''}">
        ${severityBadge(security.overall || 'info', lang)}
        <strong>${escapeHtml(lang === 'de' ? security.summary_de : security.summary_en)}</strong>
      </div>
      <div class="pm-metric">${fmt(security.score)}<small>%</small></div>
    </div>
    <div class="pm-row" style="margin-top:12px">
      <div class="pm-field"><label>${escapeHtml(t(lang, 'terminal_level'))}</label>
        <select data-setting-scope="terminal" data-setting-key="level">
          ${['observe', 'assist', 'intervene'].map((value) => `<option value="${value}" ${(state.terminal && state.terminal.level) === value ? 'selected' : ''}>${escapeHtml(t(lang, value === 'observe' ? 'level_observe' : value === 'assist' ? 'level_assist' : 'level_intervene'))}</option>`).join('')}
        </select>
      </div>
      <div class="pm-field"><label>${escapeHtml(t(lang, 'reaction'))}</label>
        <select data-setting-scope="terminal" data-setting-key="reaction">
          ${['immediate', '30s', '5m', 'next_check'].map((value) => `<option value="${value}" ${(state.terminal && state.terminal.reaction) === value ? 'selected' : ''}>${escapeHtml(t(lang, value === 'immediate' ? 'reaction_immediate' : value === '30s' ? 'reaction_30s' : value === '5m' ? 'reaction_5m' : 'reaction_next'))}</option>`).join('')}
        </select>
      </div>
      <button class="pm-button primary" data-action="save-terminal">${escapeHtml(t(lang, 'save'))}</button>
      <button class="pm-button danger" data-action="estop" data-active="${state.emergency_stop ? 'false' : 'true'}">${escapeHtml(state.emergency_stop ? t(lang, 'emergency_stop_reset') : t(lang, 'emergency_stop_off'))}</button>
    </div>
    <p class="pm-muted">${escapeHtml(t(lang, 'emergency_stop_hint'))}</p>
  </div>
  <div class="pm-card" style="margin-top:16px">
    <h3>${escapeHtml(t(lang, 'findings'))}</h3>
    ${findings.length === 0 ? `<p class="pm-muted">${escapeHtml(t(lang, 'no_findings'))}</p>` : ''}
    <div class="pm-list">
      ${findings.map((finding) => `
        <div class="pm-list-item">
          <div class="head"><strong>${escapeHtml(lang === 'de' ? finding.title_de : finding.title_en)}</strong>${severityBadge(finding.severity, lang)}</div>
          <p>${escapeHtml(lang === 'de' ? finding.detail_de : finding.detail_en)}</p>
          <p class="pm-muted"><strong>${escapeHtml(t(lang, 'repair'))}:</strong> ${escapeHtml(lang === 'de' ? finding.repair_de : finding.repair_en)}</p>
        </div>`).join('')}
    </div>
  </div>`;
}

export function renderAi(state, lang, providers) {
  const privacy = state.privacy || {};
  const ai = state.ai || {};
  const report = ai.last_report;
  const list = providers && providers.length ? providers : [];
  return `
  <h2>${escapeHtml(t(lang, 'ai_title'))}</h2>
  <p class="pm-subtitle">${escapeHtml(t(lang, 'ai_subtitle'))}</p>
  <div class="pm-privacy-banner ${privacy.external_active ? 'red' : 'green'}">${escapeHtml(lang === 'de' ? privacy.label_de : privacy.label_en)}</div>
  <div class="pm-card">
    <div class="pm-field"><label>${escapeHtml(t(lang, 'privacy_mode'))}</label>
      <select data-setting-scope="privacy" data-setting-key="mode">
        ${['local_only', 'pseudonymous', 'extended'].map((value) => `<option value="${value}" ${(privacy.settings && privacy.settings.mode) === value ? 'selected' : ''}>${escapeHtml(t(lang, value === 'local_only' ? 'mode_local' : value === 'pseudonymous' ? 'mode_pseudo' : 'mode_extended'))}</option>`).join('')}
      </select>
    </div>
    <div class="pm-row">
      <div class="pm-field" style="min-width:260px"><label>${escapeHtml(t(lang, 'provider'))}</label>
        <select data-setting-scope="ai" data-setting-key="provider_id">
          ${list.map((provider) => {
            const label = lang === 'de' ? provider.name_de : provider.name_en;
            const hint = provider.suggested
              ? ` · ${escapeHtml(t(lang, provider.local ? 'provider_local_suggested' : 'provider_suggested'))}`
              : '';
            return `<option value="${escapeHtml(provider.provider_id)}" ${ai.provider_id === provider.provider_id ? 'selected' : ''}>${escapeHtml(label)}${hint}</option>`;
          }).join('')}
        </select>
      </div>
      <div class="pm-field" style="min-width:180px"><label>${escapeHtml(t(lang, 'report_interval'))}</label>
        <select data-setting-scope="ai" data-setting-key="report_interval">
          ${['off', 'hourly', 'daily', 'weekly', 'on_error', 'manual'].map((value) => `<option value="${value}" ${ai.report_interval === value ? 'selected' : ''}>${escapeHtml(t(lang, `interval_${value === 'on_error' ? 'on_error' : value}`))}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="pm-field"><label>${escapeHtml(t(lang, 'api_key'))}</label>
      <input type="password" autocomplete="off" data-setting-scope="ai-key" data-setting-key="api_key" placeholder="${ai.api_key_set ? '••••••••' : ''}">
      <span class="pm-muted">${escapeHtml(t(lang, 'api_key_hint'))}</span>
    </div>
    <div class="pm-row">
      <button class="pm-button primary" data-action="save-ai">${escapeHtml(t(lang, 'save'))}</button>
      <button class="pm-button" data-action="preview-ai">${escapeHtml(t(lang, 'preview'))}</button>
      <button class="pm-button" data-action="request-ai">${escapeHtml(t(lang, 'request_report'))}</button>
    </div>
    <p class="pm-muted">${escapeHtml(t(lang, 'ai_advisory_only'))}</p>
  </div>
  <div class="pm-card" style="margin-top:16px">
    <h3>${escapeHtml(t(lang, 'preview'))}</h3>
    ${state.ai_preview ? `<pre class="pm-code">${escapeHtml(JSON.stringify(state.ai_preview, null, 2))}</pre>` : `<p class="pm-muted">${escapeHtml(t(lang, 'preview_empty'))}</p>`}
  </div>
  ${report ? `
  <div class="pm-card" style="margin-top:16px">
    <h3>${escapeHtml(lang === 'de' ? report.title_de : report.title_en)}</h3>
    <p>${escapeHtml(lang === 'de' ? report.summary_de : report.summary_en)}</p>
    ${report.external_data_sent ? `<div class="pm-privacy-banner red">${escapeHtml(lang === 'de' ? 'ROT: Externe Datenübertragung war aktiv.' : 'RED: External data transfer was active.')}</div>` : ''}
    ${(report.repair_de || []).length ? `<p><strong>${escapeHtml(t(lang, 'repair'))}:</strong></p><ul>${(lang === 'de' ? report.repair_de : report.repair_en).map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ul>` : ''}
  </div>` : ''}`;
}

export function renderAudit(state, lang) {
  const entries = Array.isArray(state.audit) ? state.audit : [];
  return `
  <div class="pm-row" style="justify-content:space-between">
    <div><h2>${escapeHtml(t(lang, 'audit_title'))}</h2><p class="pm-subtitle">${escapeHtml(t(lang, 'audit_subtitle'))}</p></div>
    <div class="pm-row">
      <button class="pm-button" data-action="export-json">${escapeHtml(t(lang, 'export_json'))}</button>
      <button class="pm-button" data-action="export-csv">${escapeHtml(t(lang, 'export_csv'))}</button>
      <button class="pm-button danger" data-action="clear-audit">${escapeHtml(t(lang, 'clear_audit'))}</button>
    </div>
  </div>
  <div class="pm-card">
    ${entries.length === 0 ? '<p class="pm-muted">–</p>' : `
    <table class="pm-table">
      <thead><tr><th>${escapeHtml(lang === 'de' ? 'Zeit' : 'Time')}</th><th>${escapeHtml(lang === 'de' ? 'Art' : 'Kind')}</th><th>${escapeHtml(lang === 'de' ? 'Modul' : 'Module')}</th><th>${escapeHtml(lang === 'de' ? 'Meldung' : 'Message')}</th></tr></thead>
      <tbody>${entries.slice(0, 80).map((entry) => `
        <tr><td>${escapeHtml(entry.timestamp)}</td><td>${escapeHtml(entry.kind)}</td><td>${escapeHtml(entry.module_id)}</td><td>${escapeHtml(lang === 'de' ? entry.message_de : entry.message_en)}</td></tr>`).join('')}
      </tbody>
    </table>`}
  </div>`;
}

export function renderSettings(state, lang) {
  const settings = state.settings || {};
  return `
  <h2>${escapeHtml(t(lang, 'settings_title'))}</h2>
  <p class="pm-subtitle">${escapeHtml(t(lang, 'settings_subtitle'))}</p>
  <div class="pm-card">
    <div class="pm-row">
      <div class="pm-field" style="min-width:200px"><label>${escapeHtml(t(lang, 'language'))}</label>
        <select data-setting-scope="settings" data-setting-key="language">
          <option value="de" ${state.language === 'de' ? 'selected' : ''}>Deutsch</option>
          <option value="en" ${state.language === 'en' ? 'selected' : ''}>English</option>
        </select>
      </div>
      <div class="pm-field" style="min-width:200px"><label>${escapeHtml(t(lang, 'theme'))}</label>
        <select data-setting-scope="settings" data-setting-key="theme">
          ${['auto', 'light', 'dark'].map((value) => `<option value="${value}" ${state.theme === value ? 'selected' : ''}>${escapeHtml(t(lang, value === 'auto' ? 'theme_auto' : value === 'light' ? 'theme_light' : 'theme_dark'))}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="pm-row">
      <div class="pm-field" style="min-width:220px"><label>${escapeHtml(t(lang, 'grid_import_limit'))}</label>
        <input type="number" min="0" step="100" value="${escapeHtml(settings.grid_import_limit_w ?? 0)}" data-setting-scope="settings" data-setting-key="grid_import_limit_w">
      </div>
      <div class="pm-field" style="min-width:220px"><label>${escapeHtml(t(lang, 'grid_export_limit'))}</label>
        <input type="number" min="0" step="100" value="${escapeHtml(settings.grid_export_limit_w ?? 0)}" data-setting-scope="settings" data-setting-key="grid_export_limit_w">
      </div>
      <div class="pm-field" style="min-width:220px"><label>${escapeHtml(t(lang, 'pv_peak'))}</label>
        <input type="number" min="0" step="100" value="${escapeHtml(settings.pv_peak_w ?? 0)}" data-setting-scope="settings" data-setting-key="pv_peak_w">
      </div>
    </div>
    <div class="pm-field" style="max-width:320px"><label>${escapeHtml(t(lang, 'grid_charging_allowed'))}</label>
      <select data-setting-scope="settings" data-setting-key="grid_charging_allowed" data-setting-type="bool">
        <option value="false" ${!settings.grid_charging_allowed ? 'selected' : ''}>${escapeHtml(t(lang, 'no'))}</option>
        <option value="true" ${settings.grid_charging_allowed ? 'selected' : ''}>${escapeHtml(t(lang, 'yes'))}</option>
      </select>
    </div>
    <div class="pm-row">
      <button class="pm-button primary" data-action="save-settings">${escapeHtml(t(lang, 'save'))}</button>
      <button class="pm-button" data-action="tutorial-start">${escapeHtml(t(lang, 'tutorial'))}</button>
    </div>
    <p class="pm-muted">${escapeHtml(t(lang, 'deletion_scope'))}</p>
  </div>`;
}

export function renderApp(state, view, lang) {
  const views = {
    dashboard: renderDashboard(state, lang),
    devices: renderDevices(state, lang, state.candidates),
    store: renderStore(state, lang),
    plans: renderPlans(state, lang),
    security: renderSecurity(state, lang),
    ai: renderAi(state, lang, state.providers),
    audit: renderAudit(state, lang),
    settings: renderSettings(state, lang),
  };
  const nav = [
    ['dashboard', 'nav_dashboard'],
    ['devices', 'nav_devices'],
    ['store', 'nav_store'],
    ['plans', 'nav_plans'],
    ['security', 'nav_security'],
    ['ai', 'nav_ai'],
    ['audit', 'nav_audit'],
    ['settings', 'nav_settings'],
  ];
  return `
  <div class="pm-shell">
    <div class="pm-header">
      <h1>${escapeHtml(t(lang, 'app_title'))}</h1>
      ${state.emergency_stop ? badge(t(lang, 'emergency_stop_on'), 'crit') : ''}
    </div>
    <nav class="pm-nav">
      ${nav.map(([key, label]) => `<button class="${view === key ? 'active' : ''}" data-action="view" data-view="${key}">${escapeHtml(t(lang, label))}</button>`).join('')}
    </nav>
    <main>${views[view] || views.dashboard}</main>
  </div>
  ${state.show_tutorial ? renderTutorial(lang, state.tutorial_step || 0) : ''}`;
}
