"""Constants for the PV Manager integration."""

from __future__ import annotations

DOMAIN = "pv_manager"
NAME = "PV Manager"
VERSION = "0.1.0"

PANEL_URL_PATH = "pv-manager"
PANEL_WEBCOMPONENT = "pv-manager-panel"
PANEL_TITLE = "PV Manager"
PANEL_ICON = "mdi:solar-power-variant"
STATIC_URL = "/pv_manager_panel"

CONF_METER_ENTITY = "meter_entity"
CONF_METER_MODE = "meter_mode"
CONF_METER_IMPORT_ENTITY = "meter_import_entity"
CONF_METER_EXPORT_ENTITY = "meter_export_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_PRICE_ENTITY = "price_entity"
CONF_AI_API_KEY = "ai_api_key"

STORAGE_KEY = "pv_manager.runtime.{entry_id}"
STORAGE_VERSION = 1

DEFAULT_STALE_AFTER_SECONDS = 300
DEFAULT_UPDATE_INTERVAL_SECONDS = 30
DEFAULT_AUDIT_LIMIT = 400
DEFAULT_REPORT_INTERVAL = "daily"

SERVICE_SET_MODULE = "set_module"
SERVICE_SET_SETTINGS = "set_settings"
SERVICE_SET_DEVICE_STATE = "set_device_state"
SERVICE_REQUEST_REPORT = "request_report"
SERVICE_RUN_CALIBRATION = "run_calibration"
SERVICE_CANCEL_CALIBRATION = "cancel_calibration"
SERVICE_EMERGENCY_STOP = "emergency_stop"

ATTR_ENTRY_ID = "entry_id"
ATTR_MODULE_ID = "module_id"
ATTR_ENABLED = "enabled"

EVENT_ACTION = f"{DOMAIN}_action"
EVENT_ALERT = f"{DOMAIN}_alert"
