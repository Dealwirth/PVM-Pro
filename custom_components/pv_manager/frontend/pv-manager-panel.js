/* PV Manager custom panel.

This is a standalone application rendered inside a Home Assistant sidebar
entry. It is not a Lovelace dashboard and it does not depend on Home
Assistant frontend card schemas.
*/

import { STYLES } from './styles.js';
import { renderApp, escapeHtml } from './render.js';
import { t } from './i18n.js';

const ALLOWED_VIEWS = new Set(['dashboard', 'devices', 'store', 'plans', 'security', 'ai', 'audit', 'settings']);

class PVManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._started = false;
    this._loading = true;
    this._state = null;
    this._candidates = [];
    this._providers = [];
    this._view = 'dashboard';
    this._lang = 'de';
    this._tutorialStep = 0;
    this._notice = null;
    this._noticeTone = 'ok';
    this._preview = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._started) {
      this._started = true;
      this._load();
    }
  }

  set narrow(value) {
    this._narrow = value;
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    this._render();
  }

  async _load() {
    try {
      const state = await this._hass.callWS({ type: 'pv_manager/get_state' });
      this._state = state;
      this._lang = state.language === 'en' ? 'en' : 'de';
      this._view = ALLOWED_VIEWS.has(this._view) ? this._view : 'dashboard';
      this._tutorialStep = 0;
      this._loading = false;
      try {
        const providers = await this._hass.callWS({ type: 'pv_manager/get_providers' });
        this._providers = providers.providers || [];
      } catch (error) {
        this._providers = [];
      }
      this._render();
    } catch (error) {
      this._loading = false;
      this._error = error && error.message ? error.message : 'unknown_error';
      this._render();
    }
  }

  async _refresh() {
    if (!this._hass) return;
    try {
      const state = await this._hass.callWS({ type: 'pv_manager/get_state' });
      this._state = state;
      this._lang = state.language === 'en' ? 'en' : 'de';
      this._render();
    } catch (error) {
      this._notice = String(error && error.message ? error.message : error);
      this._noticeTone = 'error';
      this._render();
    }
  }

  _render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<style>${STYLES}</style><div class="pm-shell"><div class="pm-card">${escapeHtml(t(this._lang, 'app_title'))}</div></div>`;
      return;
    }
    if (this._loading) {
      this.shadowRoot.innerHTML = `<style>${STYLES}</style><div class="pm-shell"><div class="pm-card">${escapeHtml(t(this._lang, 'loading'))}</div></div>`;
      return;
    }
    if (this._error) {
      this.shadowRoot.innerHTML = `<style>${STYLES}</style><div class="pm-shell"><div class="pm-card"><h2>${escapeHtml(t(this._lang, 'app_title'))}</h2><p class="pm-error">${escapeHtml(this._error)}</p><button class="pm-button" data-action="reload">${escapeHtml(t(this._lang, 'reload'))}</button></div></div>`;
      this._bind();
      return;
    }
    const state = {
      ...(this._state || {}),
      candidates: this._candidates,
      providers: this._providers,
      ai_preview: this._preview,
      show_tutorial: this._state ? !this._state.tutorial_done : false,
      tutorial_step: this._tutorialStep,
    };
    const noticeClass = this._noticeTone === 'error' ? 'pm-error' : 'pm-notice-ok';
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${renderApp(state, this._view, this._lang)}${this._notice ? `<div class="pm-shell"><div class="pm-card"><p class="${noticeClass}">${escapeHtml(this._notice)}</p></div></div>` : ''}`;
    this._bind();
  }

  _bind() {
    this.shadowRoot.querySelectorAll('[data-action]').forEach((element) => {
      element.addEventListener('click', (event) => this._onAction(event, element));
    });
  }

  async _onAction(event, element) {
    const action = element.dataset.action;
    this._notice = null;
    this._noticeTone = 'ok';
    try {
      if (action === 'view') {
        this._view = element.dataset.view;
        this._render();
        return;
      }
      if (action === 'reload') {
        this._error = null;
        this._loading = true;
        this._started = true;
        await this._load();
        return;
      }
      if (action === 'tutorial-next') {
        this._tutorialStep = Math.min(3, this._tutorialStep + 1);
        this._render();
        return;
      }
      if (action === 'tutorial-skip') {
        await this._finishTutorial();
        return;
      }
      if (action === 'tutorial-finish') {
        await this._finishTutorial();
        return;
      }
      if (action === 'tutorial-start') {
        this._tutorialStep = 0;
        this._state.tutorial_done = false;
        this._render();
        return;
      }
      if (action === 'discover') {
        this._notice = t(this._lang, 'search_running');
        this._render();
        const result = await this._hass.callWS({ type: 'pv_manager/discover_devices' });
        this._candidates = result.candidates || [];
        this._notice = null;
        this._render();
        return;
      }
      if (action === 'register') {
        await this._registerCandidate(element.dataset.entity, element.dataset.name);
        return;
      }
      if (action === 'toggle-module') {
        const moduleId = element.dataset.module;
        const enabled = element.dataset.enabled !== 'true';
        const result = await this._hass.callWS({ type: 'pv_manager/set_module', module_id: moduleId, enabled });
        if (!result.ok) {
          this._notice = result.error || 'module_error';
          this._noticeTone = 'error';
        }
        await this._refresh();
        return;
      }
      if (action === 'device-on' || action === 'device-off') {
        const turnOn = action === 'device-on';
        if (turnOn && !window.confirm(t(this._lang, 'confirm_turn_on'))) return;
        const result = await this._hass.callWS({
          type: 'pv_manager/control_device',
          device_id: element.dataset.device,
          turn_on: turnOn,
          user_confirmed: true,
        });
        this._notice = t(this._lang, turnOn ? 'turn_on_done' : 'turn_off_done');
        await this._refresh();
        return;
      }
      if (action === 'manual' || action === 'clear-manual') {
        await this._hass.callWS({
          type: 'pv_manager/set_manual_override',
          device_id: element.dataset.device,
          active: action === 'manual',
        });
        await this._refresh();
        return;
      }
      if (action === 'automode') {
        await this._confirmAutomation(element.dataset.device);
        return;
      }
      if (action === 'estop') {
        const active = element.dataset.active === 'true';
        if (active && !window.confirm(t(this._lang, 'confirm_emergency_stop'))) return;
        await this._hass.callWS({ type: 'pv_manager/emergency_stop', active });
        await this._refresh();
        return;
      }
      if (action === 'save-terminal') {
        const patch = this._readSettings('terminal');
        await this._hass.callWS({ type: 'pv_manager/update_settings', patch: { terminal: patch } });
        this._notice = t(this._lang, 'save_ok');
        await this._refresh();
        return;
      }
      if (action === 'save-settings') {
        const patch = this._readSettings('settings');
        await this._hass.callWS({ type: 'pv_manager/update_settings', patch: { settings: patch } });
        this._notice = t(this._lang, 'save_ok');
        await this._refresh();
        return;
      }
      if (action === 'save-ai') {
        const privacy = this._readSettings('privacy');
        const ai = this._readSettings('ai');
        const keyElement = this.shadowRoot.querySelector('[data-setting-scope="ai-key"]');
        const apiKey = keyElement ? keyElement.value.trim() : '';
        if (apiKey) {
          await this._hass.callWS({ type: 'pv_manager/set_ai_key', api_key: apiKey });
        }
        await this._hass.callWS({
          type: 'pv_manager/set_ai_provider',
          provider_id: ai.provider_id || 'local_rules',
          enabled: (ai.provider_id || 'local_rules') !== 'local_rules' && privacy.mode !== 'local_only',
        });
        await this._hass.callWS({ type: 'pv_manager/update_settings', patch: { privacy, ai } });
        this._notice = t(this._lang, 'save_ok');
        if (keyElement) keyElement.value = '';
        await this._refresh();
        return;
      }
      if (action === 'preview-ai') {
        this._preview = await this._hass.callWS({ type: 'pv_manager/prepare_ai' });
        this._render();
        return;
      }
      if (action === 'request-ai') {
        this._preview = await this._hass.callWS({ type: 'pv_manager/prepare_ai' });
        const mode = (this._state.privacy && this._state.privacy.settings && this._state.privacy.settings.mode) || 'local_only';
        const provider = (this._state.ai && this._state.ai.provider_id) || 'local_rules';
        const confirmed = provider === 'local_rules' || window.confirm(t(this._lang, 'confirm_external_ai'));
        const result = await this._hass.callWS({
          type: 'pv_manager/request_ai',
          provider_id: provider,
          user_confirmed: confirmed,
        });
        if (!result.ok) {
          this._notice = result.error || 'ai_error';
          this._noticeTone = 'error';
        }
        await this._refresh();
        return;
      }
      if (action === 'export-json' || action === 'export-csv') {
        this._download(action === 'export-json' ? 'pv-manager-audit.json' : 'pv-manager-audit.csv',
          action === 'export-json' ? JSON.stringify(this._state.audit || [], null, 2) : this._toCsv(this._state.audit || []));
        return;
      }
      if (action === 'clear-audit') {
        if (!window.confirm(t(this._lang, 'confirm_clear_audit'))) return;
        await this._hass.callWS({ type: 'pv_manager/clear_audit', confirm: true });
        await this._refresh();
        return;
      }
    } catch (error) {
      this._notice = String(error && error.message ? error.message : error);
      this._noticeTone = 'error';
      this._render();
    }
  }

  async _finishTutorial() {
    try {
      await this._hass.callWS({ type: 'pv_manager/complete_tutorial' });
    } catch (error) {
      /* Tutorial must never block the UI. */
    }
    if (this._state) this._state.tutorial_done = true;
    this._render();
  }

  async _registerCandidate(entityId, name) {
    if (!entityId) return;
    const candidate = this._candidates.find((item) => item.entity_id === entityId) || {};
    const select = this.shadowRoot.querySelector(`[data-kind-for="${entityId}"]`);
    const kind = select ? select.value : candidate.kind || 'unknown';
    const device = {
      device_id: entityId,
      entity_id: entityId,
      name: name || candidate.name || entityId,
      nickname: '',
      kind,
      capabilities: candidate.capabilities || [],
      limits: {
        min_power_w: 0,
        max_power_w: 0,
        max_energy_kwh_per_day: 0,
        min_soc: 0,
        max_soc: 100,
        min_temperature_c: 0,
        max_temperature_c: 0,
        phase_count: 1,
        phase_limit_a: 0,
        grid_import_limit_w: 0,
        grid_export_limit_w: 0,
        verified: false,
      },
      fallback: 'no_automation',
      priority: 50,
      automations_allowed: false,
    };
    await this._hass.callWS({ type: 'pv_manager/register_device', device });
    this._candidates = this._candidates.filter((item) => item.entity_id !== entityId);
    this._notice = t(this._lang, 'device_saved');
    await this._refresh();
  }

  async _confirmAutomation(deviceId) {
    const device = (this._state.devices || []).find((item) => item.device_id === deviceId);
    if (!device) return;
    const confirmed = window.confirm(t(this._lang, 'confirm_automation'));
    if (!confirmed) return;
    await this._hass.callWS({
      type: 'pv_manager/register_device',
      device: {
        device_id: device.device_id,
        entity_id: device.device_id,
        name: device.name,
        kind: device.kind,
        capabilities: device.capabilities || [],
        limits: { ...(device.limits || {}), verified: true },
        fallback: device.fallback || 'no_automation',
        priority: device.priority || 50,
        automations_allowed: true,
      },
    });
    this._notice = t(this._lang, 'automation_granted');
    await this._refresh();
  }

  _readSettings(scope) {
    const result = {};
    this.shadowRoot.querySelectorAll(`[data-setting-scope="${scope}"]`).forEach((element) => {
      const key = element.dataset.settingKey;
      if (!key) return;
      if (element.type === 'number') {
        result[key] = Number(element.value) || 0;
      } else if (element.dataset.settingType === 'bool') {
        result[key] = element.value === 'true';
      } else {
        result[key] = element.value;
      }
    });
    return result;
  }

  _download(filename, content) {
    const blob = new Blob([content], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  _toCsv(entries) {
    const header = ['timestamp', 'kind', 'module_id', 'actor', 'message_de'];
    const rows = entries.map((entry) => header.map((key) => `"${String(entry[key] ?? '').replaceAll('"', '""')}"`).join(','));
    return [header.join(','), ...rows].join('\n');
  }
}

if (!customElements.get('pv-manager-panel')) {
  customElements.define('pv-manager-panel', PVManagerPanel);
}
