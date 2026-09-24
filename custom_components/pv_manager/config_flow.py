"""Config and options flow for PV Manager."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CALENDAR_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_METER_ENTITY,
    CONF_METER_EXPORT_ENTITY,
    CONF_METER_IMPORT_ENTITY,
    CONF_METER_MODE,
    CONF_PRICE_ENTITY,
    CONF_PV_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    NAME,
)


def _entity_selector(device_classes: list[str] | None = None, domains: list[str] | None = None):
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=domains or ["sensor"],
            device_class=device_classes or None,
            multiple=False,
        )
    )


def _key(key: str, defaults: dict[str, Any], *, required: bool = False):
    """Build a voluptuous key with a default only when one is known.

    Passing the ``vol.UNDEFINED`` sentinel as a default works in most cases but
    is easy to misuse. Building the marker conditionally keeps the schema
    explicit and avoids empty-string defaults overwriting real values.
    """
    if required:
        if key in defaults and defaults[key] not in (None, ""):
            return vol.Required(key, default=defaults[key])
        return vol.Required(key)
    if key in defaults and defaults[key] not in (None, ""):
        return vol.Optional(key, default=defaults[key])
    return vol.Optional(key)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = {key: value for key, value in (defaults or {}).items() if value not in (None, "")}
    meter_select = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value="signed_net", label="Ein Wert, + Bezug / - Einspeisung"),
                selector.SelectOptionDict(value="import_positive", label="Ein Wert, positiv = Bezug"),
                selector.SelectOptionDict(value="export_positive", label="Ein Wert, positiv = Einspeisung"),
                selector.SelectOptionDict(
                    value="separate", label="Getrennte Werte für Bezug und Einspeisung"
                ),
                selector.SelectOptionDict(value="unknown", label="Unbekannt / später prüfen"),
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    fields: dict[Any, Any] = {
        _key(CONF_METER_ENTITY, defaults, required=True): _entity_selector(
            device_classes=["power", "energy"]
        ),
        _key(CONF_METER_IMPORT_ENTITY, defaults): _entity_selector(device_classes=["power", "energy"]),
        _key(CONF_METER_EXPORT_ENTITY, defaults): _entity_selector(device_classes=["power", "energy"]),
        _key(CONF_METER_MODE, defaults, required=True): meter_select,
        _key(CONF_PV_ENTITY, defaults, required=True): _entity_selector(device_classes=["power", "energy"]),
        _key(CONF_LOAD_ENTITY, defaults): _entity_selector(device_classes=["power", "energy"]),
        _key(CONF_BATTERY_ENTITY, defaults): _entity_selector(device_classes=["power"]),
        _key(CONF_BATTERY_SOC_ENTITY, defaults): _entity_selector(device_classes=["battery"]),
        _key(CONF_WEATHER_ENTITY, defaults): _entity_selector(domains=["weather"]),
        _key(CONF_CALENDAR_ENTITY, defaults): _entity_selector(domains=["calendar"]),
        _key(CONF_PRICE_ENTITY, defaults): _entity_selector(),
    }
    return vol.Schema(fields)


class PVManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set up the single PV Manager instance."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            meter = user_input.get(CONF_METER_ENTITY)
            pv = user_input.get(CONF_PV_ENTITY)
            if not meter or self.hass.states.get(meter) is None:
                errors[CONF_METER_ENTITY] = "entity_not_found"
            if not pv or self.hass.states.get(pv) is None:
                errors[CONF_PV_ENTITY] = "entity_not_found"
            if not errors:
                return self.async_create_entry(title=NAME, data={}, options=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
            description_placeholders={
                "hint": (
                    "PV-Manager erkennt Kandidaten aus Home Assistant. Bitte bestätige die "
                    "wichtigsten Energiequellen. Alles Weitere kannst du später im eigenen "
                    "PV-Manager-Modul-Store aktivieren."
                )
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return PVManagerOptionsFlow()


class PVManagerOptionsFlow(config_entries.OptionsFlow):
    """Allow the user to adjust the source entities later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the same fields with current values."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(dict(self.config_entry.options)),
            description_placeholders={
                "hint": (
                    "Änderungen werden sofort übernommen. Der PV-Manager prüft Vorzeichen und "
                    "zeigt Warnungen, falls Werte nicht zusammenpassen."
                )
            },
        )
