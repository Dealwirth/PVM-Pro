/* PV Manager design system. Uses Home Assistant CSS variables but is a fully
   independent layout - not a Lovelace dashboard. */

export const STYLES = `
:host, .pm-shell {
  background: var(--primary-background-color, #111418);
  color: var(--primary-text-color, #e8eaed);
  font-family: var(--paper-font-body1_-_font-family, 'Roboto', system-ui, sans-serif);
}
:host {
  display: block;
  min-height: 100vh;
  box-sizing: border-box;
}
/* The palette is bound to the shell as well as to the host. The standalone
   preview renders without a shadow root, where :host never matches - a missing
   palette silently turns every colour transparent instead of failing loudly. */
:host, .pm-shell {
  --pm-surface: var(--card-background-color, #1b1f24);
  --pm-surface-2: color-mix(in srgb, var(--pm-surface) 88%, var(--primary-text-color, #fff));
  --pm-accent: var(--primary-color, #0a84ff);
  --pm-pv: #f5b800;
  --pm-grid: #ff6b6b;
  --pm-house: #62b6ff;
  --pm-battery: #4cd97b;
  --pm-warning: #ffb020;
  --pm-critical: #ff3b30;
  --pm-ok: #34c759;
  --pm-radius: 16px;
  --pm-gap: 16px;
  --pm-shadow: 0 1px 2px rgba(0, 0, 0, 0.18), 0 10px 28px rgba(0, 0, 0, 0.13);
  --pm-motion: 140ms cubic-bezier(0.2, 0, 0, 1);
}
* { box-sizing: border-box; }
:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.pm-shell { max-width: 1180px; margin: 0 auto; padding: 20px 20px 64px; }
.pm-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
}
.pm-header h1 { font-size: 26px; font-weight: 600; margin: 0; flex: 1; }
.pm-subtitle { color: var(--secondary-text-color, #9aa0a6); margin: 0 0 20px; font-size: 14px; }
.pm-nav { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 20px; scrollbar-width: none; }
.pm-nav::-webkit-scrollbar { display: none; }
.pm-nav button {
  border: 1px solid var(--divider-color, #2a2f36); background: transparent; color: inherit;
  padding: 9px 14px; border-radius: 999px; cursor: pointer; white-space: nowrap; font-size: 14px;
  transition: background var(--pm-motion), border-color var(--pm-motion), color var(--pm-motion);
}
.pm-nav button:hover { background: var(--pm-surface-2); border-color: var(--pm-accent); }
.pm-nav button.active {
  background: var(--pm-accent); border-color: var(--pm-accent); color: #fff;
  box-shadow: 0 2px 12px color-mix(in srgb, var(--pm-accent) 45%, transparent);
}
.pm-grid { display: grid; gap: var(--pm-gap); }
.pm-cols-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.pm-cols-3 { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.pm-card {
  background: var(--pm-surface); border-radius: var(--pm-radius); padding: 18px;
  border: 1px solid var(--divider-color, #2a2f36);
  box-shadow: var(--pm-shadow);
}
.pm-card h2 { margin: 0 0 10px; font-size: 17px; font-weight: 600; }
.pm-card h3 { margin: 0 0 6px; font-size: 15px; font-weight: 600; }
.pm-card p { margin: 0 0 8px; line-height: 1.5; font-size: 14px; color: var(--secondary-text-color, #b7bcc2); }
.pm-metric { font-size: 30px; font-weight: 650; margin: 4px 0; font-variant-numeric: tabular-nums; letter-spacing: -0.5px; }
.pm-metric small { font-size: 14px; font-weight: 400; color: var(--secondary-text-color, #9aa0a6); margin-left: 4px; }
.pm-muted { color: var(--secondary-text-color, #9aa0a6); font-size: 13px; }
.pm-flow { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; text-align: center; }
.pm-flow .node { background: var(--pm-surface-2); border-radius: 14px; padding: 14px 10px; border: 1px solid var(--divider-color, #2a2f36); }
.pm-flow .node .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 6px; }
.pm-flow .arrow { font-size: 22px; color: var(--secondary-text-color, #9aa0a6); }
.pm-badge {
  display: inline-flex; align-items: center; gap: 6px; border-radius: 999px;
  padding: 3px 10px; font-size: 12px; font-weight: 600; border: 1px solid transparent;
}
.pm-badge.ok { background: color-mix(in srgb, var(--pm-ok) 18%, transparent); color: var(--pm-ok); }
.pm-badge.warn { background: color-mix(in srgb, var(--pm-warning) 18%, transparent); color: var(--pm-warning); }
.pm-badge.crit { background: color-mix(in srgb, var(--pm-critical) 20%, transparent); color: var(--pm-critical); }
.pm-badge.info { background: color-mix(in srgb, var(--pm-accent) 16%, transparent); color: var(--pm-accent); }
.pm-privacy-banner { border-radius: 14px; padding: 14px 16px; font-weight: 700; margin-bottom: 16px; }
.pm-privacy-banner.green { background: color-mix(in srgb, var(--pm-ok) 16%, transparent); border: 2px solid var(--pm-ok); color: var(--pm-ok); }
.pm-privacy-banner.red { background: color-mix(in srgb, var(--pm-critical) 20%, transparent); border: 3px solid var(--pm-critical); color: var(--pm-critical); text-transform: uppercase; letter-spacing: 0.4px; }
.pm-button {
  border: 1px solid var(--divider-color, #2a2f36); background: var(--pm-surface-2); color: inherit;
  border-radius: 10px; padding: 9px 14px; cursor: pointer; font-size: 14px; font-weight: 500;
  transition: background var(--pm-motion), border-color var(--pm-motion), transform var(--pm-motion), box-shadow var(--pm-motion);
}
.pm-button:hover { border-color: var(--pm-accent); background: color-mix(in srgb, var(--pm-accent) 12%, var(--pm-surface-2)); }
.pm-button:active { transform: translateY(1px); }
.pm-button.primary { background: var(--pm-accent); border-color: var(--pm-accent); color: #fff; }
.pm-button.primary:hover {
  background: color-mix(in srgb, var(--pm-accent) 85%, #fff);
  box-shadow: 0 2px 14px color-mix(in srgb, var(--pm-accent) 40%, transparent);
}
.pm-button.danger { background: var(--pm-critical); border-color: var(--pm-critical); color: #fff; font-weight: 700; }
.pm-button.danger:hover { background: color-mix(in srgb, var(--pm-critical) 85%, #fff); }
.pm-button:disabled { opacity: 0.5; cursor: not-allowed; }
.pm-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.pm-field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.pm-field label { font-size: 13px; color: var(--secondary-text-color, #9aa0a6); }
.pm-field input, .pm-field select {
  background: var(--pm-surface-2); color: inherit; border: 1px solid var(--divider-color, #2a2f36);
  border-radius: 10px; padding: 9px 10px; font-size: 14px; width: 100%;
}
.pm-list { display: grid; gap: 10px; }
.pm-list-item {
  background: var(--pm-surface-2); border-radius: 12px; padding: 12px 14px;
  border: 1px solid var(--divider-color, #2a2f36);
  transition: border-color var(--pm-motion), box-shadow var(--pm-motion);
}
.pm-list-item:hover {
  border-color: color-mix(in srgb, var(--pm-accent) 45%, var(--divider-color, #2a2f36));
  box-shadow: var(--pm-shadow);
}
.pm-list-item .head { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.pm-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; word-break: break-word;
  background: var(--pm-surface-2); padding: 10px; border-radius: 10px; max-height: 280px; overflow: auto;
  border: 1px solid var(--divider-color, #2a2f36);
}
.pm-code::-webkit-scrollbar { width: 10px; height: 10px; }
.pm-code::-webkit-scrollbar-thumb { background: var(--divider-color, #2a2f36); border-radius: 999px; }
.pm-code::-webkit-scrollbar-track { background: transparent; }
.pm-bar { height: 10px; border-radius: 6px; background: var(--pm-surface-2); overflow: hidden; display: flex; }
.pm-bar span { display: block; height: 100%; }
.pm-bar .solar { background: var(--pm-pv); }
.pm-bar .grid { background: var(--pm-grid); }
.pm-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; padding: 20px; z-index: 10; }
.pm-modal { background: var(--pm-surface); border-radius: 18px; padding: 22px; max-width: 520px; width: 100%; border: 1px solid var(--divider-color, #2a2f36); }
.pm-steps { display: flex; gap: 6px; margin-bottom: 14px; }
.pm-steps i { width: 26px; height: 5px; border-radius: 3px; background: var(--divider-color, #2a2f36); display: block; }
.pm-steps i.on { background: var(--pm-accent); }
.pm-error { color: var(--pm-critical); font-size: 13px; margin-top: 6px; }
.pm-notice-ok { color: var(--pm-ok); font-size: 13px; margin-top: 6px; font-weight: 600; }
.pm-limits { font-size: 13px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--divider-color, #2a2f36); }
.pm-limits .pm-badge { margin-left: 6px; }
.pm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pm-table th, .pm-table td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--divider-color, #2a2f36); font-variant-numeric: tabular-nums; }
.pm-table th { color: var(--secondary-text-color, #9aa0a6); font-weight: 500; }
.pm-table tbody tr { transition: background var(--pm-motion); }
.pm-table tbody tr:hover { background: var(--pm-surface-2); }
.pm-chart { display: flex; align-items: flex-end; gap: 3px; height: 120px; margin-top: 10px; }
.pm-chart .bar { flex: 1; border-radius: 4px 4px 0 0; background: var(--pm-pv); min-height: 2px; opacity: 0.85; transition: opacity var(--pm-motion); }
.pm-chart .bar:hover { opacity: 1; }
.pm-chart .bar.consumption { background: var(--pm-house); }
.pm-safety { display: flex; gap: 10px; align-items: center; padding: 12px; border-radius: 12px; background: var(--pm-surface-2); }
.pm-safety.crit { border: 2px solid var(--pm-critical); }
@media (max-width: 700px) {
  .pm-shell { padding: 14px 12px 56px; }
  .pm-metric { font-size: 24px; }
  .pm-flow { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
  .pm-button:active { transform: none; }
}
`;
